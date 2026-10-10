"""Shared pytest fixtures for the service test suite."""

import contextlib
from collections.abc import Collection, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal
from uuid import UUID

import pytest

from taxomesh.adapters.repositories._external_id import bulk_lookup_by_external_id, check_external_id_unique
from taxomesh.adapters.repositories._version import row_to_store
from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YamlRepository
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.info import RepositoryInfo
from taxomesh.domain.models import (
    Category,
    CategoryParentLink,
    Item,
    ItemParentLink,
    ItemRelationLink,
    ItemTagLink,
    Tag,
)
from taxomesh.ports.repository import TaxomeshRepositoryBase


class InMemoryRepository:
    """Pure in-memory repository for testing.

    Implements all TaxomeshRepositoryBase methods without inheriting from it,
    proving that structural (Protocol) typing is sufficient.
    """

    def __init__(self) -> None:
        """Initialise empty in-memory collections."""
        self._categories: dict[UUID, Category] = {}
        self._items: dict[UUID, Item] = {}
        self._tags: dict[UUID, Tag] = {}
        self._links: list[ItemTagLink] = []
        self._category_parent_links: list[CategoryParentLink] = []
        self._item_parent_links: list[ItemParentLink] = []
        self._item_relation_links: list[ItemRelationLink] = []

    # --- Atomicity boundary ---

    def atomic(self) -> AbstractContextManager[None]:
        """Return a best-effort no-op boundary (in-memory has no transaction)."""
        return contextlib.nullcontext()

    # --- Category ---

    def save_category(self, category: Category, *, expected_version: int | None = None) -> Category:
        """Insert or update a category; an update stores the replaced row's version plus one."""
        stored = row_to_store(
            category,
            self._categories.get(category.category_id),
            expected_version=expected_version,
            entity_name="category",
            entity_id=category.category_id,
        )
        check_external_id_unique(category.category_id, category.external_id, self._categories, "category")
        self._categories[category.category_id] = stored
        return stored

    def find_category(self, category_id: UUID) -> Category | None:
        """Return category by id, or None."""
        return self._categories.get(category_id)

    def list_categories(self, *, enabled: bool | None = True) -> list[Category]:
        """Return categories, filtered by enabled state, ordered by name then category_id."""
        cats = list(self._categories.values())
        if enabled is not None:
            cats = [c for c in cats if c.enabled == enabled]
        return sorted(cats, key=lambda c: (c.name, str(c.category_id)))

    def delete_category(self, category_id: UUID) -> bool:
        """Delete category and every link naming it; return True if it existed."""
        if category_id not in self._categories:
            return False
        del self._categories[category_id]
        self._drop_dangling_links()
        return True

    # --- Item ---

    def save_item(self, item: Item, *, expected_version: int | None = None) -> Item:
        """Insert or update an item; an update stores the replaced row's version plus one."""
        stored = row_to_store(
            item,
            self._items.get(item.item_id),
            expected_version=expected_version,
            entity_name="item",
            entity_id=item.item_id,
        )
        check_external_id_unique(item.item_id, item.external_id, self._items, "item")
        self._items[item.item_id] = stored
        return stored

    def find_item(self, item_id: UUID) -> Item | None:
        """Return item by id, or None."""
        return self._items.get(item_id)

    def list_items(self, *, enabled: bool | None = True) -> list[Item]:
        """Return items, filtered by enabled state, ordered by name then item_id."""
        items = list(self._items.values())
        if enabled is not None:
            items = [i for i in items if i.enabled == enabled]
        return sorted(items, key=lambda i: (i.name, str(i.item_id)))

    def delete_item(self, item_id: UUID) -> bool:
        """Delete item and every link naming it; return True if it existed."""
        if item_id not in self._items:
            return False
        del self._items[item_id]
        self._drop_dangling_links()
        return True

    # --- Tag ---

    def save_tag(self, tag: Tag) -> None:
        """Insert or update a tag."""
        self._tags[tag.tag_id] = tag

    def find_tag(self, tag_id: UUID) -> Tag | None:
        """Return tag by id, or None."""
        return self._tags.get(tag_id)

    def list_tags(self) -> list[Tag]:
        """Return all tags."""
        return list(self._tags.values())

    def map_tags_by_id(self, tag_ids: Collection[UUID]) -> Mapping[UUID, Tag]:
        """Return the found tags keyed by id."""
        return {tag_id: self._tags[tag_id] for tag_id in tag_ids if tag_id in self._tags}

    # --- Tag ↔ Item association ---

    def add_item_tag_link(self, item_id: UUID, tag_id: UUID) -> None:
        """Associate tag with item; idempotent."""
        already_linked = any(lnk.tag_id == tag_id and lnk.item_id == item_id for lnk in self._links)
        if not already_linked:
            self._links.append(ItemTagLink(tag_id=tag_id, item_id=item_id))

    def delete_item_tag_link(self, item_id: UUID, tag_id: UUID) -> bool:
        """Remove tag-item association; return True if it existed."""
        before = len(self._links)
        self._links = [lnk for lnk in self._links if not (lnk.tag_id == tag_id and lnk.item_id == item_id)]
        return len(self._links) < before

    def list_item_tag_links(
        self,
        *,
        item_ids: Collection[UUID] | None = None,
        tag_ids: Collection[UUID] | None = None,
    ) -> list[ItemTagLink]:
        """Return tag links, AND-filtered by either end, ordered by (item_id, tag_id)."""
        links = self._links
        if item_ids is not None:
            wanted_items = set(item_ids)
            links = [lnk for lnk in links if lnk.item_id in wanted_items]
        if tag_ids is not None:
            wanted_tags = set(tag_ids)
            links = [lnk for lnk in links if lnk.tag_id in wanted_tags]
        return sorted(links, key=lambda lnk: (lnk.item_id, lnk.tag_id))

    # --- Category parent links ---

    def save_category_parent_link(self, link: CategoryParentLink) -> None:
        """Upsert a category→parent relationship."""
        for i, existing in enumerate(self._category_parent_links):
            if existing.category_id == link.category_id and existing.parent_category_id == link.parent_category_id:
                self._category_parent_links[i] = link
                return
        self._category_parent_links.append(link)

    def list_category_parent_links(
        self,
        *,
        category_ids: Collection[UUID] | None = None,
        parent_category_ids: Collection[UUID] | None = None,
    ) -> list[CategoryParentLink]:
        """Return category parent links, optionally filtered by either end."""
        links = self._category_parent_links
        if category_ids is not None:
            wanted_children = set(category_ids)
            links = [lnk for lnk in links if lnk.category_id in wanted_children]
        if parent_category_ids is not None:
            wanted = set(parent_category_ids)
            links = [lnk for lnk in links if lnk.parent_category_id in wanted]
        return sorted(
            links,
            key=lambda lnk: (str(lnk.parent_category_id), lnk.sort_index, str(lnk.category_id)),
        )

    # --- Tag delete ---

    def delete_tag(self, tag_id: UUID) -> bool:
        """Delete tag and every link naming it; return True if it existed."""
        if tag_id not in self._tags:
            return False
        del self._tags[tag_id]
        self._drop_dangling_links()
        return True

    def _drop_dangling_links(self) -> None:
        """Drop every link that names a row not stored, as the file backends do."""
        self._links = [lnk for lnk in self._links if lnk.item_id in self._items and lnk.tag_id in self._tags]
        self._category_parent_links = [
            lnk
            for lnk in self._category_parent_links
            if lnk.category_id in self._categories and lnk.parent_category_id in self._categories
        ]
        self._item_parent_links = [
            lnk
            for lnk in self._item_parent_links
            if lnk.item_id in self._items and lnk.category_id in self._categories
        ]
        self._item_relation_links = [
            lnk
            for lnk in self._item_relation_links
            if lnk.source_item_id in self._items and lnk.target_item_id in self._items
        ]

    # --- Item → Category placement ---

    def save_item_parent_link(self, link: ItemParentLink) -> None:
        """Upsert item→category placement."""
        for i, existing in enumerate(self._item_parent_links):
            if existing.item_id == link.item_id and existing.category_id == link.category_id:
                self._item_parent_links[i] = link
                return
        self._item_parent_links.append(link)

    def list_item_parent_links(
        self,
        *,
        item_ids: Collection[UUID] | None = None,
        category_ids: Collection[UUID] | None = None,
    ) -> list[ItemParentLink]:
        """Return item→category placements in contract order, optionally filtered.

        The order is the port contract's: ``(category_id ASC, sort_index ASC,
        item_id ASC)``. An empty collection in either filter returns ``[]``;
        both filters together apply AND semantics.
        """
        links: list[ItemParentLink] = self._item_parent_links
        if item_ids is not None:
            wanted_items = set(item_ids)
            links = [lnk for lnk in links if lnk.item_id in wanted_items]
        if category_ids is not None:
            wanted = set(category_ids)
            links = [lnk for lnk in links if lnk.category_id in wanted]
        return sorted(
            links,
            key=lambda lnk: (str(lnk.category_id), lnk.sort_index, str(lnk.item_id)),
        )

    def delete_category_parent_link(self, category_id: UUID, parent_category_id: UUID) -> bool:
        """Delete a category→parent relationship; return True if found."""
        before = len(self._category_parent_links)
        self._category_parent_links = [
            lnk
            for lnk in self._category_parent_links
            if not (lnk.category_id == category_id and lnk.parent_category_id == parent_category_id)
        ]
        return len(self._category_parent_links) < before

    def delete_item_parent_link(self, item_id: UUID, category_id: UUID) -> bool:
        """Delete an item→category placement; return True if found."""
        before = len(self._item_parent_links)
        self._item_parent_links = [
            lnk for lnk in self._item_parent_links if not (lnk.item_id == item_id and lnk.category_id == category_id)
        ]
        return len(self._item_parent_links) < before

    # --- External-ID lookup ---

    def find_item_by_external_id(self, external_id: str) -> Item | None:
        """Return the item with the given external_id, or None."""
        return next((item for item in self._items.values() if item.external_id == external_id), None)

    def find_category_by_external_id(self, external_id: str) -> Category | None:
        """Return the category with the given external_id, or None."""
        return next((cat for cat in self._categories.values() if cat.external_id == external_id), None)

    def map_items_by_id(
        self,
        item_ids: Collection[UUID],
        *,
        enabled: bool | None = None,
    ) -> Mapping[UUID, Item]:
        """Return the items whose item_id is in item_ids; an identifier that names no stored item is left out."""
        result: dict[UUID, Item] = {}
        for item_id in item_ids:
            item = self._items.get(item_id)
            if item is not None and (enabled is None or item.enabled == enabled):
                result[item_id] = item
        return result

    def map_categories_by_id(
        self,
        category_ids: Collection[UUID],
        *,
        enabled: bool | None = None,
    ) -> Mapping[UUID, Category]:
        """Return the categories whose category_id is in category_ids; an identifier that names none is left out."""
        result: dict[UUID, Category] = {}
        for category_id in category_ids:
            category = self._categories.get(category_id)
            if category is not None and (enabled is None or category.enabled == enabled):
                result[category_id] = category
        return result

    def map_items_by_external_id(
        self,
        external_ids: Collection[str],
        *,
        enabled: bool | None = None,
    ) -> Mapping[str, Item]:
        """Return items whose external_id is in external_ids."""
        return bulk_lookup_by_external_id(self._items, external_ids, enabled)

    def map_categories_by_external_id(
        self,
        external_ids: Collection[str],
        *,
        enabled: bool | None = None,
    ) -> Mapping[str, Category]:
        """Return categories whose external_id is in external_ids."""
        return bulk_lookup_by_external_id(self._categories, external_ids, enabled)

    def find_item_by_slug(self, slug: str) -> Item | None:
        """Return the item with the given slug, or None."""
        return next((i for i in self._items.values() if i.slug == slug), None)

    def find_category_by_slug(self, slug: str) -> Category | None:
        """Return the category with the given slug, or None."""
        return next((c for c in self._categories.values() if c.slug == slug), None)

    # --- Item relation links ---

    def save_item_relation_link(self, link: ItemRelationLink) -> None:
        """Upsert a directed item-to-item relation."""
        for i, existing in enumerate(self._item_relation_links):
            if (
                existing.source_item_id == link.source_item_id
                and existing.target_item_id == link.target_item_id
                and existing.relation_type == link.relation_type
            ):
                self._item_relation_links[i] = link
                return
        self._item_relation_links.append(link)

    def list_item_relation_links(
        self,
        item_id: UUID,
        *,
        relation_types: Collection[str] | None = None,
        direction: Literal["outgoing", "incoming", "both"] = "outgoing",
    ) -> list[ItemRelationLink]:
        """Return item relation links for the given item."""
        if direction == "outgoing":
            result = [lnk for lnk in self._item_relation_links if lnk.source_item_id == item_id]
        elif direction == "incoming":
            result = [lnk for lnk in self._item_relation_links if lnk.target_item_id == item_id]
        else:  # "both"
            result = [lnk for lnk in self._item_relation_links if item_id in (lnk.source_item_id, lnk.target_item_id)]
        if relation_types:
            type_set = set(relation_types)
            result = [lnk for lnk in result if lnk.relation_type in type_set]
        # The port orders every direction by `(sort_index ASC, source_item_id ASC, target_item_id ASC)`,
        # which tests/adapters/repositories/test_repository_contract.py asserts.
        return sorted(result, key=lambda lnk: (lnk.sort_index, str(lnk.source_item_id), str(lnk.target_item_id)))

    def delete_item_relation_link(
        self,
        source_item_id: UUID,
        target_item_id: UUID,
        relation_type: str,
    ) -> bool:
        """Delete the specific directed relation; return True if found."""
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
        return len(self._item_relation_links) < before

    def list_item_relation_links_batch(
        self,
        item_ids: Collection[UUID],
        *,
        relation_types: Collection[str] | None = None,
        direction: Literal["outgoing", "incoming", "both"] = "outgoing",
    ) -> list[ItemRelationLink]:
        """Return relation links for many items in a single pass, by direction."""
        id_set = set(item_ids)
        if not id_set:
            return []
        if direction == "outgoing":
            result = [lnk for lnk in self._item_relation_links if lnk.source_item_id in id_set]
        elif direction == "incoming":
            result = [lnk for lnk in self._item_relation_links if lnk.target_item_id in id_set]
        else:
            result = [
                lnk
                for lnk in self._item_relation_links
                if lnk.source_item_id in id_set or lnk.target_item_id in id_set
            ]
        if relation_types:
            type_set = set(relation_types)
            result = [lnk for lnk in result if lnk.relation_type in type_set]
        if direction == "outgoing":
            return sorted(
                result,
                key=lambda lnk: (str(lnk.source_item_id), lnk.relation_type, lnk.sort_index, str(lnk.target_item_id)),
            )
        if direction == "incoming":
            return sorted(
                result,
                key=lambda lnk: (str(lnk.target_item_id), lnk.relation_type, lnk.sort_index, str(lnk.source_item_id)),
            )
        return sorted(result, key=lambda lnk: (lnk.sort_index, str(lnk.source_item_id), str(lnk.target_item_id)))

    # --- Configuration introspection ---

    def describe(self) -> RepositoryInfo:
        """Return a fixed description identifying this as an in-memory test repository."""
        return RepositoryInfo(backend=type(self).__name__, path=None, diagnostics={})

    @property
    def config_summary(self) -> str:
        """A fixed description identifying this as an in-memory test repository."""
        return "InMemoryRepository (test)"


# The Django parameter carries the ``django_db`` mark, so pytest-django creates the test
# database for any selection of tests, including one file run alone.
DJANGO_PARAM: Final = pytest.param("django", marks=pytest.mark.django_db)

# The four backends a parametrized fixture runs over.
BACKEND_PARAMS: Final = ("in_memory", "json", "yaml", DJANGO_PARAM)


def _build_repository(request: pytest.FixtureRequest, tmp_path: Path) -> TaxomeshRepositoryBase:
    """Return a fresh repository for the backend named by ``request.param``."""
    if request.param == "in_memory":
        return InMemoryRepository()
    if request.param == "json":
        return JsonRepository(tmp_path / "test.json")
    if request.param == "yaml":
        return YamlRepository(tmp_path / "test.yaml")
    # django
    pytest.importorskip("django", reason="django not installed")
    from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

    return DjangoRepository()


@pytest.fixture(params=BACKEND_PARAMS)
def service(request: pytest.FixtureRequest, tmp_path: Path) -> TaxomeshService:
    """Return a TaxomeshService backed by a fresh repository for each backend.

    Parametrized over InMemoryRepository, JsonRepository, YamlRepository, and
    DjangoRepository (optional — skips when Django is not configured) so that every
    behavioral test runs once per backend, ensuring parity.
    """
    return TaxomeshService(repository=_build_repository(request, tmp_path))


class CountingRepository:
    """Wrap any backend and count the repository reads a service call issues.

    One repository call counts as one storage read, which holds against
    ``CaptureQueriesContext`` on Django. Delegation is generic, so a single set of
    exact constants holds on every backend. ``RecordingRepository`` in
    ``test_service_no_full_scan.py`` cannot do that: it subclasses ``InMemoryRepository``
    and overrides a fixed list of eight methods, so it counts nothing on the file or Django
    backends.

    A read is any callable whose name starts with ``get_``, ``list_``, ``find_`` or ``map_``.
    The port's single-row lookups are ``find_*`` and its keyed batch reads ``map_*``: without
    those prefixes the proxy would count none of them, and every read-count assertion would
    pass while measuring nothing. Configuration introspection needs no exclusion: the
    ``config_summary`` property and ``describe()`` carry no read prefix.
    """

    _READ_PREFIXES = ("get_", "list_", "find_", "map_")

    def __init__(self, wrapped: TaxomeshRepositoryBase) -> None:
        self._wrapped = wrapped
        self.calls: list[str] = []

    @property
    def total(self) -> int:
        """Total storage reads recorded since the last :meth:`reset`."""
        return len(self.calls)

    def count_of(self, name: str) -> int:
        """Return how many times the named read was issued."""
        return self.calls.count(name)

    def reset(self) -> None:
        """Discard recorded calls, so a measurement excludes fixture setup."""
        self.calls.clear()

    # Any: a proxy forwards whatever attribute the wrapped repository has, called with whatever it takes.
    def __getattr__(self, name: str) -> Any:
        # Only reached for names not found on the instance or class, so `_wrapped` and
        # `calls` (set in __init__) cannot recurse. Writes and `atomic()` fall through
        # untouched — they are not reads. `getattr` evaluates a property here, so
        # `config_summary` arrives as a plain str and the non-callable guard returns it.
        attr = getattr(self._wrapped, name)
        if not callable(attr) or not name.startswith(self._READ_PREFIXES):
            return attr

        # Any: the forwarded read takes and returns whatever the port member does.
        def proxy(*args: Any, **kwargs: Any) -> Any:
            self.calls.append(name)
            return attr(*args, **kwargs)

        return proxy


@dataclass(frozen=True, slots=True)
class CountedService:
    """A service whose storage reads can be counted, and the counter itself."""

    service: TaxomeshService
    reads: CountingRepository

    def cold(self) -> None:
        """Drop the service's cache, both search corpora and every recorded read, so the next measurement is cold."""
        self.service._cache.clear()
        self.service._item_corpus.invalidate()
        self.service._category_corpus.invalidate()
        self.reads.reset()


@pytest.fixture(params=BACKEND_PARAMS)
def counting_service(request: pytest.FixtureRequest, tmp_path: Path) -> CountedService:
    """Return a read-counting service for each backend.

    Parametrized exactly like :func:`service`, so a read-count assertion written once is
    asserted on all four backends.
    """
    counter = CountingRepository(_build_repository(request, tmp_path))
    return CountedService(service=TaxomeshService(repository=counter), reads=counter)
