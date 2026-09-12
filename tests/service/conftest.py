"""Shared pytest fixtures for the service test suite."""

import contextlib
from collections.abc import Collection
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import pytest

from taxomesh.adapters.repositories._external_id import bulk_lookup_by_external_id
from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YAMLRepository
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import (
    Category,
    CategoryParentLink,
    Item,
    ItemParentLink,
    ItemRelationLink,
    ItemTagLink,
    Tag,
)
from taxomesh.utils.memoize import clear_all_caches


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

    def save_category(self, category: Category) -> None:
        """Insert or update a category."""
        self._categories[category.category_id] = category

    def get_category(self, category_id: UUID) -> Category | None:
        """Return category by id, or None."""
        return self._categories.get(category_id)

    def list_categories(self, *, enabled: bool | None = True) -> list[Category]:
        """Return categories, filtered by enabled state."""
        cats = list(self._categories.values())
        if enabled is not None:
            cats = [c for c in cats if c.enabled == enabled]
        return cats

    def delete_category(self, category_id: UUID) -> bool:
        """Delete category; return True if it existed."""
        if category_id not in self._categories:
            return False
        del self._categories[category_id]
        return True

    # --- Item ---

    def save_item(self, item: Item) -> None:
        """Insert or update an item."""
        self._items[item.item_id] = item

    def get_item(self, item_id: UUID) -> Item | None:
        """Return item by id, or None."""
        return self._items.get(item_id)

    def list_items(self, *, enabled: bool | None = True) -> list[Item]:
        """Return items, filtered by enabled state."""
        items = list(self._items.values())
        if enabled is not None:
            items = [i for i in items if i.enabled == enabled]
        return items

    def delete_item(self, item_id: UUID) -> bool:
        """Delete item; return True if it existed. Cascades relation links."""
        if item_id not in self._items:
            return False
        del self._items[item_id]
        self._item_relation_links = [
            lnk for lnk in self._item_relation_links if item_id not in {lnk.source_item_id, lnk.target_item_id}
        ]
        return True

    # --- Tag ---

    def save_tag(self, tag: Tag) -> None:
        """Insert or update a tag."""
        self._tags[tag.tag_id] = tag

    def get_tag(self, tag_id: UUID) -> Tag | None:
        """Return tag by id, or None."""
        return self._tags.get(tag_id)

    def list_tags(self) -> list[Tag]:
        """Return all tags."""
        return list(self._tags.values())

    # --- Tag ↔ Item association ---

    def assign_tag(self, tag_id: UUID, item_id: UUID) -> None:
        """Associate tag with item; idempotent."""
        already_linked = any(lnk.tag_id == tag_id and lnk.item_id == item_id for lnk in self._links)
        if not already_linked:
            self._links.append(ItemTagLink(tag_id=tag_id, item_id=item_id))

    def remove_tag(self, tag_id: UUID, item_id: UUID) -> bool:
        """Remove tag-item association; return True if it existed."""
        before = len(self._links)
        self._links = [lnk for lnk in self._links if not (lnk.tag_id == tag_id and lnk.item_id == item_id)]
        return len(self._links) < before

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
        parent_category_ids: Collection[UUID] | None = None,
    ) -> list[CategoryParentLink]:
        """Return category parent links, optionally filtered by parent."""
        links = self._category_parent_links
        if parent_category_ids is not None:
            wanted = set(parent_category_ids)
            links = [lnk for lnk in links if lnk.parent_category_id in wanted]
        return sorted(
            links,
            key=lambda lnk: (str(lnk.parent_category_id), lnk.sort_index, str(lnk.category_id)),
        )

    # --- Tag delete ---

    def delete_tag(self, tag_id: UUID) -> bool:
        """Delete tag; return True if it existed."""
        if tag_id not in self._tags:
            return False
        del self._tags[tag_id]
        return True

    # --- Item → Category placement ---

    def save_item_parent_link(self, link: ItemParentLink) -> None:
        """Upsert item→category placement."""
        for existing in self._item_parent_links:
            if existing.item_id == link.item_id and existing.category_id == link.category_id:
                existing.sort_index = link.sort_index
                return
        self._item_parent_links.append(link)

    def list_item_parent_links(
        self,
        *,
        item_id: UUID | None = None,
        category_ids: Collection[UUID] | None = None,
    ) -> list[ItemParentLink]:
        """Return item→category placements in contract order, optionally filtered.

        Ordering follows the port contract: ``(category_id ASC, sort_index ASC,
        item_id ASC)``. An empty ``category_ids`` collection returns ``[]``;
        both filters together apply AND semantics.
        """
        links: list[ItemParentLink] = self._item_parent_links
        if item_id is not None:
            links = [lnk for lnk in links if lnk.item_id == item_id]
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

    def get_item_by_external_id(self, external_id: str) -> Item | None:
        """Return the item with the given external_id, or None."""
        return next((item for item in self._items.values() if item.external_id == external_id), None)

    def get_category_by_external_id(self, external_id: str) -> Category | None:
        """Return the category with the given external_id, or None."""
        return next((cat for cat in self._categories.values() if cat.external_id == external_id), None)

    def get_items_by_ids(
        self,
        item_ids: Collection[UUID],
        *,
        enabled: bool | None = None,
    ) -> dict[UUID, Item]:
        """Return items whose item_id is in item_ids; missing IDs silently absent."""
        result: dict[UUID, Item] = {}
        for item_id in item_ids:
            item = self._items.get(item_id)
            if item is not None and (enabled is None or item.enabled == enabled):
                result[item_id] = item
        return result

    def get_categories_by_ids(
        self,
        category_ids: Collection[UUID],
        *,
        enabled: bool | None = None,
    ) -> dict[UUID, Category]:
        """Return categories by id, missing ids silently absent."""
        result: dict[UUID, Category] = {}
        for category_id in category_ids:
            category = self._categories.get(category_id)
            if category is not None and (enabled is None or category.enabled == enabled):
                result[category_id] = category
        return result

    def get_items_by_external_ids(
        self,
        external_ids: Collection[str],
        *,
        enabled: bool | None = None,
    ) -> dict[str, Item]:
        """Return items whose external_id is in external_ids."""
        return bulk_lookup_by_external_id(self._items, external_ids, enabled)

    def get_categories_by_external_ids(
        self,
        external_ids: Collection[str],
        *,
        enabled: bool | None = None,
    ) -> dict[str, Category]:
        """Return categories whose external_id is in external_ids."""
        return bulk_lookup_by_external_id(self._categories, external_ids, enabled)

    def get_item_by_slug(self, slug: str) -> Item | None:
        """Return the item with the given slug, or None."""
        return next((i for i in self._items.values() if i.slug == slug), None)

    def get_category_by_slug(self, slug: str) -> Category | None:
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
        relation_type: str | None = None,
        direction: Literal["outgoing", "incoming", "both"] = "outgoing",
    ) -> list[ItemRelationLink]:
        """Return item relation links for the given item."""
        if direction == "outgoing":
            result = [lnk for lnk in self._item_relation_links if lnk.source_item_id == item_id]
        elif direction == "incoming":
            result = [lnk for lnk in self._item_relation_links if lnk.target_item_id == item_id]
        else:  # "both"
            result = [lnk for lnk in self._item_relation_links if item_id in (lnk.source_item_id, lnk.target_item_id)]
        if relation_type is not None:
            result = [lnk for lnk in result if lnk.relation_type == relation_type]
        return result

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

    def list_item_relation_links_for_items(
        self,
        item_ids: Collection[UUID],
        *,
        direction: Literal["outgoing", "incoming", "both"] = "outgoing",
        relation_types: Collection[str] | None = None,
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

    def get_debug_info(self) -> dict[str, Any]:
        """Return a fixed description identifying this as an in-memory test repository."""
        return {"type": "InMemoryRepository"}

    def get_config_summary(self) -> str:
        """Return a fixed description identifying this as an in-memory test repository."""
        return "InMemoryRepository (test)"


def _build_repository(request: pytest.FixtureRequest, tmp_path: Path) -> Any:
    """Return a fresh repository for the backend named by ``request.param``."""
    if request.param == "in_memory":
        return InMemoryRepository()
    if request.param == "json":
        return JsonRepository(tmp_path / "test.json")
    if request.param == "yaml":
        return YAMLRepository(tmp_path / "test.yaml")
    # django
    pytest.importorskip("django", reason="django not installed")
    request.getfixturevalue("db")
    from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

    return DjangoRepository()


@pytest.fixture(
    params=["in_memory", "json", "yaml", "django"],
    ids=["in_memory", "json", "yaml", "django"],
)
def service(request: pytest.FixtureRequest, tmp_path: Path) -> TaxomeshService:
    """Return a TaxomeshService backed by a fresh repository for each backend.

    Parametrized over InMemoryRepository, JsonRepository, YAMLRepository, and
    DjangoRepository (optional — skips when Django is not configured) so that every
    behavioral test runs once per backend, ensuring parity.
    """
    return TaxomeshService(repository=_build_repository(request, tmp_path))


class CountingRepository:
    """Wrap any backend and count the repository reads a service call issues.

    One repository call counts as one storage read — the equivalence spec 060 established
    against ``CaptureQueriesContext`` on Django. Delegation is generic, so a single set of
    exact constants holds on every backend. ``RecordingRepository`` in
    ``test_service_no_full_scan.py`` cannot do that: it subclasses ``InMemoryRepository``
    and overrides a fixed list of eight methods, so it counts nothing on the file or Django
    backends.

    A read is any callable whose name starts with ``get_`` or ``list_``, minus
    ``get_config_summary``, which reports configuration rather than reading storage.
    """

    _READ_PREFIXES = ("get_", "list_")
    _NOT_READS = frozenset({"get_config_summary"})

    def __init__(self, wrapped: Any) -> None:
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

    def __getattr__(self, name: str) -> Any:
        # Only reached for names not found on the instance or class, so `_wrapped` and
        # `calls` (set in __init__) cannot recurse. Writes and `atomic()` fall through
        # untouched — they are not reads.
        attr = getattr(self._wrapped, name)
        if not callable(attr) or not name.startswith(self._READ_PREFIXES) or name in self._NOT_READS:
            return attr

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
        """Drop every cache entry and every recorded read, so the next measurement is cold."""
        clear_all_caches()
        self.reads.reset()


@pytest.fixture(
    params=["in_memory", "json", "yaml", "django"],
    ids=["in_memory", "json", "yaml", "django"],
)
def counting_service(request: pytest.FixtureRequest, tmp_path: Path) -> CountedService:
    """Return a read-counting service for each backend.

    Parametrized exactly like :func:`service`, so a read-count assertion written once is
    asserted on all four backends (spec 061 FR-011).
    """
    counter = CountingRepository(_build_repository(request, tmp_path))
    return CountedService(service=TaxomeshService(repository=counter), reads=counter)


@pytest.fixture
def tmp_json_path(tmp_path: Path) -> Path:
    """Return a temporary file path for JsonRepository tests.

    The file does not exist yet; JsonRepository must create it.
    """
    return tmp_path / "taxomesh_test.json"
