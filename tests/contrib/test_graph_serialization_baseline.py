"""Recorded serializer output, pinned byte for byte.

Ordinary data serializes to exactly the recorded bytes: this file records what ``graph_to_dict``
emits and fails if a single character moves.

The recorded taxonomy is deliberately **not** a plain tree. It contains a category reachable
through two parents:

* The graph holds each category exactly once: ``Shared`` is **one** node, reached from both
  parents.
* The serializer emits ``children`` per path, so it emits that subtree **once per path**, which
  is what the bytes below record.

Storage does not duplicate; emission does. A guard that suppressed re-emission of an already-seen
node *would* change this output, and a guard that only breaks cycles does not. The serializer's
guard is *path-local*: it holds only the ancestors of the node being emitted, so a shared subtree
is still emitted once per path and the bytes stay as recorded.

That is why this file cannot be the only guard on the guard: a serializer whose exit
sentinel is pushed in the wrong order, and one with no cycle guard at all, both reproduce these
bytes exactly. Termination on a stored cycle is pinned by
``tests/contrib/test_graph_serialization_limits.py``, which asserts an exact emitted count for
that reason.

The graph is assembled from domain objects with fixed identifiers rather than through
``TaxomeshService``, so the bytes do not depend on ``uuid4`` or on audit timestamps. It is built
through the same flat constructor the service uses — there is no test-only way to make one.
This is a test of the serializer.
"""

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from taxomesh.contrib.api.serializers import graph_to_dict
from taxomesh.domain.graph import TaxomeshGraph
from taxomesh.domain.models import Category, Item

BASELINE = Path(__file__).parent / "fixtures" / "graph_serialization_baseline.json"


def _uuid(n: int) -> UUID:
    """Return a fixed, readable UUID so the recorded bytes never depend on ``uuid4``."""
    return UUID(f"00000000-0000-0000-0000-{n:012d}")


def _category(n: int, name: str) -> Category:
    """Build a Category with a fixed id and default audit fields."""
    return Category(category_id=_uuid(n), name=name, slug=name.lower())


def _item(n: int, name: str) -> Item:
    """Build an Item with a fixed id and default audit fields."""
    return Item(item_id=_uuid(n), name=name, slug=name.lower())


def build_reference_graph() -> TaxomeshGraph:
    """Assemble the reference taxonomy from flat maps, exactly as the service assembles one.

    Shape::

        Alpha            Beta
          └─ Shared        └─ Shared      <- the SAME category, two parents
               └─ Leaf          └─ Leaf

    ``Shared`` and ``Leaf`` are **one node each**, reached from both parents. The
    duplication in the recorded bytes comes from the serializer's own per-path emission, not
    from the graph.
    """
    alpha = _category(1, "Alpha")
    beta = _category(2, "Beta")
    shared = _category(3, "Shared")
    leaf = _category(4, "Leaf")

    first = _item(10, "First")
    second = _item(11, "Second")

    return TaxomeshGraph(
        categories={category.category_id: category for category in (alpha, beta, shared, leaf)},
        children={
            alpha.category_id: [shared.category_id],
            beta.category_id: [shared.category_id],
            shared.category_id: [leaf.category_id],
        },
        parents={
            shared.category_id: [alpha.category_id, beta.category_id],
            leaf.category_id: [shared.category_id],
        },
        items={alpha.category_id: [first], shared.category_id: [second]},
        roots=[alpha.category_id, beta.category_id],
    )


def render(graph: TaxomeshGraph) -> str:
    """Serialize a graph to the exact text form recorded in the baseline file."""
    return json.dumps(graph_to_dict(graph), indent=2, sort_keys=True) + "\n"


class TestGraphSerializationBaseline:
    """Byte-for-byte parity against the recorded output."""

    def test_matches_the_recorded_baseline(self) -> None:
        """The serializer's output is byte-identical to what was recorded."""
        assert BASELINE.exists(), f"baseline missing: {BASELINE}"
        assert render(build_reference_graph()) == BASELINE.read_text(encoding="utf-8")

    def test_the_baseline_records_a_shared_subtree_twice(self) -> None:
        """Guard the guard: the baseline is only meaningful if it contains the hard case.

        If a future edit simplifies the reference taxonomy into a plain tree, this file would
        keep passing while testing nothing about shared subtrees.
        """
        # Any: the recorded document is heterogeneous JSON (str, bool, list, nested dict)
        recorded: dict[str, Any] = json.loads(BASELINE.read_text(encoding="utf-8"))
        rendered = json.dumps(recorded)

        assert rendered.count(str(_uuid(3))) == 2, "the shared category must appear under both parents"
        assert rendered.count(str(_uuid(4))) == 2, "and so must everything beneath it"
