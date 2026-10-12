"""Serialization of the shapes a recursive serializer could not survive.

A serializer recursing over ``node.children`` would recurse without bound on a cycle present in
stored data. Cycle prevention guards the write path, but rows also arrive by direct SQL, a migration
or a restored backup.

``graph_to_dict``'s guard is **path-local**, and that distinction is load-bearing. The recorded
baseline emits a shared subtree once per path and those bytes must not move, so a global set is not
merely a different choice: it changes the recorded output. ``TaxomeshGraph.walk``'s visited set is
global for the opposite reason: a walk yields each node exactly once. The two guards must not be
conflated.

**Why these tests assert an exact emitted count.** Byte parity cannot protect the guard: a
serializer with the exit sentinel pushed *after* its children — which silently disables the guard —
and a serializer with no guard at all both reproduce the recorded baseline byte-for-byte. Nor can
termination alone protect it, because the emitted-node budget terminates the broken variant too,
just later. The exact count is the only assertion that separates a working guard from a
budget-rescued hang.
"""

from typing import Any
from uuid import UUID

import pytest

from taxomesh.contrib.api.errors import TaxomeshGraphTooLargeError
from taxomesh.contrib.api.serializers import MAX_EMITTED_NODES, graph_to_dict
from taxomesh.domain.graph import TaxomeshGraph
from taxomesh.domain.models import Category

# A → B → C → A. The serializer emits A, B, C, then A a second time where the cycle closes,
# without descending from it: four dicts, and no fifth.
CYCLE_EMITTED_NODES = 4


def _uuid(n: int) -> UUID:
    """Return a fixed, readable UUID so a failure names a recognisable category."""
    return UUID(f"00000000-0000-0000-0000-{n:012d}")


def _category(n: int, name: str) -> Category:
    """Build a Category with a fixed id."""
    return Category(category_id=_uuid(n), name=name, slug=name.lower())


def build_cyclic_graph() -> TaxomeshGraph:
    """Assemble a graph whose stored links form a cycle: ``A → B → C → A``.

    No public write path produces this — ``check_no_cycle`` rejects it. It is assembled from flat
    maps directly, which is how such rows actually reach a repository.
    """
    first, second, third = _category(1, "A"), _category(2, "B"), _category(3, "C")
    return TaxomeshGraph(
        categories={category.category_id: category for category in (first, second, third)},
        children={
            first.category_id: [second.category_id],
            second.category_id: [third.category_id],
            third.category_id: [first.category_id],
        },
        parents={
            second.category_id: [first.category_id],
            third.category_id: [second.category_id],
            first.category_id: [third.category_id],
        },
        items={},
        roots=[first.category_id],
    )


# Any: a serialized payload is heterogeneous JSON (str, bool, list, nested dict)
def count_emitted(payload: dict[str, Any]) -> int:
    """Count the node dicts in a serialized payload, iteratively.

    Iterative on purpose: a recursive count would raise on exactly the shapes this file exists to
    serialize, for reasons that have nothing to do with what is being tested.
    """
    stack: list[dict[str, Any]] = list(payload["roots"])
    total = 0
    while stack:
        node = stack.pop()
        total += 1
        stack.extend(node["children"])
    return total


class TestStoredCycle:
    """A cycle in stored data terminates instead of recursing without bound."""

    def test_serializing_a_stored_cycle_terminates(self) -> None:
        """A stored cycle serializes and returns, where a recursive serializer would never return."""
        payload = graph_to_dict(build_cyclic_graph())

        assert count_emitted(payload) == CYCLE_EMITTED_NODES

    def test_the_cycle_is_cut_by_emitting_the_repeat_without_descending(self) -> None:
        """The repeated category is emitted, so its parent's child list stays complete.

        Every stored child link produces an entry in its parent's ``children`` — for cyclic data as
        for any other. Descent is what stops, not emission: the repeat carries no children, and the
        children it does have were already emitted higher on the same path.
        """
        payload = graph_to_dict(build_cyclic_graph())

        first = payload["roots"][0]
        second = first["children"][0]
        third = second["children"][0]
        repeated = third["children"][0]

        assert repeated["category"]["category_id"] == str(_uuid(1))
        assert repeated["children"] == []

    def test_a_shared_branch_outside_a_cycle_is_still_emitted_once_per_path(self) -> None:
        """Guard the guard: the cycle fix must not turn into a global visited set.

        A global set would suppress the second emission of a shared branch, changing the recorded
        bytes. This is the same property the recorded baseline holds, asserted here on a
        hand-built shape so a failure points at the guard rather than at a fixture.
        """
        top, left, right = _category(1, "Top"), _category(2, "Left"), _category(3, "Right")
        shared = _category(4, "Shared")
        graph = TaxomeshGraph(
            categories={c.category_id: c for c in (top, left, right, shared)},
            children={
                top.category_id: [left.category_id, right.category_id],
                left.category_id: [shared.category_id],
                right.category_id: [shared.category_id],
            },
            parents={
                left.category_id: [top.category_id],
                right.category_id: [top.category_id],
                shared.category_id: [left.category_id, right.category_id],
            },
            items={},
            roots=[top.category_id],
        )

        payload = graph_to_dict(graph)

        # Top, Left, Shared, Right, Shared — the shared branch once under each parent.
        assert count_emitted(payload) == 5


def build_stacked_diamonds(levels: int) -> TaxomeshGraph:
    """Assemble ``levels`` stacked diamonds: the shape whose emission grows as ``2^(levels+2)-3``.

    Every link passes cycle detection, so ordinary ``add_parent`` calls reach this shape. Each
    level hangs two categories off the current one and rejoins them into a single child, which
    doubles the number of paths reaching everything below it.

    Args:
        levels: How many diamonds to stack.

    Returns:
        A graph of ``3 * levels + 1`` stored categories with a single root.
    """
    categories: dict[UUID, Category] = {}
    children: dict[UUID, list[UUID]] = {}
    parents: dict[UUID, list[UUID]] = {}

    def add() -> UUID:
        category_id = _uuid(len(categories) + 1)
        categories[category_id] = Category(category_id=category_id, name=f"C{len(categories) + 1}")
        return category_id

    root = add()
    current = root
    for _ in range(levels):
        left, right, join = add(), add(), add()
        children[current] = [left, right]
        children[left] = [join]
        children[right] = [join]
        parents[left] = [current]
        parents[right] = [current]
        parents[join] = [left, right]
        current = join

    return TaxomeshGraph(categories=categories, children=children, parents=parents, items={}, roots=[root])


class TestEmittedNodeBudget:
    """Emission that grows exponentially raises rather than running unbounded."""

    def test_the_budget_is_reached_by_a_few_dozen_categories(self) -> None:
        """The honest cost of the budget, pinned: this is not a huge taxonomy.

        Fifteen stacked diamonds is 46 stored categories and 131 069 emitted nodes. The graph
        itself holds 46 — the explosion is entirely in the per-path emission the document shape
        requires.
        """
        graph = build_stacked_diamonds(15)

        assert len(graph) == 46

        with pytest.raises(TaxomeshGraphTooLargeError) as raised:
            graph_to_dict(graph)

        assert str(MAX_EMITTED_NODES) in str(raised.value)

    def test_a_shape_just_under_the_budget_still_serializes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Guard the guard: the budget must not fire early enough to break ordinary data.

        Monkeypatched rather than built, because a graph emitting exactly ``MAX_EMITTED_NODES``
        is a second or so of pure emission to prove a boundary that is arithmetic.
        """
        monkeypatch.setattr("taxomesh.contrib.api.serializers.MAX_EMITTED_NODES", 5)

        # Top, Left, Shared, Right, Shared — five, exactly at the limit.
        graph = build_stacked_diamonds(1)

        assert count_emitted(graph_to_dict(graph)) == 5

    def test_one_node_past_the_budget_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """And the node after the last permitted one is refused."""
        monkeypatch.setattr("taxomesh.contrib.api.serializers.MAX_EMITTED_NODES", 4)

        with pytest.raises(TaxomeshGraphTooLargeError):
            graph_to_dict(build_stacked_diamonds(1))

    def test_the_budget_is_counted_across_roots_not_per_root(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A multi-root graph cannot emit the budget once per root.

        Counting per root would let an N-root taxonomy emit N times the budget, which is the
        unbounded case the budget exists to close.
        """
        monkeypatch.setattr("taxomesh.contrib.api.serializers.MAX_EMITTED_NODES", 3)

        first, second, third, fourth = (_category(n, f"R{n}") for n in (1, 2, 3, 4))
        graph = TaxomeshGraph(
            categories={c.category_id: c for c in (first, second, third, fourth)},
            children={},
            parents={},
            items={},
            roots=[c.category_id for c in (first, second, third, fourth)],
        )

        with pytest.raises(TaxomeshGraphTooLargeError):
            graph_to_dict(graph)
