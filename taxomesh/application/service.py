"""Application service layer for taxomesh.

TaxomeshService is the single public facade for all taxomesh operations.
It delegates all reads and writes to a pluggable repository backend and
contains no storage logic itself.
"""

import heapq
import logging
import tomllib
from collections.abc import Callable, Collection, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Literal, TypeVar
from uuid import UUID, uuid4

from taxomesh.application.search import DEFAULT_SEARCH_LIMIT, SearchCandidate, SearchEngine
from taxomesh.domain.constants import DEFAULT_ITEM_EXTERNAL_ID, ROOT_CATEGORY_NAME
from taxomesh.domain.dag import check_no_cycle
from taxomesh.domain.graph import CategoryNode, TaxomeshGraph
from taxomesh.domain.models import Category, CategoryParentLink, Item, ItemParentLink, ItemRelationLink, Tag
from taxomesh.domain.types import ExternalId
from taxomesh.exceptions import (
    TaxomeshCategoryNotFoundError,
    TaxomeshConfigError,
    TaxomeshCyclicDependencyError,
    TaxomeshDuplicateSlugError,
    TaxomeshItemNotFoundError,
    TaxomeshRelationError,
    TaxomeshRootCategoryError,
    TaxomeshTagNotFoundError,
)
from taxomesh.ports.repository import TaxomeshRepositoryBase
from taxomesh.utils.memoize import clear_all_caches, memoize

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

_DEFAULT_CONFIG_FILENAME: Final[str] = "taxomesh.toml"
DEFAULT_CACHE_TTL: Final[int] = 5


class _UnsetType:
    """Singleton sentinel distinguishing 'not provided' from None in update methods."""


_UNSET: Final[_UnsetType] = _UnsetType()


def _normalise_external_ids(external_ids: Iterable[str]) -> frozenset[str]:
    """Strip and deduplicate external IDs, dropping blanks."""
    return frozenset(str(v).strip() for v in external_ids if str(v).strip())


class TaxomeshService:
    """Single entry point for all taxomesh category, item, and tag operations.

    Accepts any object that structurally satisfies TaxomeshRepositoryBase at
    construction time. No inheritance from TaxomeshRepositoryBase is required.

    When no repository is provided the service resolves a storage backend from
    configuration: it reads ``taxomesh.toml`` at ``config_path`` (if given) or
    auto-discovers it from the current working directory. If no config file is
    found it falls back to ``YAMLRepository`` with its built-in default path.

    Args:
        repository: Explicit storage backend. When provided, ``config_path`` is
            ignored entirely.
        config_path: Path to a ``taxomesh.toml`` file. When ``None`` the service
            looks for ``taxomesh.toml`` in the current working directory.
            Ignored when ``repository`` is provided.
    """

    def __init__(
        self,
        repository: TaxomeshRepositoryBase | None = None,
        *,
        config_path: Path | str | None = None,
    ) -> None:
        """Initialise the service with a storage backend.

        Args:
            repository: Explicit storage backend. When provided, ``config_path``
                is ignored entirely.
            config_path: Path to a ``taxomesh.toml`` file. When ``None`` the
                service looks for ``taxomesh.toml`` in the current working
                directory. Ignored when ``repository`` is provided.

        Raises:
            TaxomeshConfigError: If the config file exists but cannot be parsed
                or specifies an unsupported repository type.
            TaxomeshRepositoryError: If the repository adapter fails to initialise.
        """
        self._config_name: str | None = None
        if repository is None:
            resolved = Path(config_path) if config_path is not None else Path.cwd() / _DEFAULT_CONFIG_FILENAME
            if resolved.exists():
                try:
                    raw = tomllib.loads(resolved.read_text(encoding="utf-8"))
                except tomllib.TOMLDecodeError as exc:
                    raise TaxomeshConfigError(f"Could not parse config file {resolved}: {exc}") from exc
                except OSError as exc:
                    raise TaxomeshConfigError(f"Could not read config file {resolved}: {exc}") from exc
                self._config_name = raw.get("taxomesh", {}).get("name")
                self._repo: TaxomeshRepositoryBase = self._build_repo_from_config(raw, resolved)
            else:
                from taxomesh.adapters.repositories.yaml_repository import YAMLRepository  # noqa: PLC0415

                self._repo = YAMLRepository()
        else:
            self._repo = repository
        self._root_id: UUID = self._ensure_root()
        self._item_corpus: list[SearchCandidate[Item]] | None = None
        self._category_corpus: list[SearchCandidate[Category]] | None = None

    @property
    def repository(self) -> TaxomeshRepositoryBase:
        """Return the active storage backend."""
        return self._repo

    def get_debug(self) -> dict[str, Any]:
        """Return diagnostic information about this taxomesh installation.

        Returns:
            Dict with keys: version, config_name, repository_type,
            working_path, repository_info, item_corpus_size, and
            category_corpus_size. Corpus size keys are ``None`` when the
            respective corpus has not been built yet or has been invalidated.
        """
        import importlib.metadata  # noqa: PLC0415

        try:
            version: str = importlib.metadata.version("taxomesh")
        except importlib.metadata.PackageNotFoundError:
            version = "unknown"
        repo_info = self._repo.get_debug_info()
        working_path: str | None = repo_info.get("path")
        return {
            "version": version,
            "config_name": self._config_name,
            "repository_type": type(self._repo).__name__,
            "working_path": working_path,
            "repository_info": repo_info,
            "item_corpus_size": len(self._item_corpus) if self._item_corpus is not None else None,
            "category_corpus_size": len(self._category_corpus) if self._category_corpus is not None else None,
        }

    @staticmethod
    def _build_repo_from_config(config: dict[str, Any], config_path: Path) -> TaxomeshRepositoryBase:
        """Construct a repository adapter from a parsed taxomesh.toml config dict.

        Args:
            config: Parsed TOML document as a dict.
            config_path: Resolved path to the config file (used in error messages).

        Returns:
            A repository adapter matching the ``[repository]`` section settings.

        Raises:
            TaxomeshConfigError: If ``type`` is not a supported value.
            TaxomeshRepositoryError: If the adapter fails to initialise.
        """
        from taxomesh.adapters.repositories.django_repository import DJANGO_REPO_TYPE  # noqa: PLC0415
        from taxomesh.adapters.repositories.json_repository import JSON_REPO_TYPE, JsonRepository  # noqa: PLC0415
        from taxomesh.adapters.repositories.yaml_repository import YAML_REPO_TYPE, YAMLRepository  # noqa: PLC0415

        def _build_yaml(section: dict[str, Any]) -> TaxomeshRepositoryBase:
            return YAMLRepository(Path(section["path"])) if "path" in section else YAMLRepository()

        def _build_json(section: dict[str, Any]) -> TaxomeshRepositoryBase:
            return JsonRepository(Path(section["path"])) if "path" in section else JsonRepository()

        def _build_django(section: dict[str, Any]) -> TaxomeshRepositoryBase:
            from taxomesh.adapters.repositories.django_repository import (  # noqa: PLC0415
                _USING_DEFAULT as _DJANGO_USING_DEFAULT,
            )
            from taxomesh.adapters.repositories.django_repository import (  # noqa: PLC0415
                DjangoRepository,
            )

            using: str = section.get("using", _DJANGO_USING_DEFAULT)
            return DjangoRepository(using=using)

        _REPO_BUILDERS: dict[str, Callable[[dict[str, Any]], TaxomeshRepositoryBase]] = {
            YAML_REPO_TYPE: _build_yaml,
            JSON_REPO_TYPE: _build_json,
            DJANGO_REPO_TYPE: _build_django,
        }

        section = config.get("repository", {})
        repo_type: str = section.get("type", YAML_REPO_TYPE)
        builder = _REPO_BUILDERS.get(repo_type)
        if builder is None:
            supported = ", ".join(f"'{k}'" for k in _REPO_BUILDERS)
            raise TaxomeshConfigError(
                f"Unsupported repository type '{repo_type}' in {config_path}. Supported: {supported}."
            )
        return builder(section)

    def _ensure_root(self) -> UUID:
        """Guarantee the reserved root category exists and return its UUID.

        Scans the repository for an existing root category. Creates one if absent.
        Called once at the end of ``__init__``.
        """
        for cat in self._repo.list_categories(enabled=None):
            if cat.name == ROOT_CATEGORY_NAME:
                return cat.category_id
        root = Category(category_id=uuid4(), name=ROOT_CATEGORY_NAME)
        self._repo.save_category(root)
        return root.category_id

    # ------------------------------------------------------------------
    # Category
    # ------------------------------------------------------------------

    def create_category(
        self,
        name: str,
        description: str = "",
        metadata: dict[str, Any] | None = None,
        slug: str = "",
        external_id: str | None = None,
    ) -> Category:
        """Create a new category and persist it.

        Args:
            name: Category name; max 256 characters.
            description: Optional description; max 100 000 characters. Defaults to "".
            metadata: Optional arbitrary key-value pairs; defaults to {}.
            slug: Optional URL-friendly identifier; must be unique when non-empty. Defaults to "".
            external_id: Optional external identifier. Defaults to None (no external reference).

        Returns:
            The newly created Category with a library-assigned UUID.

        Raises:
            TaxomeshDuplicateSlugError: If slug is non-empty and already used by another category.
        """
        if name == ROOT_CATEGORY_NAME:
            raise TaxomeshRootCategoryError(f"Category name '{ROOT_CATEGORY_NAME}' is reserved")
        if slug:
            existing = self._repo.get_category_by_slug(slug)
            if existing is not None:
                raise TaxomeshDuplicateSlugError(f"Slug '{slug}' is already in use")
        now = datetime.now(tz=UTC)
        category = Category(
            category_id=uuid4(),
            name=name,
            description=description,
            slug=slug,
            metadata=metadata if metadata is not None else {},
            external_id=external_id,
            created_at=now,
            updated_at=now,
        )
        self._repo.save_category(category)
        self._repo.save_category_parent_link(
            CategoryParentLink(category_id=category.category_id, parent_category_id=self._root_id, sort_index=0)
        )
        clear_all_caches()
        self._category_corpus = None
        return category

    @memoize(DEFAULT_CACHE_TTL)
    def get_category(self, category_id: UUID) -> Category:
        """Retrieve a category by its identifier.

        Args:
            category_id: The library-assigned UUID of the category.

        Returns:
            The matching Category.

        Raises:
            TaxomeshCategoryNotFoundError: If no category with the given id exists.
        """
        result = self._repo.get_category(category_id)
        if result is None:
            raise TaxomeshCategoryNotFoundError(f"Category not found: {category_id}")
        return result

    @memoize(DEFAULT_CACHE_TTL)
    def list_categories(
        self,
        *,
        parent_id: UUID | None = None,
        external_id: str | None = None,
        enabled: bool | None = True,
    ) -> list[Category]:
        """Return stored categories, optionally filtered by parent, external_id, and/or enabled.

        Args:
            parent_id: When provided, returns child categories of this parent
                ordered by sort_index. When None, returns all root-level categories.
            external_id: When provided, returns the single category with this external_id
                (at most one, since external_id is unique). The root category is never
                returned. When both parent_id and external_id are given, returns the
                intersection (0 or 1 element; unsorted).
            enabled: True (default) returns only enabled categories; False
                returns only disabled; None returns all regardless of enabled state.

        Returns:
            List of categories. When filtering by external_id only, contains at most one
            element and is not sorted. When filtering by parent_id only, ordered by
            sort_index.

        Raises:
            TaxomeshCategoryNotFoundError: If parent_id is provided but not found.
        """
        if external_id is not None:
            cat = self._repo.get_category_by_external_id(external_id)
            results: list[Category] = []
            if cat is not None and cat.category_id != self._root_id:
                results = [cat]
            if enabled is not None:
                results = [c for c in results if c.enabled == enabled]
            if parent_id is not None:
                self.get_category(parent_id)
                child_ids = {
                    lnk.category_id
                    for lnk in self._repo.list_category_parent_links()
                    if lnk.parent_category_id == parent_id
                }
                results = [c for c in results if c.category_id in child_ids]
            return results
        if parent_id is None:
            parent_id = self._root_id
        else:
            self.get_category(parent_id)
        links = sorted(
            [lnk for lnk in self._repo.list_category_parent_links() if lnk.parent_category_id == parent_id],
            key=lambda lnk: lnk.sort_index,
        )
        cats = [self.get_category(lnk.category_id) for lnk in links]
        if enabled is not None:
            cats = [c for c in cats if c.enabled == enabled]
        return cats

    def delete_category(self, category_id: UUID) -> None:
        """Delete a category by its identifier.

        Args:
            category_id: The library-assigned UUID of the category to delete.

        Raises:
            TaxomeshCategoryNotFoundError: If no category with the given id exists.
        """
        if category_id == self._root_id:
            raise TaxomeshRootCategoryError("Cannot delete the root category")
        found = self._repo.delete_category(category_id)
        if not found:
            raise TaxomeshCategoryNotFoundError(f"Category not found: {category_id}")
        clear_all_caches()
        self._category_corpus = None

    @memoize(DEFAULT_CACHE_TTL)
    def get_category_by_slug(self, slug: str) -> Category:
        """Retrieve a category by its slug.

        Args:
            slug: The URL-friendly identifier of the category.

        Returns:
            The matching Category.

        Raises:
            TaxomeshCategoryNotFoundError: If no category with the given slug exists.
        """
        result = self._repo.get_category_by_slug(slug)
        if result is None or result.category_id == self._root_id:
            raise TaxomeshCategoryNotFoundError(f"Category not found for slug: {slug!r}")
        return result

    def update_category(  # noqa: PLR0913
        self,
        category_id: UUID,
        name: str | None = None,
        description: str | None = None,
        slug: str | None = None,
        metadata: dict[str, Any] | None = None,
        external_id: str | None | _UnsetType = _UNSET,
        enabled: bool | None = None,
    ) -> Category:
        """Update a category's name, description, slug, external_id, enabled, and/or metadata.

        Args:
            category_id: The library-assigned UUID of the category to update.
            name: New name; unchanged if None.
            description: New description; unchanged if None.
            slug: New slug; unchanged if None. Pass "" to clear the slug.
            metadata: New metadata dict; unchanged if None.
            external_id: New external_id; pass None to clear the field; omit to leave unchanged.
            enabled: New enabled state; unchanged if None.

        Returns:
            The updated Category.

        Raises:
            TaxomeshCategoryNotFoundError: If no category with the given id exists.
            TaxomeshDuplicateSlugError: If slug is non-empty and already used by another category.
        """
        if category_id == self._root_id:
            raise TaxomeshRootCategoryError("Cannot update the root category")
        category = self.get_category(category_id)
        if slug is not None and slug:
            existing = self._repo.get_category_by_slug(slug)
            if existing is not None and existing.category_id != category_id:
                raise TaxomeshDuplicateSlugError(f"Slug '{slug}' is already in use")
        if name is not None:
            category.name = name
        if description is not None:
            category.description = description
        if slug is not None:
            category.slug = slug
        if metadata is not None:
            category.metadata = metadata
        if not isinstance(external_id, _UnsetType):
            category.external_id = external_id
        if enabled is not None:
            category.enabled = enabled
        now = datetime.now(tz=UTC)
        category.updated_at = now
        self._repo.save_category(category)
        clear_all_caches()
        self._category_corpus = None
        return category

    # ------------------------------------------------------------------
    # Item
    # ------------------------------------------------------------------

    def create_item(
        self,
        name: str,
        external_id: ExternalId = DEFAULT_ITEM_EXTERNAL_ID,
        metadata: dict[str, Any] | None = None,
        slug: str = "",
    ) -> Item:
        """Create a new item and persist it.

        Args:
            name: Human-readable item name; max 256 characters.
            external_id: Optional caller-provided identifier linking this item to an external
                entity. May be a UUID, a string (max 256 chars), or an int. Defaults to None
                (no external reference).
            metadata: Optional arbitrary key-value pairs; defaults to {}.
            slug: Optional URL-friendly identifier; must be unique when non-empty. Defaults to "".

        Returns:
            The newly created Item with a library-assigned internal UUID.

        Raises:
            TaxomeshDuplicateSlugError: If slug is non-empty and already used by another item.
        """
        if slug:
            existing = self._repo.get_item_by_slug(slug)
            if existing is not None:
                raise TaxomeshDuplicateSlugError(f"Slug '{slug}' is already in use")
        now = datetime.now(tz=UTC)
        item = Item(
            name=name,
            external_id=None if external_id is None else str(external_id),
            slug=slug,
            metadata=metadata if metadata is not None else {},
            created_at=now,
            updated_at=now,
        )
        self._repo.save_item(item)
        clear_all_caches()
        self._item_corpus = None
        return item

    @memoize(DEFAULT_CACHE_TTL)
    def get_item(self, item_id: UUID) -> Item:
        """Retrieve an item by its internal identifier.

        Args:
            item_id: The library-assigned UUID of the item.

        Returns:
            The matching Item.

        Raises:
            TaxomeshItemNotFoundError: If no item with the given id exists.
        """
        result = self._repo.get_item(item_id)
        if result is None:
            raise TaxomeshItemNotFoundError(f"Item not found: {item_id}")
        return result

    @memoize(DEFAULT_CACHE_TTL)
    def list_items(self, *, category_id: UUID | None = None, enabled: bool | None = True) -> list[Item]:
        """Return stored items, optionally filtered by category and/or enabled state.

        Args:
            category_id: When provided, returns items placed in this category
                ordered by sort_index. When None, returns all items.
            enabled: True (default) returns only enabled items; False
                returns only disabled; None returns all regardless of enabled state.

        Returns:
            List of items.

        Raises:
            TaxomeshCategoryNotFoundError: If category_id is provided but not found.
        """
        if category_id is None:
            return self._repo.list_items(enabled=enabled)
        self.get_category(category_id)
        links = sorted(
            self._repo.list_item_parent_links(category_ids=[category_id]),
            key=lambda lnk: lnk.sort_index,
        )
        items = [self.get_item(lnk.item_id) for lnk in links]
        if enabled is not None:
            items = [i for i in items if i.enabled == enabled]
        return items

    @memoize(DEFAULT_CACHE_TTL)
    def list_categories_by_item(self, item_id: UUID, *, enabled: bool | None = True) -> list[Category]:
        """Return the categories in which the given item has an active placement.

        Categories are returned in ascending sort_index order (the order defined
        by item-to-category placement links).

        Args:
            item_id: The library-assigned UUID of the item.
            enabled: True (default) returns only enabled categories; False
                returns only disabled; None returns all regardless of enabled state.

        Returns:
            List of Category objects ordered by ItemParentLink.sort_index ascending.
            Returns an empty list when the item has no placements (or none match the
            enabled filter).

        Raises:
            TaxomeshItemNotFoundError: If no item with the given item_id exists.

        Example:

            cats = svc.list_categories_by_item(album.item_id)
            # [Category(name="Jazz", ...), Category(name="Music", ...)]
            # — ordered by sort_index assigned at placement time
        """
        self.get_item(item_id)
        links = sorted(
            self._repo.list_item_parent_links(item_id=item_id),
            key=lambda lnk: lnk.sort_index,
        )
        cats = [self.get_category(lnk.category_id) for lnk in links]
        if enabled is not None:
            cats = [c for c in cats if c.enabled == enabled]
        return cats

    def delete_item(self, item_id: UUID) -> None:
        """Delete an item by its internal identifier.

        Args:
            item_id: The library-assigned UUID of the item to delete.

        Raises:
            TaxomeshItemNotFoundError: If no item with the given id exists.
        """
        found = self._repo.delete_item(item_id)
        if not found:
            raise TaxomeshItemNotFoundError(f"Item not found: {item_id}")
        clear_all_caches()
        self._item_corpus = None

    @memoize(DEFAULT_CACHE_TTL)
    def get_item_by_slug(self, slug: str) -> Item:
        """Retrieve an item by its slug.

        Args:
            slug: The URL-friendly identifier of the item.

        Returns:
            The matching Item.

        Raises:
            TaxomeshItemNotFoundError: If no item with the given slug exists.
        """
        result = self._repo.get_item_by_slug(slug)
        if result is None:
            raise TaxomeshItemNotFoundError(f"Item not found for slug: {slug!r}")
        return result

    def update_item(
        self,
        item_id: UUID,
        enabled: bool | None = None,
        slug: str | None = None,
        name: str | None = None,
        external_id: str | None | _UnsetType = _UNSET,
        metadata: dict[str, Any] | None = None,
    ) -> Item:
        """Update an item's enabled state, slug, name, external_id, and/or metadata.

        Args:
            item_id: The library-assigned UUID of the item to update.
            enabled: New enabled state; unchanged if None.
            slug: New slug; unchanged if None. Pass "" to clear the slug.
            name: New name; unchanged if None.
            external_id: New external identifier; pass None to clear the field; omit to leave unchanged.
            metadata: New metadata dict; unchanged if None.

        Returns:
            The updated Item.

        Raises:
            TaxomeshItemNotFoundError: If no item with the given id exists.
            TaxomeshDuplicateSlugError: If slug is non-empty and already used by another item.
        """
        item = self.get_item(item_id)
        if slug is not None and slug:
            existing = self._repo.get_item_by_slug(slug)
            if existing is not None and existing.item_id != item_id:
                raise TaxomeshDuplicateSlugError(f"Slug '{slug}' is already in use")
        if enabled is not None:
            item.enabled = enabled
        if slug is not None:
            item.slug = slug
        if name is not None:
            item.name = name
        if not isinstance(external_id, _UnsetType):
            item.external_id = external_id
        if metadata is not None:
            item.metadata = metadata
        now = datetime.now(tz=UTC)
        item.updated_at = now
        self._repo.save_item(item)
        clear_all_caches()
        self._item_corpus = None
        return item

    # ------------------------------------------------------------------
    # Tag
    # ------------------------------------------------------------------

    def create_tag(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> Tag:
        """Create a new tag and persist it.

        Args:
            name: Tag name; max 25 characters.
            metadata: Optional arbitrary key-value pairs; defaults to {}.

        Returns:
            The newly created Tag with a library-assigned UUID.
        """
        tag = Tag(
            tag_id=uuid4(),
            name=name,
            metadata=metadata if metadata is not None else {},
        )
        self._repo.save_tag(tag)
        clear_all_caches()
        return tag

    @memoize(DEFAULT_CACHE_TTL)
    def list_tags(self) -> list[Tag]:
        """Return all stored tags.

        Returns:
            List of all tags; empty list if none exist.
        """
        return self._repo.list_tags()

    def update_tag(self, tag_id: UUID, name: str | None = None) -> Tag:
        """Update a tag's name.

        Args:
            tag_id: The library-assigned UUID of the tag to update.
            name: New name; unchanged if None.

        Returns:
            The updated Tag.

        Raises:
            TaxomeshTagNotFoundError: If no tag with the given id exists.
        """
        result = self._repo.get_tag(tag_id)
        if result is None:
            raise TaxomeshTagNotFoundError(f"Tag not found: {tag_id}")
        if name is not None:
            result.name = name
        self._repo.save_tag(result)
        clear_all_caches()
        return result

    def delete_tag(self, tag_id: UUID) -> None:
        """Delete a tag by its identifier.

        Args:
            tag_id: The library-assigned UUID of the tag to delete.

        Raises:
            TaxomeshTagNotFoundError: If no tag with the given id exists.
        """
        found = self._repo.delete_tag(tag_id)
        if not found:
            raise TaxomeshTagNotFoundError(f"Tag not found: {tag_id}")
        clear_all_caches()

    def assign_tag(self, tag_id: UUID, item_id: UUID) -> None:
        """Associate a tag with an item. Idempotent.

        Validates that both the tag and the item exist before delegating to
        the repository. Tag existence is validated before item existence.

        Args:
            tag_id: The library-assigned UUID of the tag.
            item_id: The library-assigned UUID of the item.

        Raises:
            TaxomeshTagNotFoundError: If no tag with the given tag_id exists.
            TaxomeshItemNotFoundError: If no item with the given item_id exists.
        """
        if self._repo.get_tag(tag_id) is None:
            raise TaxomeshTagNotFoundError(f"Tag not found: {tag_id}")
        if self._repo.get_item(item_id) is None:
            raise TaxomeshItemNotFoundError(f"Item not found: {item_id}")
        self._repo.assign_tag(tag_id, item_id)
        clear_all_caches()

    def add_category_parent(
        self,
        category_id: UUID,
        parent_id: UUID,
        sort_index: int = 0,
    ) -> CategoryParentLink:
        """Add a parent relationship between two categories, enforcing DAG integrity.

        Idempotent — calling with the same (category_id, parent_id) pair updates
        sort_index if changed, without creating a duplicate link.

        Validates that both categories exist, then delegates cycle detection to
        the domain layer before persisting the link.

        Args:
            category_id: The child category's UUID.
            parent_id: The parent category's UUID.
            sort_index: Sort position among this category's parents; defaults to 0.

        Returns:
            The created CategoryParentLink.

        Raises:
            TaxomeshCategoryNotFoundError: If either category does not exist.
            TaxomeshCyclicDependencyError: If the relationship would create a cycle.
        """
        if category_id == self._root_id:
            raise TaxomeshRootCategoryError("Cannot add a parent to the root category")
        if category_id == parent_id:
            raise TaxomeshCyclicDependencyError(f"Category {category_id} cannot be its own parent.")
        if self._repo.get_category(category_id) is None:
            raise TaxomeshCategoryNotFoundError(f"Category not found: {category_id}")
        if self._repo.get_category(parent_id) is None:
            raise TaxomeshCategoryNotFoundError(f"Category not found: {parent_id}")
        check_no_cycle(category_id, parent_id, self._repo.list_category_parent_links())
        link = CategoryParentLink(
            category_id=category_id,
            parent_category_id=parent_id,
            sort_index=sort_index,
        )
        self._repo.save_category_parent_link(link)
        clear_all_caches()
        return link

    @memoize(DEFAULT_CACHE_TTL)
    def get_graph(self, *, enabled: bool | None = True) -> TaxomeshGraph:
        """Build and return a full taxonomy snapshot.

        Reads all categories (excluding the internal root), all category-parent
        relationships, and all item placements from the configured repository.
        Constructs a tree of CategoryNode instances rooted at the implicit
        taxonomy root.

        Args:
            enabled: True (default) includes only enabled categories and items;
                False includes only disabled; None includes all regardless of state.

        Returns:
            A TaxomeshGraph snapshot. Returns a graph with an empty roots list
            when no user-created categories exist.

        Raises:
            TaxomeshRepositoryError: If the underlying repository fails during read.
        """
        all_cats = {
            c.category_id: c for c in self._repo.list_categories(enabled=enabled) if c.category_id != self._root_id
        }
        all_links = self._repo.list_category_parent_links()

        # Filter links to only include categories present in all_cats (respects enabled filter)
        explicit_links = [
            lnk
            for lnk in all_links
            if lnk.parent_category_id != self._root_id
            and lnk.category_id in all_cats
            and lnk.parent_category_id in all_cats
        ]
        root_child_links = [
            lnk for lnk in all_links if lnk.parent_category_id == self._root_id and lnk.category_id in all_cats
        ]
        root_sort = {lnk.category_id: lnk.sort_index for lnk in root_child_links}

        explicitly_parented = {lnk.category_id for lnk in explicit_links}
        top_level_ids = {cid for cid in root_sort if cid not in explicitly_parented}

        children_by_parent: dict[UUID, list[tuple[int, UUID]]] = {}
        for lnk in explicit_links:
            children_by_parent.setdefault(lnk.parent_category_id, []).append((lnk.sort_index, lnk.category_id))
        for bucket in children_by_parent.values():
            bucket.sort(key=lambda t: t[0])

        item_links = self._repo.list_item_parent_links()
        items_map = {i.item_id: i for i in self._repo.list_items(enabled=enabled)}
        items_pairs_by_cat: dict[UUID, list[tuple[int, Item]]] = {}
        for ilnk in item_links:
            if ilnk.item_id in items_map:
                items_pairs_by_cat.setdefault(ilnk.category_id, []).append((ilnk.sort_index, items_map[ilnk.item_id]))
        sorted_items_by_cat: dict[UUID, list[Item]] = {
            cid: [item for _, item in sorted(pairs, key=lambda t: t[0])] for cid, pairs in items_pairs_by_cat.items()
        }

        def _build_node(cat_id: UUID) -> CategoryNode:
            items = sorted_items_by_cat.get(cat_id, [])
            children = [_build_node(cid) for _, cid in children_by_parent.get(cat_id, [])]
            return CategoryNode(category=all_cats[cat_id], items=items, children=children)

        roots = [_build_node(cid) for cid in sorted(top_level_ids, key=lambda cid: root_sort[cid])]
        return TaxomeshGraph(roots=roots)

    def place_item_in_category(
        self,
        item_id: UUID,
        category_id: UUID,
        sort_index: int = 0,
    ) -> ItemParentLink:
        """Place an item in a category. Idempotent — updates sort_index if already placed.

        Args:
            item_id: The library-assigned UUID of the item.
            category_id: The library-assigned UUID of the category.
            sort_index: Sort position within the category; defaults to 0.

        Returns:
            The resulting ItemParentLink.

        Raises:
            TaxomeshItemNotFoundError: If no item with the given id exists.
            TaxomeshCategoryNotFoundError: If no category with the given id exists.
        """
        self.get_item(item_id)
        self.get_category(category_id)
        link = ItemParentLink(item_id=item_id, category_id=category_id, sort_index=sort_index)
        self._repo.save_item_parent_link(link)
        clear_all_caches()
        return link

    def remove_tag(self, tag_id: UUID, item_id: UUID) -> None:
        """Remove the association between a tag and an item. No-op if not linked.

        Validates that both the tag and the item exist before delegating to
        the repository. Tag existence is validated before item existence.

        Args:
            tag_id: The library-assigned UUID of the tag.
            item_id: The library-assigned UUID of the item.

        Raises:
            TaxomeshTagNotFoundError: If no tag with the given tag_id exists.
            TaxomeshItemNotFoundError: If no item with the given item_id exists.
        """
        if self._repo.get_tag(tag_id) is None:
            raise TaxomeshTagNotFoundError(f"Tag not found: {tag_id}")
        if self._repo.get_item(item_id) is None:
            raise TaxomeshItemNotFoundError(f"Item not found: {item_id}")
        self._repo.remove_tag(tag_id, item_id)
        clear_all_caches()

    # ------------------------------------------------------------------
    # External-ID lookup
    # ------------------------------------------------------------------

    @memoize(DEFAULT_CACHE_TTL)
    def get_item_by_external_id(self, external_id: ExternalId) -> Item | None:
        """Return the item with the given external_id, or None.

        Returns None immediately if external_id is None (no repository call).
        UUID and int inputs are coerced to str before lookup.

        Args:
            external_id: The external identifier to look up — UUID, int, str, or None.

        Returns:
            The matching Item, or None if not found or external_id is None.

        Raises:
            TaxomeshRepositoryError: If the underlying repository raises it.
        """
        if external_id is None:
            return None
        return self._repo.get_item_by_external_id(str(external_id))

    @memoize(DEFAULT_CACHE_TTL)
    def get_category_by_external_id(self, external_id: ExternalId) -> Category | None:
        """Return the category with the given external_id, or None.

        Returns None immediately if external_id is None (no repository call).
        UUID and int inputs are coerced to str before lookup.
        Root category is always excluded from results.

        Args:
            external_id: The external identifier to look up — UUID, int, str, or None.

        Returns:
            The matching non-root Category, or None if not found or external_id is None.

        Raises:
            TaxomeshRepositoryError: If the underlying repository raises it.
        """
        if external_id is None:
            return None
        cat = self._repo.get_category_by_external_id(str(external_id))
        if cat is None or cat.category_id == self._root_id:
            return None
        return cat

    def get_items_by_external_ids(
        self,
        external_ids: Iterable[str],
        *,
        enabled: bool | None = None,
    ) -> dict[str, Item]:
        """Resolve multiple items by their external_id in a single bulk operation.

        Normalises each input with ``str(value).strip()``, ignores blank values,
        deduplicates into a ``frozenset``, then delegates to the memoized
        implementation. Returns only found items; missing or disabled IDs are
        silently omitted.

        Args:
            external_ids: An iterable of external ID strings. Generators supported.
            enabled: ``True`` returns only enabled items; ``False`` only disabled;
                ``None`` (default) returns all matching items regardless of enabled state.

        Returns:
            A dict mapping each found external_id (after normalisation) to its Item.

        Raises:
            TaxomeshRepositoryError: If the underlying repository raises it.
        """
        normalised = _normalise_external_ids(external_ids)
        if not normalised:
            return {}
        return self._fetch_items_by_external_ids(normalised, enabled=enabled)

    @memoize(DEFAULT_CACHE_TTL)
    def _fetch_items_by_external_ids(
        self,
        external_ids: frozenset[str],
        *,
        enabled: bool | None = None,
    ) -> dict[str, Item]:
        """Memoized bulk repository call. frozenset arg → hashable cache key."""
        return self._repo.get_items_by_external_ids(external_ids, enabled=enabled)

    def get_categories_by_external_ids(
        self,
        external_ids: Iterable[str],
        *,
        enabled: bool | None = None,
    ) -> dict[str, Category]:
        """Resolve multiple categories by their external_id in a single bulk operation.

        Normalises each input with ``str(value).strip()``, ignores blank values,
        deduplicates into a ``frozenset``, then delegates to the memoized
        implementation. The root category is always excluded from results.

        Args:
            external_ids: An iterable of external ID strings. Generators supported.
            enabled: ``True`` returns only enabled categories; ``False`` only disabled;
                ``None`` (default) returns all matching categories regardless of enabled state.

        Returns:
            A dict mapping each found external_id (after normalisation) to its Category.
            The root category is never included even if its external_id matches.

        Raises:
            TaxomeshRepositoryError: If the underlying repository raises it.
        """
        normalised = _normalise_external_ids(external_ids)
        if not normalised:
            return {}
        result = self._fetch_categories_by_external_ids(normalised, enabled=enabled)
        return {k: v for k, v in result.items() if v.category_id != self._root_id}

    @memoize(DEFAULT_CACHE_TTL)
    def _fetch_categories_by_external_ids(
        self,
        external_ids: frozenset[str],
        *,
        enabled: bool | None = None,
    ) -> dict[str, Category]:
        """Memoized bulk repository call. frozenset arg → hashable cache key."""
        return self._repo.get_categories_by_external_ids(external_ids, enabled=enabled)

    def remove_category_parent(self, category_id: UUID, parent_id: UUID) -> None:
        """Remove a parent relationship from a category. No-op if the link does not exist.

        Args:
            category_id: The child category's UUID.
            parent_id: The parent category's UUID.

        Raises:
            TaxomeshCategoryNotFoundError: If either category does not exist.
        """
        if self._repo.get_category(category_id) is None:
            raise TaxomeshCategoryNotFoundError(f"Category not found: {category_id}")
        if self._repo.get_category(parent_id) is None:
            raise TaxomeshCategoryNotFoundError(f"Category not found: {parent_id}")
        self._repo.delete_category_parent_link(category_id, parent_id)
        clear_all_caches()

    # ------------------------------------------------------------------
    # Item relations
    # ------------------------------------------------------------------

    def relate_items(
        self,
        source_item_id: UUID,
        target_item_id: UUID,
        relation_type: str,
        sort_index: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> ItemRelationLink:
        """Create or update a directed typed relation between two items.

        Upsert semantics: if a relation with the same
        ``(source_item_id, target_item_id, relation_type)`` triple already
        exists its ``sort_index`` and ``metadata`` are updated in-place.

        Args:
            source_item_id: UUID of the source item.
            target_item_id: UUID of the target item.
            relation_type: Human-readable relation label (e.g. ``"covers"``).
                Case is normalised to lowercase.
            sort_index: Sort position; defaults to 0.
            metadata: Optional arbitrary key-value pairs; defaults to ``{}``.

        Returns:
            The created or updated ItemRelationLink.

        Raises:
            TaxomeshItemNotFoundError: If either item does not exist.
            TaxomeshRelationError: If ``source_item_id == target_item_id``
                or ``relation_type`` is empty / whitespace-only.
        """
        self.get_item(source_item_id)
        self.get_item(target_item_id)
        link = ItemRelationLink(
            source_item_id=source_item_id,
            target_item_id=target_item_id,
            relation_type=relation_type,
            sort_index=sort_index,
            metadata=metadata if metadata is not None else {},
        )
        self._repo.save_item_relation_link(link)
        clear_all_caches()
        return link

    @memoize(DEFAULT_CACHE_TTL)
    def list_item_relations(
        self,
        item_id: UUID,
        *,
        relation_type: str | None = None,
        direction: Literal["outgoing", "incoming", "both"] = "outgoing",
    ) -> list[ItemRelationLink]:
        """Return relation links for the given item.

        Args:
            item_id: The UUID of the item to query.
            relation_type: Optional filter; case-insensitive. When provided
                only links whose normalised type matches are returned.
            direction: ``"outgoing"`` (default) returns links where this item
                is the source; ``"incoming"`` returns links where it is the
                target; ``"both"`` returns links where this item is either the
                source or the target, each link at most once. Note that a
                bidirectional relation persisted as two separate rows
                (``A --rel--> B`` and ``B --rel--> A``) yields two distinct
                links under ``"both"`` when queried for ``A`` — one outgoing,
                one incoming — because they are genuinely distinct directed
                edges. Relation type values are opaque to taxomesh: callers
                define their own vocabulary.

        Returns:
            List of matching ItemRelationLink objects; empty list if none match.
        """
        normalised_type = relation_type.strip().lower() if relation_type is not None else None
        return self._repo.list_item_relation_links(item_id, relation_type=normalised_type, direction=direction)

    @memoize(DEFAULT_CACHE_TTL)
    def list_related_items(
        self,
        item_id: UUID,
        *,
        relation_type: str | None = None,
        direction: Literal["outgoing", "incoming", "both"] = "outgoing",
    ) -> list[Item]:
        """Return the items reachable via relations from/to the given item.

        Related items are resolved through one bulk repository lookup (not one
        query per link), regardless of enabled state — matching the per-item
        :meth:`get_item` semantics this method previously relied on.

        Args:
            item_id: The UUID of the item to query.
            relation_type: Optional filter; case-insensitive.
            direction: ``"outgoing"`` (default) returns targets; ``"incoming"``
                returns sources; ``"both"`` returns the *other* endpoint of
                every link touching ``item_id`` (the target of outgoing links
                and the source of incoming links), in link order.

        Returns:
            List of related Item objects in link order; empty list if none match.

        Raises:
            TaxomeshItemNotFoundError: If a related item referenced by a link
                does not exist in the repository.
        """
        links = self.list_item_relations(item_id, relation_type=relation_type, direction=direction)
        if direction == "outgoing":
            ordered_ids = [lnk.target_item_id for lnk in links]
        elif direction == "incoming":
            ordered_ids = [lnk.source_item_id for lnk in links]
        else:  # "both" — return the endpoint that is not item_id
            ordered_ids = [
                lnk.target_item_id if lnk.source_item_id == item_id else lnk.source_item_id for lnk in links
            ]
        if not ordered_ids:
            return []
        item_map = self._repo.get_items_by_ids(set(ordered_ids), enabled=None)
        result: list[Item] = []
        for needed_id in ordered_ids:
            found = item_map.get(needed_id)
            if found is None:
                raise TaxomeshItemNotFoundError(f"Item not found: {needed_id}")
            result.append(found)
        return result

    def list_related_items_for_sources(
        self,
        source_item_ids: Collection[UUID],
        *,
        relation_types: Collection[str] | None = None,
        skip_on_error: bool = True,
        direction: Literal["outgoing", "incoming", "both"] = "outgoing",
    ) -> dict[UUID, dict[str, list[Item]]]:
        """Return related items grouped by queried item ID and relation type.

        Resolves the relations of every item in *source_item_ids* in exactly
        **two repository calls** — one batched link query
        (:meth:`~taxomesh.ports.repository.TaxomeshRepositoryBase.list_item_relation_links_for_items`)
        plus one bulk item lookup restricted to the endpoints of the matched
        links — for **every** direction, including ``"both"`` (which uses a single
        combined ``source OR target`` query rather than two). This eliminates the
        N+1 pattern of calling :meth:`list_related_items` in a loop.

        The call count is constant regardless of how many ids are passed (it never
        degrades to a per-item query). Relation type strings are
        normalised to lower-case before filtering so callers may pass ``"Covers"``
        or ``"COVERS"`` freely.

        Despite the historical ``source_item_ids`` / ``..._for_sources`` naming,
        the ids are the **queried** items, interpreted per *direction*: matched on
        the source side (``"outgoing"``), the target side (``"incoming"``), or
        either side (``"both"``). The related item is the *other* endpoint of each
        matched link — the target for outgoing links, the source for incoming
        links. Queried items with no matching links (or none matching the filter)
        are **absent** from the returned dict — they are not represented as empty
        inner dicts.

        Results are served from the service read cache for ``DEFAULT_CACHE_TTL``
        seconds: calls that differ only in argument ordering, duplicates, or
        relation-type casing/whitespace share one cache entry; *direction* is part
        of the cache key, so each direction is an independent entry. Any write
        operation (or :func:`taxomesh.utils.memoize.clear_all_caches`) invalidates
        the cache. Cached results are shared object references — callers must not
        mutate the returned structures.

        Args:
            source_item_ids: Collection of queried item UUIDs.  Duplicates are
                deduplicated automatically; order is not significant.
                An empty collection returns ``{}`` immediately.
            relation_types: Optional case-insensitive allow-list.
                ``None`` or ``[]`` means no filter — all relation types are
                included.
            skip_on_error: When ``True`` (default), dangling links — where the
                related endpoint is not found in the repository — are skipped and
                a ``WARNING`` is logged identifying the queried item, the orphaned
                related item, and the ``relation_type``.  When ``False``, the
                ``TaxomeshItemNotFoundError`` is raised immediately.
            direction: ``"outgoing"`` (default) resolves the targets of the
                queried items; ``"incoming"`` resolves the sources pointing at
                them; ``"both"`` resolves the union of the two.

        Returns:
            Nested dict ``{queried_item_id: {relation_type: [Item, ...]}}``.
            Within each relation-type list, ``"outgoing"`` items appear in
            ``(sort_index ASC, target_item_id ASC)`` order, ``"incoming"`` items
            in ``(sort_index ASC, source_item_id ASC)`` order, and ``"both"``
            concatenates the outgoing-derived items first, then the
            incoming-derived items. Queried IDs with no matching links are absent.

        Raises:
            TaxomeshItemNotFoundError: If a related item referenced by any matched
                link does not exist in the repository and ``skip_on_error`` is
                ``False``.

        Example:

            song_a = service.create_item(name="Song A")
            artist = service.create_item(name="Artist X")
            service.relate_items(song_a.item_id, artist.item_id, "performed_by")

            # Outgoing: what does song_a point to?
            out = service.list_related_items_for_sources([song_a.item_id])
            # out == {song_a.item_id: {"performed_by": [artist]}}

            # Incoming: what points at artist?
            inc = service.list_related_items_for_sources(
                [artist.item_id], direction="incoming"
            )
            # inc == {artist.item_id: {"performed_by": [song_a]}}
        """
        unique_ids = frozenset(source_item_ids)
        if not unique_ids:
            return {}
        normalised_types = tuple(sorted({t.strip().lower() for t in relation_types})) if relation_types else None
        return self._fetch_related_items_for_sources(
            unique_ids, relation_types=normalised_types, skip_on_error=skip_on_error, direction=direction
        )

    @memoize(DEFAULT_CACHE_TTL)
    def _fetch_related_items_for_sources(
        self,
        source_item_ids: frozenset[UUID],
        *,
        relation_types: tuple[str, ...] | None,
        skip_on_error: bool,
        direction: Literal["outgoing", "incoming", "both"],
    ) -> dict[UUID, dict[str, list[Item]]]:
        """Memoized batch lookup. Hashable, pre-normalised args → cache key.

        Resolves all directions in a **single** batched link query
        (:meth:`list_item_relation_links_for_items`) plus one bulk item lookup —
        two repository calls total, ``"both"`` included. Each entry is
        ``(group_key_id, related_id, relation_type, sort_index, related_is_target)``
        where ``group_key_id`` is the queried endpoint (the outer dict key) and
        ``related_id`` is the endpoint to materialise. For ``"both"`` the entries
        are reordered so each group lists outgoing-derived items first, then
        incoming-derived items.
        """
        links = self._repo.list_item_relation_links_for_items(
            source_item_ids, direction=direction, relation_types=relation_types
        )
        if not links:
            return {}
        entries: list[tuple[UUID, UUID, str, int, bool]] = []
        needed_ids: set[UUID] = set()
        # One loop covers all directions. The endpoint membership check is what
        # disambiguates "both" (a link may match on either or both endpoints);
        # for "outgoing"/"incoming" the repo already filtered, so it is always true.
        for link in links:
            if direction in ("outgoing", "both") and link.source_item_id in source_item_ids:
                entries.append((link.source_item_id, link.target_item_id, link.relation_type, link.sort_index, True))
                needed_ids.update((link.source_item_id, link.target_item_id))
            if direction in ("incoming", "both") and link.target_item_id in source_item_ids:
                entries.append((link.target_item_id, link.source_item_id, link.relation_type, link.sort_index, False))
                needed_ids.update((link.target_item_id, link.source_item_id))
        if direction == "both":
            # Single OR query returns links in one order; re-sort so each
            # (group, relation_type) lists outgoing-derived items (related_is_target
            # True → sorts first) before incoming-derived ones.
            entries.sort(key=lambda e: (e[0], e[2], not e[4], e[3], e[1]))
        item_map: dict[UUID, Item] = self._repo.get_items_by_ids(needed_ids, enabled=True)
        result: dict[UUID, dict[str, list[Item]]] = {}
        for group_key_id, related_id, relation_type, _sort_index, related_is_target in entries:
            if related_id not in item_map:
                if skip_on_error:
                    if logger.isEnabledFor(logging.WARNING):
                        self._log_dangling_relation(
                            item_map, group_key_id, related_id, relation_type, related_is_target
                        )
                    continue
                raise TaxomeshItemNotFoundError(f"Item {related_id!r} referenced by relation not found")
            result.setdefault(group_key_id, {}).setdefault(relation_type, []).append(item_map[related_id])
        return result

    def _log_dangling_relation(
        self,
        item_map: dict[UUID, Item],
        present_id: UUID,
        orphan_id: UUID,
        relation_type: str,
        orphan_is_target: bool,
    ) -> None:
        """Emit the WARNING for a dangling relation skipped during batch resolution.

        *present_id* is the queried endpoint (expected to be enabled and present);
        *orphan_id* is the related endpoint that could not be materialised. Role
        labels follow the link's direction so the message stays accurate for
        outgoing, incoming, and both traversals.
        """
        present_role = "source" if orphan_is_target else "target"
        orphan_role = "target" if orphan_is_target else "source"
        present_item = item_map.get(present_id)
        if present_item is None:
            present_repr = f"<unknown {present_role} item {present_id}>"
        else:
            try:
                present_repr = str(present_item)
            except Exception:
                present_repr = f"<item {present_id} str() failed>"
        logger.warning(
            f"list_related_items_for_sources: dangling relation skipped — "
            f"{present_role}: %s, {orphan_role}: <orphaned item %s>, relation_type: %r",
            present_repr,
            orphan_id,
            relation_type,
        )

    def remove_item_relation(
        self,
        source_item_id: UUID,
        target_item_id: UUID,
        relation_type: str,
    ) -> None:
        """Remove a specific directed relation between two items.

        Args:
            source_item_id: UUID of the source item.
            target_item_id: UUID of the target item.
            relation_type: Relation label to remove (case-insensitive).

        Raises:
            TaxomeshRelationError: If the specified relation does not exist.
        """
        normalised = relation_type.strip().lower()
        found = self._repo.delete_item_relation_link(source_item_id, target_item_id, normalised)
        if not found:
            raise TaxomeshRelationError(
                f"Relation '{normalised}' from {source_item_id} to {target_item_id} does not exist"
            )
        clear_all_caches()

    def reorder_subcategories(self, parent_id: UUID, category_ids_in_order: list[UUID]) -> None:
        """Reassign sort_index values for child categories within a parent category.

        Args:
            parent_id: The UUID of the parent category whose children are being reordered.
            category_ids_in_order: All child category UUIDs in the desired final order.

        Raises:
            TaxomeshCategoryNotFoundError: If the parent category does not exist.
            ValueError: If any UUID in category_ids_in_order is not a child of parent_id.
        """
        if self._repo.get_category(parent_id) is None:
            raise TaxomeshCategoryNotFoundError(f"Category not found: {parent_id}")
        existing = {
            lnk.category_id: lnk
            for lnk in self._repo.list_category_parent_links()
            if lnk.parent_category_id == parent_id
        }
        for uid in category_ids_in_order:
            if uid not in existing:
                raise ValueError(f"Category {uid} is not a child of {parent_id}")
        for sort_index, uid in enumerate(category_ids_in_order):
            link = existing[uid]
            link.sort_index = sort_index
            self._repo.save_category_parent_link(link)
        clear_all_caches()

    def reparent_item(
        self,
        item_id: UUID,
        old_category_id: UUID,
        new_category_id: UUID,
        insert_before_uuid: UUID | None,
    ) -> ItemParentLink:
        """Move an item from one category to another, inserting at the specified position.

        Args:
            item_id: The UUID of the item to move.
            old_category_id: The UUID of the category to remove the item from.
            new_category_id: The UUID of the category to add the item to.
            insert_before_uuid: Insert the item before this sibling UUID; None appends at end.

        Returns:
            The new ItemParentLink in the destination category.

        Raises:
            TaxomeshItemNotFoundError: If the item does not exist.
            TaxomeshCategoryNotFoundError: If old or new category does not exist.
        """
        self.get_item(item_id)
        self.get_category(old_category_id)
        self.get_category(new_category_id)

        existing_siblings = sorted(
            [
                lnk
                for lnk in self._repo.list_item_parent_links()
                if lnk.category_id == new_category_id and lnk.item_id != item_id
            ],
            key=lambda lnk: lnk.sort_index,
        )

        if insert_before_uuid is None:
            insert_pos = len(existing_siblings)
        else:
            insert_pos = next(
                (i for i, lnk in enumerate(existing_siblings) if lnk.item_id == insert_before_uuid),
                len(existing_siblings),
            )

        self._repo.delete_item_parent_link(item_id, old_category_id)

        new_link = ItemParentLink(item_id=item_id, category_id=new_category_id, sort_index=insert_pos)
        existing_siblings.insert(insert_pos, new_link)

        for i, lnk in enumerate(existing_siblings):
            lnk.sort_index = i
            self._repo.save_item_parent_link(lnk)

        clear_all_caches()
        return new_link

    def reparent_category(
        self,
        category_id: UUID,
        old_parent_id: UUID,
        new_parent_id: UUID,
        insert_before_uuid: UUID | None,
    ) -> CategoryParentLink:
        """Move a category from one parent to another, inserting at the specified position.

        Args:
            category_id: The UUID of the category to move.
            old_parent_id: The UUID of the current parent to remove the category from.
            new_parent_id: The UUID of the target parent to add the category to.
            insert_before_uuid: Insert before this sibling UUID; None appends at end.

        Returns:
            The new CategoryParentLink in the destination parent.

        Raises:
            TaxomeshCategoryNotFoundError: If any category does not exist.
            TaxomeshCyclicDependencyError: If the move would create a DAG cycle.
        """
        self.get_category(category_id)
        self.get_category(old_parent_id)
        self.get_category(new_parent_id)

        existing_siblings = sorted(
            [
                lnk
                for lnk in self._repo.list_category_parent_links()
                if lnk.parent_category_id == new_parent_id and lnk.category_id != category_id
            ],
            key=lambda lnk: lnk.sort_index,
        )

        if insert_before_uuid is None:
            insert_pos = len(existing_siblings)
        else:
            insert_pos = next(
                (i for i, lnk in enumerate(existing_siblings) if lnk.category_id == insert_before_uuid),
                len(existing_siblings),
            )

        self._repo.delete_category_parent_link(category_id, old_parent_id)

        # add_category_parent runs cycle detection internally
        new_link = self.add_category_parent(category_id, new_parent_id, sort_index=insert_pos)
        existing_siblings.insert(insert_pos, new_link)

        for i, lnk in enumerate(existing_siblings):
            lnk.sort_index = i
            self._repo.save_category_parent_link(lnk)

        clear_all_caches()
        return new_link

    def reorder_items_in_category(self, category_id: UUID, item_ids_in_order: list[UUID]) -> None:
        """Reassign sort_index values for items within a category.

        Args:
            category_id: The UUID of the category whose items are being reordered.
            item_ids_in_order: All item UUIDs in the desired final order.

        Raises:
            TaxomeshCategoryNotFoundError: If the category does not exist.
            ValueError: If any UUID in item_ids_in_order is not placed in this category.
        """
        if self._repo.get_category(category_id) is None:
            raise TaxomeshCategoryNotFoundError(f"Category not found: {category_id}")
        existing = {lnk.item_id: lnk for lnk in self._repo.list_item_parent_links() if lnk.category_id == category_id}
        for uid in item_ids_in_order:
            if uid not in existing:
                raise ValueError(f"Item {uid} is not placed in category {category_id}")
        for sort_index, uid in enumerate(item_ids_in_order):
            link = existing[uid]
            link.sort_index = sort_index
            self._repo.save_item_parent_link(link)
        clear_all_caches()

    def remove_item_from_category(self, item_id: UUID, category_id: UUID) -> None:
        """Remove an item's placement from a category. No-op if the placement does not exist.

        Args:
            item_id: The item's UUID.
            category_id: The category's UUID.

        Raises:
            TaxomeshItemNotFoundError: If no item with the given item_id exists.
            TaxomeshCategoryNotFoundError: If no category with the given category_id exists.
        """
        if self._repo.get_item(item_id) is None:
            raise TaxomeshItemNotFoundError(f"Item not found: {item_id}")
        if self._repo.get_category(category_id) is None:
            raise TaxomeshCategoryNotFoundError(f"Category not found: {category_id}")
        self._repo.delete_item_parent_link(item_id, category_id)
        clear_all_caches()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_items(
        self,
        query: str,
        *,
        limit: int = DEFAULT_SEARCH_LIMIT,
        category_id: UUID | None = None,
        enabled: bool = True,
        fuzzy: bool = True,
        recursive: bool = False,
    ) -> list[Item]:
        """Search items by name, slug, and external_id using fuzzy matching.

        When *category_id* is ``None`` (the default), candidates are loaded from
        an internal pre-normalized corpus that is built once and reused across
        repeated searches. The corpus is automatically invalidated by any item
        write operation. Category-filtered searches bypass the corpus and load
        candidates directly.

        Args:
            query: The text to search for.
            limit: Maximum number of results to return; must be ≥ 1.
            category_id: When provided, restrict candidates to items placed in
                this category. When *recursive* is also ``True`` the candidates
                include items in all descendant categories as well.
            enabled: When ``True`` (default) only enabled items are
                considered. Pass ``False`` for only disabled items.
            fuzzy: When ``True`` (default) rapidfuzz scores are included in
                ranking. Pass ``False`` for exact/substring matching only.
            recursive: Only meaningful when *category_id* is set. When ``True``
                the search covers the full category sub-tree.

        Returns:
            Scored items in descending score order (ties broken by normalised
            name), trimmed to *limit* entries.

        Raises:
            ValueError: If *limit* ≤ 0.
            TaxomeshCategoryNotFoundError: If *category_id* is provided but
                does not exist in the repository.
        """
        if limit <= 0:
            raise ValueError(f"limit must be ≥ 1, got {limit}")
        if not query.strip():
            return []

        norm_q = SearchEngine.normalize(query)
        if category_id is None:
            corpus = self._get_item_corpus()
            filtered = [sc for sc in corpus if sc.obj.enabled == enabled]
            return self._score_corpus(norm_q, filtered, fuzzy=fuzzy, limit=limit)
        candidates = self._load_item_candidates(category_id=category_id, recursive=recursive)
        candidates = [item for item in candidates if item.enabled == enabled]
        return self._score_and_rank(
            norm_q,
            candidates,
            get_name=lambda i: i.name,
            get_slug=lambda i: i.slug,
            get_ext=lambda i: i.external_id,
            fuzzy=fuzzy,
            limit=limit,
        )

    def search_categories(
        self,
        query: str,
        *,
        limit: int = DEFAULT_SEARCH_LIMIT,
        parent_id: UUID | None = None,
        enabled: bool = True,
        fuzzy: bool = True,
    ) -> list[Category]:
        """Search categories by name, slug, and external_id using fuzzy matching.

        The internal root category is always excluded from results.

        When *parent_id* is ``None`` (the default), candidates are loaded from
        an internal pre-normalized corpus that is built once and reused across
        repeated searches. The corpus is automatically invalidated by any
        category write operation. Parent-filtered searches bypass the corpus
        and load candidates directly.

        Args:
            query: The text to search for.
            limit: Maximum number of results to return; must be ≥ 1.
            parent_id: When provided, restrict candidates to direct children of
                this category.
            enabled: When ``True`` (default) only enabled categories are
                considered. Pass ``False`` for only disabled categories.
            fuzzy: When ``True`` (default) rapidfuzz scores are included.

        Returns:
            Scored categories in descending score order, trimmed to *limit*.

        Raises:
            ValueError: If *limit* ≤ 0.
            TaxomeshCategoryNotFoundError: If *parent_id* is provided but does
                not exist in the repository.
        """
        if limit <= 0:
            raise ValueError(f"limit must be ≥ 1, got {limit}")
        if not query.strip():
            return []

        norm_q = SearchEngine.normalize(query)
        if parent_id is None:
            corpus = self._get_category_corpus()
            filtered = [sc for sc in corpus if sc.obj.enabled == enabled]
            return self._score_corpus(norm_q, filtered, fuzzy=fuzzy, limit=limit)
        candidates = self.list_categories(parent_id=parent_id, enabled=enabled)
        return self._score_and_rank(
            norm_q,
            candidates,
            get_name=lambda c: c.name,
            get_slug=lambda c: c.slug,
            get_ext=lambda c: c.external_id,
            fuzzy=fuzzy,
            limit=limit,
        )

    def _get_item_corpus(self) -> list[SearchCandidate[Item]]:
        """Build and cache pre-normalized search candidates for all items.

        Returns the cached item corpus if already built; otherwise loads all items
        via the memoized ``list_items()`` path, normalizes each candidate's fields
        once, stores the result, and returns it.

        The corpus is invalidated (set to ``None``) by any item write operation
        (``create_item``, ``update_item``, ``delete_item``).

        Returns:
            List of ``SearchCandidate`` wrappers covering all items.
        """
        if self._item_corpus is None:
            self._item_corpus = [
                SearchCandidate(
                    obj=item,
                    norm_name=SearchEngine.normalize(item.name),
                    norm_slug=SearchEngine.normalize(item.slug),
                    norm_ext=(SearchEngine.normalize(item.external_id) if item.external_id is not None else ""),
                )
                for item in self._repo.list_items(enabled=None)
            ]
        return self._item_corpus

    def _get_category_corpus(self) -> list[SearchCandidate[Category]]:
        """Build and cache pre-normalized search candidates for all categories.

        Returns the cached category corpus if already built; otherwise loads all
        categories from the repository, excludes the internal root category,
        normalizes each candidate's fields once, stores the result, and returns it.

        The corpus is invalidated (set to ``None``) by any category write operation
        (``create_category``, ``update_category``, ``delete_category``).

        Returns:
            List of ``SearchCandidate`` wrappers covering all non-root categories.
        """
        if self._category_corpus is None:
            self._category_corpus = [
                SearchCandidate(
                    obj=cat,
                    norm_name=SearchEngine.normalize(cat.name),
                    norm_slug=SearchEngine.normalize(cat.slug),
                    norm_ext=(SearchEngine.normalize(cat.external_id) if cat.external_id is not None else ""),
                )
                for cat in self._repo.list_categories(enabled=None)
                if cat.category_id != self._root_id
            ]
        return self._category_corpus

    def _rank_scored(self, scored: list[tuple[float, str, _T]], limit: int) -> list[_T]:
        """Sort *scored* tuples by descending score then ascending name, capped at *limit*.

        When *limit* is smaller than the number of matches, ``heapq.nsmallest`` is
        used to avoid a full sort (O(N log k) vs O(N log N)).

        Args:
            scored: List of ``(score, norm_name, obj)`` tuples to rank.
            limit: Maximum number of results to return.

        Returns:
            Domain objects in ranked order, capped at *limit*.
        """
        if limit < len(scored):
            return [c for _, _, c in heapq.nsmallest(limit, scored, key=lambda t: (-t[0], t[1]))]
        scored.sort(key=lambda t: (-t[0], t[1]))
        return [c for _, _, c in scored]

    def _score_corpus(
        self,
        norm_q: str,
        corpus: list[SearchCandidate[_T]],
        *,
        fuzzy: bool,
        limit: int,
    ) -> list[_T]:
        """Score pre-normalized search candidates and return the top *limit* results.

        Accepts a list of ``SearchCandidate`` wrappers whose fields are already
        normalized, skipping the per-call normalization step performed by
        ``_score_and_rank``. Uses the same ranking logic: descending score, then
        ascending normalized name.

        Args:
            norm_q: Pre-normalized query string.
            corpus: Pre-normalized candidates to score.
            fuzzy: Passed through to ``SearchEngine._score_prenorm``.
            limit: Maximum number of results to return.

        Returns:
            Domain objects sorted by descending score then normalised name, capped
            at *limit*.
        """
        engine = SearchEngine()
        scored: list[tuple[float, str, _T]] = []
        for sc in corpus:
            score = engine._score_prenorm(norm_q, sc.norm_name, sc.norm_slug, sc.norm_ext, fuzzy=fuzzy)
            if score is not None:
                scored.append((score, sc.norm_name, sc.obj))
        return self._rank_scored(scored, limit)

    def _score_and_rank(
        self,
        norm_q: str,
        candidates: list[_T],
        *,
        get_name: Callable[[_T], str],
        get_slug: Callable[[_T], str],
        get_ext: Callable[[_T], str | None],
        fuzzy: bool,
        limit: int,
    ) -> list[_T]:
        """Score *candidates* against *norm_q* and return the top *limit* results.

        Each candidate's fields are normalized exactly once via
        ``SearchCandidate`` before scoring. When ``limit`` is smaller than the
        number of matching candidates, ``heapq.nsmallest`` is used instead of a
        full sort to reduce work from O(N log N) to O(N log k).

        Args:
            norm_q: Pre-normalised query string.
            candidates: Entities to score (items or categories).
            get_name: Accessor for the candidate's name field.
            get_slug: Accessor for the candidate's slug field.
            get_ext: Accessor for the candidate's external_id field.
            fuzzy: Passed through to ``SearchEngine._score_prenorm``.
            limit: Maximum number of results to return.

        Returns:
            Entities sorted by descending score then normalised name, capped at *limit*.
        """
        engine = SearchEngine()

        # Normalize each candidate's fields exactly once.
        def _norm_ext(c: _T) -> str:
            ext = get_ext(c)
            return SearchEngine.normalize(ext) if ext is not None else ""

        search_candidates: list[SearchCandidate[_T]] = [
            SearchCandidate(
                obj=c,
                norm_name=SearchEngine.normalize(get_name(c)),
                norm_slug=SearchEngine.normalize(get_slug(c)),
                norm_ext=_norm_ext(c),
            )
            for c in candidates
        ]
        scored: list[tuple[float, str, _T]] = []
        for sc in search_candidates:
            score = engine._score_prenorm(norm_q, sc.norm_name, sc.norm_slug, sc.norm_ext, fuzzy=fuzzy)
            if score is not None:
                scored.append((score, sc.norm_name, sc.obj))
        return self._rank_scored(scored, limit)

    def _collect_descendant_ids(self, category_id: UUID) -> set[UUID]:
        """Return the set of all descendant category UUIDs using BFS.

        Args:
            category_id: The root of the sub-tree to traverse.

        Returns:
            Set of UUIDs for every category that is (directly or transitively)
            a child of *category_id*. Does not include *category_id* itself.
        """
        links = self._repo.list_category_parent_links()
        children_map: dict[UUID, list[UUID]] = {}
        for lnk in links:
            children_map.setdefault(lnk.parent_category_id, []).append(lnk.category_id)

        result: set[UUID] = set()
        queue = list(children_map.get(category_id, []))
        while queue:
            cid = queue.pop()
            if cid not in result:
                result.add(cid)
                queue.extend(children_map.get(cid, []))
        return result

    def _load_item_candidates(
        self,
        *,
        category_id: UUID | None,
        recursive: bool,
    ) -> list[Item]:
        """Return item candidates for search, respecting category and recursive filters.

        Args:
            category_id: Category filter; ``None`` means all items.
            recursive: When ``True`` and *category_id* is set, include items in
                all descendant categories (deduplication is applied).

        Returns:
            Deduplicated list of Item instances.
        """
        if category_id is None:
            return self.list_items()

        if not recursive:
            # list_items validates category existence
            return self.list_items(category_id=category_id)

        # Recursive: union of items in category_id and all descendants
        # Validate existence first (fail-fast before tree traversal)
        self.get_category(category_id)
        all_category_ids = {category_id} | self._collect_descendant_ids(category_id)

        links = self._repo.list_item_parent_links(category_ids=all_category_ids)
        # Ordered dedup: first link wins per item (dict preserves insertion order)
        matched_ids = list(dict.fromkeys(lnk.item_id for lnk in links))
        item_map = self._repo.get_items_by_ids(matched_ids, enabled=True)
        return [item_map[item_id] for item_id in matched_ids if item_id in item_map]
