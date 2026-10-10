"""``search`` takes the three-state enabled filter on both collections.

``enabled`` is ``bool | None`` on both searches, matching ``list`` and ``roots``: ``True`` enabled
only, ``False`` disabled only, ``None`` everything, ranked together in one result rather than in
two calls the caller has to merge.

Each of the four load paths (items with and without a category, recursive or not, and categories
with and without a parent) must pass the filter into the load rather than filter after it. A path
that loaded with ``list``'s own ``enabled=True`` default and then asked those rows for
``enabled is False`` would answer ``[]`` for every disabled search, which is why every path is
asserted under every state.

The cases run on all four backends. Sets are compared rather than sequences: no order is promised
across backends.
"""

from collections.abc import Sequence
from typing import NamedTuple
from uuid import UUID

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Category, Item


class _Taxonomy(NamedTuple):
    """Identifiers of the fixture rows, all of which match the query ``tango``."""

    parent_id: UUID
    child_id: UUID
    dim_id: UUID
    on_id: UUID
    off_id: UUID


def _build(service: TaxomeshService) -> _Taxonomy:
    """Two enabled categories and one disabled one; two items, one of each state.

    ``Tango Child`` and ``Tango Dim`` are both children of ``Tango Parent``, so a
    ``parent`` search sees one row of each state. Both items sit in ``Tango Child``, so a
    ``category`` search sees one of each directly and a recursive search from the parent
    reaches the same pair through the subtree.
    """
    parent = service.categories.create(name="Tango Parent")
    child = service.categories.create(name="Tango Child")
    dim = service.categories.create(name="Tango Dim")
    service.categories.add_parent(child.category_id, parent.category_id)
    service.categories.add_parent(dim.category_id, parent.category_id)
    service.categories.update(dim.category_id, enabled=False)

    on = service.items.create(name="Tango On")
    off = service.items.create(name="Tango Off")
    service.items.place_in(on.item_id, child.category_id)
    service.items.place_in(off.item_id, child.category_id)
    service.items.update(off.item_id, enabled=False)

    return _Taxonomy(
        parent_id=parent.category_id,
        child_id=child.category_id,
        dim_id=dim.category_id,
        on_id=on.item_id,
        off_id=off.item_id,
    )


def _names(rows: Sequence[Category] | Sequence[Item]) -> set[str]:
    """The names in a result, as a set — ordering is not promised across backends."""
    return {row.name for row in rows}


class TestCategorySearchUnscoped:
    """The corpus path — ``parent`` not given."""

    def test_true_returns_enabled_only(self, service: TaxomeshService) -> None:
        _build(service)

        assert _names(service.categories.search("tango", enabled=True)) == {"Tango Parent", "Tango Child"}

    def test_false_returns_disabled_only(self, service: TaxomeshService) -> None:
        _build(service)

        assert _names(service.categories.search("tango", enabled=False)) == {"Tango Dim"}

    def test_none_returns_both_states_ranked_together(self, service: TaxomeshService) -> None:
        """The newly reachable state: one ranked result carrying both, not two calls merged."""
        _build(service)

        results = service.categories.search("tango", enabled=None)

        assert _names(results) == {"Tango Parent", "Tango Child", "Tango Dim"}


class TestCategorySearchScopedToAParent:
    """The ``parent`` path — candidates come from ``list``, which already took ``None``."""

    def test_true_returns_enabled_only(self, service: TaxomeshService) -> None:
        tree = _build(service)

        results = service.categories.search("tango", parent=tree.parent_id, enabled=True)

        assert _names(results) == {"Tango Child"}

    def test_false_returns_disabled_only(self, service: TaxomeshService) -> None:
        tree = _build(service)

        results = service.categories.search("tango", parent=tree.parent_id, enabled=False)

        assert _names(results) == {"Tango Dim"}

    def test_none_returns_both_states_ranked_together(self, service: TaxomeshService) -> None:
        """This branch hands ``None`` to ``list``, which answers both states."""
        tree = _build(service)

        results = service.categories.search("tango", parent=tree.parent_id, enabled=None)

        assert _names(results) == {"Tango Child", "Tango Dim"}


class TestItemSearchUnscoped:
    """The corpus path — ``category`` not given."""

    def test_true_returns_enabled_only(self, service: TaxomeshService) -> None:
        _build(service)

        assert _names(service.items.search("tango", enabled=True)) == {"Tango On"}

    def test_false_returns_disabled_only(self, service: TaxomeshService) -> None:
        _build(service)

        assert _names(service.items.search("tango", enabled=False)) == {"Tango Off"}

    def test_none_returns_both_states_ranked_together(self, service: TaxomeshService) -> None:
        _build(service)

        results = service.items.search("tango", enabled=None)

        assert _names(results) == {"Tango On", "Tango Off"}


class TestItemSearchScopedToACategory:
    """The candidate path, direct — ``category`` given, ``recursive`` left off.

    A post-filter over rows loaded with ``enabled=True`` would answer ``[]`` for ``enabled=False``
    here, for every fixture.
    """

    def test_true_returns_enabled_only(self, service: TaxomeshService) -> None:
        tree = _build(service)

        results = service.items.search("tango", category=tree.child_id, enabled=True)

        assert _names(results) == {"Tango On"}

    def test_false_returns_disabled_only(self, service: TaxomeshService) -> None:
        """The repair: the loader filters, so a disabled row reaches the ranking at all."""
        tree = _build(service)

        results = service.items.search("tango", category=tree.child_id, enabled=False)

        assert _names(results) == {"Tango Off"}

    def test_none_returns_both_states_ranked_together(self, service: TaxomeshService) -> None:
        tree = _build(service)

        results = service.items.search("tango", category=tree.child_id, enabled=None)

        assert _names(results) == {"Tango On", "Tango Off"}


class TestItemSearchScopedRecursively:
    """The candidate path, recursive — the subtree branch, which hardcoded ``enabled=True``."""

    def test_true_returns_enabled_only(self, service: TaxomeshService) -> None:
        tree = _build(service)

        results = service.items.search("tango", category=tree.parent_id, recursive=True, enabled=True)

        assert _names(results) == {"Tango On"}

    def test_false_returns_disabled_only(self, service: TaxomeshService) -> None:
        """The same repair on the branch that reached the rows through ``map_items_by_id``."""
        tree = _build(service)

        results = service.items.search("tango", category=tree.parent_id, recursive=True, enabled=False)

        assert _names(results) == {"Tango Off"}

    def test_none_returns_both_states_ranked_together(self, service: TaxomeshService) -> None:
        tree = _build(service)

        results = service.items.search("tango", category=tree.parent_id, recursive=True, enabled=None)

        assert _names(results) == {"Tango On", "Tango Off"}
