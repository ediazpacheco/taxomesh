"""File-backed YAML repository for taxomesh.

Reads the full data set from a single YAML file at initialisation and writes
the full current state back after every mutating operation. Writes are atomic:
a sibling temporary file is flushed with ``os.fsync`` and then renamed into
place with ``os.replace`` so the target file is never in a partial state.
"""

import os
import tempfile
from collections.abc import Collection
from pathlib import Path
from typing import Any, Final, Literal
from uuid import UUID

import yaml

from taxomesh.adapters.repositories._external_id import bulk_lookup_by_external_id, check_external_id_unique
from taxomesh.domain.models import (
    Category,
    CategoryParentLink,
    Item,
    ItemParentLink,
    ItemRelationLink,
    ItemTagLink,
    Tag,
)
from taxomesh.exceptions import TaxomeshRepositoryError

DEFAULT_YAML_PATH: Final[Path] = Path("data/taxomesh.yaml")

# TOML config identifier for the YAML backend (value of [repository] type).
YAML_REPO_TYPE: Final[str] = "yaml"


class YAMLRepository:
    """Repository that persists taxomesh data to a YAML file on disk.

    All entity collections (categories, items, tags, and all link types)
    are stored as a single YAML document. The file is read once at
    construction and written atomically after every mutation.

    Uses ``yaml.safe_load`` / ``yaml.safe_dump`` exclusively to prevent
    arbitrary object deserialisation from untrusted files.

    Args:
        path: Path to the YAML storage file. Defaults to ``data/taxomesh.yaml`` in
            the current working directory. Missing parent directories are
            created automatically.

    Raises:
        TaxomeshRepositoryError: If ``path`` is a directory, or if the file
            exists but cannot be parsed as valid storage content.
    """

    def __init__(self, path: Path | str = DEFAULT_YAML_PATH) -> None:
        """Initialise the repository from an existing file or create a new one.

        Args:
            path: Path to the YAML storage file. Defaults to ``data/taxomesh.yaml``
                in the current working directory.

        Raises:
            TaxomeshRepositoryError: If the path is a directory, or if the
                file exists but cannot be parsed.
        """
        self._path = Path(path)
        self._categories: dict[UUID, Category] = {}
        self._items: dict[UUID, Item] = {}
        self._tags: dict[UUID, Tag] = {}
        self._links: list[ItemTagLink] = []
        self._category_parent_links: list[CategoryParentLink] = []
        self._item_parent_links: list[ItemParentLink] = []
        self._item_relation_links: list[ItemRelationLink] = []

        if self._path.is_dir():
            raise TaxomeshRepositoryError(f"path is a directory, not a file: {self._path}")

        if self._path.exists():
            self._load()
        else:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._flush()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load state from the YAML file into in-memory collections.

        Raises:
            TaxomeshRepositoryError: If the file cannot be read or parsed.
        """
        try:
            raw: Any = yaml.safe_load(self._path.read_text(encoding="utf-8"))
            if raw is None:
                # Empty file — treat as empty taxonomy
                return
            if not isinstance(raw, dict):
                raise ValueError("expected a YAML mapping at the top level")
            data: dict[str, Any] = raw
            self._categories = {UUID(k): Category.model_validate(v) for k, v in data.get("categories", {}).items()}
            self._items = {UUID(k): Item.model_validate(v) for k, v in data.get("items", {}).items()}
            self._tags = {UUID(k): Tag.model_validate(v) for k, v in data.get("tags", {}).items()}
            self._links = [ItemTagLink.model_validate(lnk) for lnk in data.get("item_tag_links", [])]
            self._category_parent_links = [
                CategoryParentLink.model_validate(lnk) for lnk in data.get("category_parent_links", [])
            ]
            self._item_parent_links = [ItemParentLink.model_validate(lnk) for lnk in data.get("item_parent_links", [])]
            self._item_relation_links = [
                ItemRelationLink.model_validate(lnk) for lnk in data.get("item_relation_links", [])
            ]
        except TaxomeshRepositoryError:
            raise
        except Exception as exc:
            raise TaxomeshRepositoryError(f"could not load repository from {self._path}: {exc}") from exc

    def _flush(self) -> None:
        """Atomically write the current in-memory state to disk.

        Serialises all collections to YAML, writes to a sibling temp file,
        calls ``os.fsync`` to flush OS buffers, then replaces the target file
        via ``os.replace`` (POSIX atomic rename).
        """
        data: dict[str, Any] = {
            "categories": {str(k): v.model_dump(mode="json") for k, v in self._categories.items()},
            "items": {str(k): v.model_dump(mode="json") for k, v in self._items.items()},
            "tags": {str(k): v.model_dump(mode="json") for k, v in self._tags.items()},
            "item_tag_links": [lnk.model_dump(mode="json") for lnk in self._links],
            "category_parent_links": [lnk.model_dump(mode="json") for lnk in self._category_parent_links],
            "item_parent_links": [lnk.model_dump(mode="json") for lnk in self._item_parent_links],
            "item_relation_links": [lnk.model_dump(mode="json") for lnk in self._item_relation_links],
        }
        payload = yaml.safe_dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
        dir_ = self._path.parent
        fd, tmp_path_str = tempfile.mkstemp(dir=dir_, suffix=".tmp")
        tmp_path = Path(tmp_path_str)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, self._path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    # ------------------------------------------------------------------
    # Category
    # ------------------------------------------------------------------

    def save_category(self, category: Category) -> None:
        """Insert or update a category record.

        Args:
            category: The Category instance to persist.

        Raises:
            TaxomeshExternalIdConflictError: If category.external_id is not None and another
                record with a different category_id already holds the same external_id.
        """
        check_external_id_unique(category.category_id, category.external_id, self._categories, "category")
        if category.category_id in self._categories:
            category.version += 1
        self._categories[category.category_id] = category
        self._flush()

    def get_category(self, category_id: UUID) -> Category | None:
        """Retrieve a category by its identifier.

        Args:
            category_id: The library-assigned UUID of the category.

        Returns:
            The matching Category, or None if it does not exist.
        """
        return self._categories.get(category_id)

    def list_categories(self, *, enabled: bool | None = True) -> list[Category]:
        """Return stored categories ordered by name then category_id.

        Args:
            enabled: ``True`` returns only enabled; ``False`` only disabled;
                ``None`` returns all regardless of enabled state.

        Returns:
            List of categories ordered by ``(name ASC, category_id ASC)``;
            empty list if no categories match.
        """
        cats = list(self._categories.values())
        if enabled is not None:
            cats = [c for c in cats if c.enabled == enabled]
        return sorted(cats, key=lambda c: (c.name, str(c.category_id)))

    def delete_category(self, category_id: UUID) -> bool:
        """Delete a category by its identifier.

        Args:
            category_id: The library-assigned UUID of the category to delete.

        Returns:
            True if the category was found and deleted; False if it did not exist.
        """
        if category_id not in self._categories:
            return False
        del self._categories[category_id]
        self._flush()
        return True

    # ------------------------------------------------------------------
    # Item
    # ------------------------------------------------------------------

    def save_item(self, item: Item) -> None:
        """Insert or update an item record.

        Args:
            item: The Item instance to persist.

        Raises:
            TaxomeshExternalIdConflictError: If item.external_id is not None and another
                record with a different item_id already holds the same external_id.
        """
        check_external_id_unique(item.item_id, item.external_id, self._items, "item")
        if item.item_id in self._items:
            item.version += 1
        self._items[item.item_id] = item
        self._flush()

    def get_item(self, item_id: UUID) -> Item | None:
        """Retrieve an item by its internal identifier.

        Args:
            item_id: The library-assigned UUID of the item.

        Returns:
            The matching Item, or None if it does not exist.
        """
        return self._items.get(item_id)

    def list_items(self, *, enabled: bool | None = True) -> list[Item]:
        """Return stored items ordered by name then item_id.

        Args:
            enabled: ``True`` returns only enabled; ``False`` only disabled;
                ``None`` returns all regardless of enabled state.

        Returns:
            List of items ordered by ``(name ASC, item_id ASC)``; empty list
            if no items match.
        """
        items = list(self._items.values())
        if enabled is not None:
            items = [i for i in items if i.enabled == enabled]
        return sorted(items, key=lambda i: (i.name, str(i.item_id)))

    def delete_item(self, item_id: UUID) -> bool:
        """Delete an item by its internal identifier.

        Cascades: all item relation links where this item is the source or
        target are removed alongside the item.

        Args:
            item_id: The library-assigned UUID of the item to delete.

        Returns:
            True if the item was found and deleted; False if it did not exist.
        """
        if item_id not in self._items:
            return False
        del self._items[item_id]
        self._item_relation_links = [
            lnk for lnk in self._item_relation_links if item_id not in {lnk.source_item_id, lnk.target_item_id}
        ]
        self._flush()
        return True

    # ------------------------------------------------------------------
    # Tag
    # ------------------------------------------------------------------

    def save_tag(self, tag: Tag) -> None:
        """Insert or update a tag record.

        Args:
            tag: The Tag instance to persist.
        """
        self._tags[tag.tag_id] = tag
        self._flush()

    def get_tag(self, tag_id: UUID) -> Tag | None:
        """Retrieve a tag by its identifier.

        Args:
            tag_id: The library-assigned UUID of the tag.

        Returns:
            The matching Tag, or None if it does not exist.
        """
        return self._tags.get(tag_id)

    def list_tags(self) -> list[Tag]:
        """Return all stored tags.

        Returns:
            List of all tags; empty list if the store is empty.
        """
        return list(self._tags.values())

    def delete_tag(self, tag_id: UUID) -> bool:
        """Delete a tag entity by its identifier.

        Args:
            tag_id: The library-assigned UUID of the tag.

        Returns:
            True if the tag was found and deleted; False if it did not exist.
        """
        if tag_id not in self._tags:
            return False
        del self._tags[tag_id]
        self._flush()
        return True

    # ------------------------------------------------------------------
    # Tag ↔ Item association
    # ------------------------------------------------------------------

    def assign_tag(self, tag_id: UUID, item_id: UUID) -> None:
        """Associate a tag with an item. Idempotent — no-op if already linked.

        Args:
            tag_id: The library-assigned UUID of the tag.
            item_id: The library-assigned UUID of the item.
        """
        already_linked = any(lnk.tag_id == tag_id and lnk.item_id == item_id for lnk in self._links)
        if not already_linked:
            self._links.append(ItemTagLink(tag_id=tag_id, item_id=item_id))
            self._flush()

    def remove_tag(self, tag_id: UUID, item_id: UUID) -> bool:
        """Remove the association between a tag and an item.

        Args:
            tag_id: The library-assigned UUID of the tag.
            item_id: The library-assigned UUID of the item.

        Returns:
            True if the association was found and removed; False if it did not exist.
        """
        before = len(self._links)
        self._links = [lnk for lnk in self._links if not (lnk.tag_id == tag_id and lnk.item_id == item_id)]
        if len(self._links) < before:
            self._flush()
            return True
        return False

    # ------------------------------------------------------------------
    # Category parent links
    # ------------------------------------------------------------------

    def save_category_parent_link(self, link: CategoryParentLink) -> None:
        """Upsert a category→parent relationship.

        If a link with the same (category_id, parent_category_id) pair already
        exists its sort_index is updated in-place. No duplicate is created.

        Args:
            link: The CategoryParentLink to persist.
        """
        for i, existing in enumerate(self._category_parent_links):
            if existing.category_id == link.category_id and existing.parent_category_id == link.parent_category_id:
                self._category_parent_links[i] = link
                self._flush()
                return
        self._category_parent_links.append(link)
        self._flush()

    def list_category_parent_links(self) -> list[CategoryParentLink]:
        """Return all stored category-parent relationships grouped by parent then sort_index.

        Returns:
            List of all CategoryParentLink records ordered by
            ``(parent_category_id ASC, sort_index ASC, category_id ASC)``.
        """
        return sorted(
            self._category_parent_links,
            key=lambda lnk: (str(lnk.parent_category_id), lnk.sort_index, str(lnk.category_id)),
        )

    # ------------------------------------------------------------------
    # Item → Category placement
    # ------------------------------------------------------------------

    def save_item_parent_link(self, link: ItemParentLink) -> None:
        """Upsert an item→category placement.

        If a link with the same (item_id, category_id) pair already exists its
        sort_index is updated in-place. No duplicate is created.

        Args:
            link: The ItemParentLink to persist.
        """
        for i, existing in enumerate(self._item_parent_links):
            if existing.item_id == link.item_id and existing.category_id == link.category_id:
                self._item_parent_links[i] = link
                self._flush()
                return
        self._item_parent_links.append(link)
        self._flush()

    def list_item_parent_links(self) -> list[ItemParentLink]:
        """Return all item→category placements grouped by category then sort_index.

        Returns:
            List of all ItemParentLink records ordered by
            ``(category_id ASC, sort_index ASC, item_id ASC)``.
        """
        return sorted(
            self._item_parent_links,
            key=lambda lnk: (str(lnk.category_id), lnk.sort_index, str(lnk.item_id)),
        )

    def delete_category_parent_link(self, category_id: UUID, parent_category_id: UUID) -> bool:
        """Delete a category→parent relationship.

        Args:
            category_id: The child category's UUID.
            parent_category_id: The parent category's UUID.

        Returns:
            True if the link was found and deleted; False if it did not exist.
        """
        before = len(self._category_parent_links)
        self._category_parent_links = [
            lnk
            for lnk in self._category_parent_links
            if not (lnk.category_id == category_id and lnk.parent_category_id == parent_category_id)
        ]
        if len(self._category_parent_links) < before:
            self._flush()
            return True
        return False

    def delete_item_parent_link(self, item_id: UUID, category_id: UUID) -> bool:
        """Delete an item→category placement.

        Args:
            item_id: The item's UUID.
            category_id: The category's UUID.

        Returns:
            True if the placement was found and deleted; False if it did not exist.
        """
        before = len(self._item_parent_links)
        self._item_parent_links = [
            lnk for lnk in self._item_parent_links if not (lnk.item_id == item_id and lnk.category_id == category_id)
        ]
        if len(self._item_parent_links) < before:
            self._flush()
            return True
        return False

    # ------------------------------------------------------------------
    # Item relation links
    # ------------------------------------------------------------------

    def save_item_relation_link(self, link: ItemRelationLink) -> None:
        """Upsert a directed item-to-item relation.

        Args:
            link: The ItemRelationLink to persist.
        """
        for i, existing in enumerate(self._item_relation_links):
            if (
                existing.source_item_id == link.source_item_id
                and existing.target_item_id == link.target_item_id
                and existing.relation_type == link.relation_type
            ):
                self._item_relation_links[i] = link
                self._flush()
                return
        self._item_relation_links.append(link)
        self._flush()

    def list_item_relation_links(
        self,
        item_id: UUID,
        *,
        relation_type: str | None = None,
        direction: Literal["outgoing", "incoming"] = "outgoing",
    ) -> list[ItemRelationLink]:
        """Return item relation links for the given item.

        Args:
            item_id: The UUID of the item to query.
            relation_type: Optional filter; if provided only links with this
                exact (already-normalised) type are returned.
            direction: ``"outgoing"`` returns links where ``source_item_id``
                equals ``item_id``; ``"incoming"`` returns links where
                ``target_item_id`` equals ``item_id``.

        Returns:
            List of matching ItemRelationLink objects; empty list if none match.
        """
        if direction == "outgoing":
            result = [lnk for lnk in self._item_relation_links if lnk.source_item_id == item_id]
        else:
            result = [lnk for lnk in self._item_relation_links if lnk.target_item_id == item_id]
        if relation_type is not None:
            result = [lnk for lnk in result if lnk.relation_type == relation_type]
        return sorted(result, key=lambda lnk: (lnk.sort_index, str(lnk.source_item_id), str(lnk.target_item_id)))

    def list_item_relation_links_for_sources(
        self,
        source_item_ids: Collection[UUID],
        *,
        relation_types: Collection[str] | None = None,
    ) -> list[ItemRelationLink]:
        """Return outgoing links for many source items."""
        source_set = set(source_item_ids)
        if not source_set:
            return []
        result = [lnk for lnk in self._item_relation_links if lnk.source_item_id in source_set]
        if relation_types:
            type_set = set(relation_types)
            result = [lnk for lnk in result if lnk.relation_type in type_set]
        return sorted(
            result,
            key=lambda lnk: (str(lnk.source_item_id), lnk.relation_type, lnk.sort_index, str(lnk.target_item_id)),
        )

    def delete_item_relation_link(
        self,
        source_item_id: UUID,
        target_item_id: UUID,
        relation_type: str,
    ) -> bool:
        """Delete the specific directed relation identified by the triple.

        Args:
            source_item_id: UUID of the source item.
            target_item_id: UUID of the target item.
            relation_type: Exact (already-normalised, lowercase) relation type string.

        Returns:
            True if the relation was found and deleted; False if it did not exist.
        """
        before = len(self._item_relation_links)
        self._item_relation_links = [
            lnk
            for lnk in self._item_relation_links
            if not (
                lnk.source_item_id == source_item_id
                and lnk.target_item_id == target_item_id
                and lnk.relation_type == relation_type
            )
        ]
        if len(self._item_relation_links) < before:
            self._flush()
            return True
        return False

    # ------------------------------------------------------------------
    # External-ID lookup
    # ------------------------------------------------------------------

    def get_item_by_external_id(self, external_id: str) -> Item | None:
        """Return the item with the given external_id, or None.

        Args:
            external_id: The external identifier to look up (already a str; never None).

        Returns:
            The matching Item, or None if no item has this external_id.
        """
        return next((item for item in self._items.values() if item.external_id == external_id), None)

    def get_category_by_external_id(self, external_id: str) -> Category | None:
        """Return the category with the given external_id, or None.

        Args:
            external_id: The external identifier to look up (already a str; never None).

        Returns:
            The matching Category, or None if no category has this external_id.
        """
        return next((cat for cat in self._categories.values() if cat.external_id == external_id), None)

    def get_items_by_external_ids(
        self,
        external_ids: Collection[str],
        *,
        enabled: bool | None = None,
    ) -> dict[str, Item]:
        """Return items whose external_id is in external_ids.

        Args:
            external_ids: A collection of external ID strings to look up.
                Pre-normalised: no blank strings, no duplicates expected.
            enabled: ``True`` returns only enabled items; ``False`` only
                disabled; ``None`` (default) returns all matching items.

        Returns:
            A dict mapping each found external_id to its Item. Missing IDs
            are silently absent — no error is raised.
        """
        return bulk_lookup_by_external_id(self._items, external_ids, enabled)

    def get_categories_by_external_ids(
        self,
        external_ids: Collection[str],
        *,
        enabled: bool | None = None,
    ) -> dict[str, Category]:
        """Return categories whose external_id is in external_ids.

        Root category exclusion is the service's responsibility, not the
        adapter's.

        Args:
            external_ids: A collection of external ID strings to look up.
                Pre-normalised: no blank strings, no duplicates expected.
            enabled: ``True`` returns only enabled categories; ``False`` only
                disabled; ``None`` (default) returns all matching categories.

        Returns:
            A dict mapping each found external_id to its Category. Missing
            IDs are silently absent — no error is raised.
        """
        return bulk_lookup_by_external_id(self._categories, external_ids, enabled)

    def get_item_by_slug(self, slug: str) -> Item | None:
        """Return the item with the given slug, or None.

        Args:
            slug: The slug to look up.

        Returns:
            The matching Item, or None if no item has this slug.
        """
        return next((i for i in self._items.values() if i.slug == slug), None)

    def get_category_by_slug(self, slug: str) -> Category | None:
        """Return the category with the given slug, or None.

        Args:
            slug: The slug to look up.

        Returns:
            The matching Category, or None if no category has this slug.
        """
        return next((c for c in self._categories.values() if c.slug == slug), None)

    # ------------------------------------------------------------------
    # Configuration introspection
    # ------------------------------------------------------------------

    def get_config_summary(self) -> str:
        """Return the as-configured path of the YAML storage file.

        Returns:
            String representation of the path supplied at construction time.
            Never raises; never returns an empty string.
        """
        return str(self._path)

    def get_debug_info(self) -> dict[str, Any]:
        """Return diagnostic info for this YAML repository.

        Returns:
            Dict with key ``path`` containing the storage file path as a string.
        """
        return {"path": str(self._path)}
