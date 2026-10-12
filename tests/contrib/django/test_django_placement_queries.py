"""Query-count gates for the three placement read paths.

The point of this module is not that the paths are *fast* but that their cost is
**constant**: the same number of queries for 5 rows as for 200. A regression to
per-row resolution changes that number and fails here, rather than merely
running slower and going unnoticed.

Every measurement is taken cold. The service's cache is cleared before each
``CaptureQueriesContext`` block, because these methods sit behind the read cache
and a warm second call would report zero queries and prove nothing.
"""

from collections.abc import Callable
from dataclasses import dataclass
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.db import connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.application.service import TaxomeshService  # noqa: E402
from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: E402

pytestmark = pytest.mark.django_db

# Two sizes far enough apart that any per-row term is unmissable.
CORPUS_SIZES = (5, 200)

# Existence check + link query + batch resolve.
EXPECTED_QUERIES = 3

# Existence check + link query; the batch resolve is skipped on an empty link set.
EXPECTED_QUERIES_EMPTY = 2


@dataclass(frozen=True)
class Corpus:
    """A populated store plus the three ids the gates read from."""

    service: TaxomeshService
    category_id: UUID
    """A category holding ``size`` item placements."""
    parent_id: UUID
    """A category holding ``size`` child categories."""
    item_id: UUID
    """An item placed in ``size`` distinct categories."""
    size: int


@pytest.fixture(params=CORPUS_SIZES, ids=lambda n: f"n{n}")
def corpus(request: pytest.FixtureRequest) -> Corpus:
    """Build a corpus of the parametrised size covering all three read paths."""
    size = int(request.param)
    service = TaxomeshService(repository=DjangoRepository())
    holder = service.categories.create(f"holder-{size}", slug=f"holder-{size}")
    parent = service.categories.create(f"parent-{size}", slug=f"parent-{size}")
    probe = service.items.create(name=f"probe-{size}")

    for i in range(size):
        placed = service.items.create(name=f"item-{size}-{i}")
        service.items.place_in(placed.item_id, holder.category_id, sort_index=i)

        child = service.categories.create(f"child-{size}-{i}", slug=f"child-{size}-{i}")
        service.categories.add_parent(child.category_id, parent.category_id, sort_index=i)
        service.items.place_in(probe.item_id, child.category_id, sort_index=i)

    return Corpus(
        service=service,
        category_id=holder.category_id,
        parent_id=parent.category_id,
        item_id=probe.item_id,
        size=size,
    )


def count_queries(service: TaxomeshService, call: Callable[[], object]) -> int:
    """Return the number of queries *call* issues, measured cold.

    Clearing the service's cache first is what makes the figure meaningful;
    without it a second measurement of the same call reports zero.
    """
    service._cache.clear()
    with CaptureQueriesContext(connection) as ctx:
        call()
    return len(ctx.captured_queries)


# ---------------------------------------------------------------------------
# items.list(category=…)
# ---------------------------------------------------------------------------


def test_items_list_by_category_costs_a_constant_number_of_queries(corpus: Corpus) -> None:
    """The canonical 'show me this category's contents' call must not scale in queries."""
    count = count_queries(corpus.service, lambda: corpus.service.items.list(category=corpus.category_id))
    assert count == EXPECTED_QUERIES, (
        f"items.list(category=…) issued {count} queries for {corpus.size} placements; "
        f"expected a constant {EXPECTED_QUERIES}. A count near {corpus.size + 2} means "
        "per-row resolution has returned."
    )


def test_items_list_by_category_returns_every_placement(corpus: Corpus) -> None:
    """Guard against a query count that is constant only because rows went missing."""
    corpus.service._cache.clear()
    assert len(corpus.service.items.list(category=corpus.category_id)) == corpus.size


def test_items_list_by_category_is_empty_without_a_batch_resolve(corpus: Corpus) -> None:
    """An empty link set short-circuits before the batch resolve."""
    empty = corpus.service.categories.create(f"empty-{corpus.size}", slug=f"empty-{corpus.size}")
    count = count_queries(corpus.service, lambda: corpus.service.items.list(category=empty.category_id))
    assert count == EXPECTED_QUERIES_EMPTY


# ---------------------------------------------------------------------------
# Oversized batch input
# ---------------------------------------------------------------------------
#
# This lives with the database backend because it is the only one with a
# per-query parameter limit — the file backends resolve from an in-memory dict
# and have nothing to exceed. Testing it against them would be theatre, and
# building the corpus there is O(n²) in file rewrites.

# The pre-3.32 SQLite parameter ceiling. Modern builds allow ~32k, and the
# project floor is Python 3.13, whose SQLite is newer, so this must simply work.
LEGACY_SQLITE_PARAM_LIMIT = 999


def test_batch_category_lookup_handles_a_large_id_set() -> None:
    """One request, no internal splitting, correct result."""
    from taxomesh.domain.models import Category  # noqa: PLC0415

    repository = DjangoRepository()
    created = []
    for i in range(LEGACY_SQLITE_PARAM_LIMIT + 1):
        category = Category(name=f"bulk-{i}", slug=f"bulk-{i}")
        repository.save_category(category)
        created.append(category.category_id)

    with CaptureQueriesContext(connection) as ctx:
        result = repository.map_categories_by_id(created)

    assert len(result) == len(created), "rows went missing — the backend truncated or split badly"
    assert len(ctx.captured_queries) == 1, "the request was split; the port requires exactly one"


# ---------------------------------------------------------------------------
# categories.list(parent=…)
# ---------------------------------------------------------------------------


def test_categories_list_by_parent_costs_a_constant_number_of_queries(corpus: Corpus) -> None:
    count = count_queries(corpus.service, lambda: corpus.service.categories.list(parent=corpus.parent_id))
    assert count == EXPECTED_QUERIES, (
        f"categories.list(parent=…) issued {count} queries for {corpus.size} children; "
        f"expected a constant {EXPECTED_QUERIES}."
    )


def test_categories_list_by_parent_returns_every_child(corpus: Corpus) -> None:
    corpus.service._cache.clear()
    assert len(corpus.service.categories.list(parent=corpus.parent_id)) == corpus.size


def test_categories_list_by_parent_ignores_unrelated_branches(corpus: Corpus) -> None:
    """Cost must not depend on categories living under OTHER parents.

    Before the parent filter this path read every category-parent link in the
    store, so growing an unrelated branch grew the work. The query count alone
    would not have caught it — one unfiltered scan is still one query — which is
    why this asserts on the result as well.
    """
    before = count_queries(corpus.service, lambda: corpus.service.categories.list(parent=corpus.parent_id))

    stranger = corpus.service.categories.create(f"stranger-{corpus.size}", slug=f"stranger-{corpus.size}")
    for i in range(50):
        extra = corpus.service.categories.create(f"extra-{corpus.size}-{i}", slug=f"extra-{corpus.size}-{i}")
        corpus.service.categories.add_parent(extra.category_id, stranger.category_id, sort_index=i)

    after = count_queries(corpus.service, lambda: corpus.service.categories.list(parent=corpus.parent_id))

    assert after == before == EXPECTED_QUERIES
    assert len(corpus.service.categories.list(parent=corpus.parent_id)) == corpus.size


def test_categories_list_of_a_leaf_skips_the_batch_resolve(corpus: Corpus) -> None:
    leaf = corpus.service.categories.create(f"leaf-{corpus.size}", slug=f"leaf-{corpus.size}")
    count = count_queries(corpus.service, lambda: corpus.service.categories.list(parent=leaf.category_id))
    assert count == EXPECTED_QUERIES_EMPTY


# ---------------------------------------------------------------------------
# categories.list(item=…)
# ---------------------------------------------------------------------------


def test_categories_list_by_item_costs_a_constant_number_of_queries(corpus: Corpus) -> None:
    count = count_queries(corpus.service, lambda: corpus.service.categories.list(item=corpus.item_id))
    assert count == EXPECTED_QUERIES, (
        f"categories.list(item=…) issued {count} queries for {corpus.size} placements; "
        f"expected a constant {EXPECTED_QUERIES}."
    )


def test_categories_list_by_item_returns_every_placement(corpus: Corpus) -> None:
    corpus.service._cache.clear()
    assert len(corpus.service.categories.list(item=corpus.item_id)) == corpus.size


def test_categories_list_of_an_unplaced_item_skips_the_batch_resolve(corpus: Corpus) -> None:
    loose = corpus.service.items.create(name=f"loose-{corpus.size}")
    count = count_queries(corpus.service, lambda: corpus.service.categories.list(item=loose.item_id))
    assert count == EXPECTED_QUERIES_EMPTY


# ---------------------------------------------------------------------------
# Storage failure surfaces as the library's own error
# ---------------------------------------------------------------------------
#
# Django is the only backend that can fail at the storage boundary, so this is
# where the wrapper is provable. It is also what an oversized id collection
# relies on: exceeding the parameter limit raises a DatabaseError like any other,
# and must not escape the port as a raw Django exception.


def test_batch_category_lookup_wraps_a_database_error() -> None:
    """A backend failure must never escape the port unwrapped."""
    repository = DjangoRepository()

    with (
        patch.object(repository._CategoryModel.objects, "using", side_effect=django.db.DatabaseError("db down")),
        pytest.raises(TaxomeshRepositoryError),
    ):
        repository.map_categories_by_id([uuid4()])


def test_category_parent_link_listing_wraps_a_database_error() -> None:
    """For the newly filtered link listing, which gained its own query path."""
    repository = DjangoRepository()

    with (
        patch.object(
            repository._CategoryParentLinkModel.objects, "using", side_effect=django.db.DatabaseError("db down")
        ),
        pytest.raises(TaxomeshRepositoryError),
    ):
        repository.list_category_parent_links(parent_category_ids=[uuid4()])


def test_unfiltered_category_parent_link_listing_wraps_a_database_error() -> None:
    """The unfiltered path is the one eleven existing call sites use — it must wrap too."""
    repository = DjangoRepository()

    with (
        patch.object(
            repository._CategoryParentLinkModel.objects, "using", side_effect=django.db.DatabaseError("db down")
        ),
        pytest.raises(TaxomeshRepositoryError),
    ):
        repository.list_category_parent_links()
