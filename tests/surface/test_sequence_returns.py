"""A member returning a sequence returns a tuple, and ``mypy --strict`` reports a mutation.

Two guarantees, checked two ways.

* **At runtime**, every member annotated ``Sequence[…]`` on the three collections, the graph, its
  nodes and ``RelatedItems`` returns a ``tuple``: from the cache or not, empty or not, on every
  path a filter selects. The memo hands one value to every caller until the next write, and
  rows are frozen, so a tuple is safe to share all the way down. The members are enumerated from
  the code, so a new one that no case exercises fails here.
* **Statically**, the annotation stays ``Sequence[X]``, so ``mypy --strict`` reports an
  ``.append(...)`` at the consumer's own call site. ``py.typed`` ships, so that report reaches
  consumers. Only the type checker can check this, which is why the second half of this file
  runs it.

The type-checking fixtures are written to a temporary file rather than committed, for the reason
``tests/utils/test_memoize_typing.py`` gives for the same choice: a committed file full of
deliberate errors would fail the repository's own ``mypy --strict .`` gate, and an exclusion added
to keep it out is one more thing that can drift. They cover three layers: the collections, the
port and the HTTP handlers.
"""

import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.application.collections.categories import CategoryCollection
from taxomesh.application.collections.items import ItemCollection
from taxomesh.application.collections.tags import TagCollection
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.graph import CategoryNode, TaxomeshGraph
from taxomesh.domain.models import Category, Item, Tag
from taxomesh.domain.related import RelatedItems
from tests.surface._surface import public_names, render_member

_REPO_ROOT = Path(__file__).resolve().parents[2]

# The types whose members may return a sequence. Each member whose return annotation is
# ``Sequence[…]`` must appear in ``_calls`` below.
SEQUENCE_OWNERS: list[type] = [
    CategoryCollection,
    ItemCollection,
    TagCollection,
    TaxomeshGraph,
    CategoryNode,
    RelatedItems,
]

_RETURNS_A_SEQUENCE = re.compile(r"(->|: property ->) (collections\.abc\.)?Sequence\[")


def _sequence_members() -> list[str]:
    """Return every public member of the owners whose return annotation is a sequence."""
    return sorted(
        f"{owner.__name__}.{name}"
        for owner in SEQUENCE_OWNERS
        for name in public_names(owner)
        if _RETURNS_A_SEQUENCE.search(render_member(owner, name))
    )


@dataclass(frozen=True, slots=True)
class _Taxonomy:
    """A small stored taxonomy: a parent with one child, two related items and a tag."""

    service: TaxomeshService
    parent: Category
    child: Category
    item: Item
    other: Item
    tag: Tag


@pytest.fixture
def taxonomy(tmp_path: Path) -> _Taxonomy:
    service = TaxomeshService(repository=JsonRepository(tmp_path / "taxonomy.json"))
    parent = service.categories.create("Tango")
    child = service.categories.create("Milonga")
    service.categories.add_parent(child.category_id, parent.category_id)
    item = service.items.create("Percanta")
    other = service.items.create("Mina")
    service.items.place_in(item.item_id, child.category_id)
    service.items.relate(item.item_id, other.item_id, "covers")
    tag = service.tags.create("lunfardo")
    service.items.tag(item.item_id, tag.tag_id)
    return _Taxonomy(service=service, parent=parent, child=child, item=item, other=other, tag=tag)


def _calls(t: _Taxonomy) -> dict[str, list[Callable[[], object]]]:
    """Return, per member, calls covering each path it takes, an empty result included."""
    s = t.service
    graph = s.graph()
    related = s.items.get_many_related([t.item.item_id])[t.item.item_id]
    return {
        "CategoryCollection.list": [
            s.categories.list,
            lambda: s.categories.list(parent=t.parent.category_id),
            lambda: s.categories.list(item=t.item.item_id),
            lambda: s.categories.list(parent=t.child.category_id),
        ],
        "CategoryCollection.roots": [s.categories.roots],
        "CategoryCollection.search": [
            lambda: s.categories.search("milonga"),
            lambda: s.categories.search("milonga", parent=t.parent.category_id),
            lambda: s.categories.search(" "),
        ],
        "ItemCollection.list": [
            s.items.list,
            lambda: s.items.list(category=t.child.category_id),
            lambda: s.items.list(category=t.parent.category_id, recursive=True),
            lambda: s.items.list(category=t.parent.category_id),
            lambda: s.items.list(tag=t.tag.tag_id),
            lambda: s.items.list(category=t.child.category_id, tag=t.tag.tag_id),
        ],
        "ItemCollection.list_related": [
            lambda: s.items.list_related(t.item.item_id),
            lambda: s.items.list_related(t.other.item_id),
        ],
        "ItemCollection.list_relations": [
            lambda: s.items.list_relations(t.item.item_id),
            lambda: s.items.list_relations(t.other.item_id),
        ],
        "ItemCollection.search": [
            lambda: s.items.search("percanta"),
            lambda: s.items.search("percanta", category=t.child.category_id),
            lambda: s.items.search("percanta", category=t.parent.category_id, recursive=True),
            lambda: s.items.search(" "),
        ],
        "TagCollection.list": [
            s.tags.list,
            lambda: s.tags.list(item=t.item.item_id),
            lambda: s.tags.list(item=t.other.item_id),
        ],
        "TaxomeshGraph.roots": [lambda: graph.roots],
        "CategoryNode.children": [
            lambda: graph[t.parent.category_id].children,
            lambda: graph[t.child.category_id].children,
        ],
        "CategoryNode.parents": [
            lambda: graph[t.child.category_id].parents,
            lambda: graph[t.parent.category_id].parents,
        ],
        "CategoryNode.items": [
            lambda: graph[t.child.category_id].items,
            lambda: graph[t.parent.category_id].items,
        ],
        "CategoryNode.ancestors": [
            graph[t.child.category_id].ancestors,
            graph[t.parent.category_id].ancestors,
        ],
        "CategoryNode.descendants": [
            graph[t.parent.category_id].descendants,
            graph[t.child.category_id].descendants,
        ],
        "RelatedItems.of_type": [lambda: related.of_type("covers"), lambda: related.of_type("absent")],
        "RelatedItems.relation_types": [lambda: related.relation_types],
    }


def test_every_sequence_member_is_exercised(taxonomy: _Taxonomy) -> None:
    """A member annotated ``Sequence[…]`` that no case below calls fails here."""
    assert sorted(_calls(taxonomy)) == _sequence_members()


@pytest.mark.parametrize("member", _sequence_members())
def test_a_sequence_member_returns_a_tuple(taxonomy: _Taxonomy, member: str) -> None:
    """Each call returns a tuple, and so does the same call answered from the cache."""
    for call in _calls(taxonomy)[member]:
        for _ in range(2):
            result = call()
            assert type(result) is tuple, f"{member} returned {type(result).__name__}: {result!r}"


def test_the_groups_of_related_items_are_tuples(taxonomy: _Taxonomy) -> None:
    """Each relation type's group, read straight from ``by_type``, is a tuple too."""
    for _ in range(2):
        related = taxonomy.service.items.get_many_related([taxonomy.item.item_id])[taxonomy.item.item_id]
        assert [type(group) for group in related.by_type.values()] == [tuple]


# One mutation per line, each tagged with the marker the assertion looks for. Keep the
# ``# E:`` comment on the same line as the expression it describes. Indexing is not a
# mutation and must stay clean — it is how each line names a value of the right type
# without constructing one.
MUTATION_SOURCE = '''\
"""Deliberate mutations of sequence-returning members. Every marked line must error."""

from taxomesh.application.service import TaxomeshService
from taxomesh.contrib.api import handlers
from taxomesh.ports.repository import TaxomeshRepositoryBase


def through_a_collection(service: TaxomeshService) -> None:
    categories = service.categories.list()
    categories.append(categories[0])  # E: a memoized collection listing is shared, not owned

    ranked = service.items.search("query")
    ranked.append(ranked[0])  # E: a ranked result is a sequence too


def through_the_port(repository: TaxomeshRepositoryBase) -> None:
    items = repository.list_items()
    items.append(items[0])  # E: a port listing is not the caller's to mutate

    links = repository.list_item_parent_links()
    links.append(links[0])  # E: link reads are sequences on the port as well


def through_a_handler(service: TaxomeshService) -> None:
    tags = handlers.tags_list(service)
    tags.append(tags[0])  # E: the HTTP handler layer agrees with the port it calls
'''

# The counterpart's fixture: every shape a consumer legitimately uses. Without it the
# assertion above would still pass if the annotations rejected *everything*.
READ_ONLY_SOURCE = '''\
"""Read-only use of sequence-returning members — must type-check clean."""

from taxomesh.application.service import TaxomeshService
from taxomesh.contrib.api import handlers, schemas, serializers
from taxomesh.domain.models import Category
from taxomesh.ports.repository import TaxomeshRepositoryBase


def serializing(service: TaxomeshService) -> int:
    """A result goes straight into the serializers, as docs/http-api-integration.md shows."""
    found = handlers.items_search(service, params=schemas.SearchItemsRequest(query="q"))
    payload = serializers.items_to_list(found) + serializers.categories_to_list(service.categories.list())
    return len(payload)


def reading(service: TaxomeshService, repository: TaxomeshRepositoryBase) -> int:
    categories = service.categories.list()
    first: Category = categories[0]
    for category in categories:
        first = category
    total = len(categories) + len(repository.list_items()) + len(handlers.tags_list(service))
    return total if first.name else 0


def copying(service: TaxomeshService) -> list[Category]:
    """Taking a mutable copy is how a consumer that needs one asks for it."""
    owned = list(service.categories.roots())
    owned.append(owned[0])
    return owned
'''


def _expected_error_lines(source: str) -> list[int]:
    """Return the 1-based line numbers carrying an ``# E:`` marker."""
    return [n for n, line in enumerate(source.splitlines(), start=1) if "# E:" in line]


def _run_mypy(fixture: Path) -> subprocess.CompletedProcess[str]:
    """Type-check one fixture file under the repository's own settings."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--strict",
            "--python-version",
            "3.13",
            "--no-error-summary",
            "--no-incremental",
            str(fixture),
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_mutating_a_returned_sequence_is_reported(tmp_path: Path) -> None:
    """Every marked mutation errors, and nothing else does."""
    fixture = tmp_path / "sequence_mutation.py"
    fixture.write_text(MUTATION_SOURCE, encoding="utf-8")

    result = _run_mypy(fixture)

    reported = {int(line.split(":")[1]) for line in result.stdout.splitlines() if ": error:" in line}
    expected = set(_expected_error_lines(MUTATION_SOURCE))

    missed = sorted(expected - reported)
    assert not missed, (
        f"mypy did not report these mutations: {missed}. A member whose return annotation "
        f"widens back to list lets a consumer corrupt a memoized value shared with every "
        f"other caller, silently.\n{result.stdout}"
    )
    unexpected = sorted(reported - expected)
    assert not unexpected, f"mypy reported errors on unmarked lines {unexpected}:\n{result.stdout}"


def test_reading_a_returned_sequence_type_checks_clean(tmp_path: Path) -> None:
    """Indexing, iterating, counting and copying stay legal.

    ``Sequence`` is the read-only half of ``list``, not a narrower one: everything a caller
    does with a result short of mutating it in place must keep type-checking, or the
    annotation has bought its guarantee by breaking consumers.
    """
    fixture = tmp_path / "sequence_read_only.py"
    fixture.write_text(READ_ONLY_SOURCE, encoding="utf-8")

    result = _run_mypy(fixture)

    assert result.returncode == 0, result.stdout
