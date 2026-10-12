"""The graph loader's cache stays bounded however many roots are asked for.

The graph memoizes its **loader**, keyed by ``(enabled, include_items)``, and leaves the
**assembler** unmemoized; this is its gate.

The alternative, memoizing the assembled graph, would key the cache on ``root`` too, since
:meth:`TaxomeshService.graph` accepts one. That cache has **no size bound**: within ``cache_ttl``,
entries live until the next write. So a caller building a rooted graph per category —
a navigation menu, a sidebar, the Django admin — would retain one full taxonomy snapshot per
category, and nothing in the test suite would notice: every correctness assertion stays green
while memory grows with the taxonomy.

Only a bound on the cache itself can catch that, which is why this file reaches past the public
surface into the service's cache for ``_load_graph_rows``. The bound is **six** — three ``enabled`` states times
two ``include_items`` states — and it holds no matter how many distinct roots are requested.
"""

from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import TaxomeshCategoryNotFoundError
from tests.service.conftest import InMemoryRepository

# Three ``enabled`` states (True, False, None) times two ``include_items`` states. Every graph
# form the service can be asked for reaches the loader through one of these six keys.
MAX_LOADER_ENTRIES = 6


def loader_cache_size(service: TaxomeshService) -> int:
    """Return how many entries the graph loader holds in this service's cache."""
    return len(service._cache.entries(TaxomeshService._load_graph_rows))


@pytest.fixture
def service() -> TaxomeshService:
    """Return a service over a fresh in-memory backend, whose cache starts empty."""
    return TaxomeshService(repository=InMemoryRepository())


class TestTheLoaderCacheIsBounded:
    """Retention is bounded by the data, not by how many roots were requested."""

    def test_many_distinct_roots_hold_at_most_six_entries(self, service: TaxomeshService) -> None:
        """Twenty roots, one cache entry, asserted rather than assumed.

        Each of these twenty calls assembles a different graph. If the *assembler* were the
        memoized unit there would be twenty entries, each holding its own snapshot; because the
        **loader** is, they all answer from the one set of rows they share.
        """
        roots = [service.categories.create(f"r{i}") for i in range(20)]

        for root in roots:
            service.graph(root=root.category_id)

        assert loader_cache_size(service) == 1

    def test_every_form_together_still_holds_six(self, service: TaxomeshService) -> None:
        """All six loader keys, crossed with many roots, and the bound is exactly six.

        The number is the point: six is ``len({True, False, None}) * len({True, False})``, so it
        is a property of the *key shape* and cannot grow with the taxonomy or with the number of
        distinct roots a caller asks for.

        The ``enabled=False`` pair is exercised **unrooted**, because every category built here is
        enabled and a graph rooted at one of them under the disabled filter is legitimately
        not-found — pinned as behaviour in ``test_service_graph.py``. The key being counted is the
        loader's, and it does not care which of the two forms populated it.
        """
        roots = [service.categories.create(f"r{i}") for i in range(10)]

        for root in roots:
            for include_items in (True, False):
                for enabled in (True, None):
                    service.graph(root=root.category_id, enabled=enabled, include_items=include_items)
        for include_items in (True, False):
            service.graph(enabled=False, include_items=include_items)

        assert loader_cache_size(service) == MAX_LOADER_ENTRIES

    def test_the_unrooted_form_shares_those_same_six_keys(self, service: TaxomeshService) -> None:
        """A rooted graph and a whole-taxonomy graph reach the *same* entry.

        ``root`` is applied by the assembler, not the loader, so it must not appear in the
        key. If it did, this would be two entries rather than one — and that is precisely the
        regression this file exists to catch.
        """
        root = service.categories.create("Alpha")

        service.graph(include_items=False)
        assert loader_cache_size(service) == 1

        service.graph(root=root.category_id, include_items=False)

        assert loader_cache_size(service) == 1

    def test_a_root_that_does_not_exist_caches_nothing(self, service: TaxomeshService) -> None:
        """A rejected ``root`` leaves no entry behind.

        Validation happens before the loader runs, so a bad identifier raises without reaching
        storage. Worth pinning: the opposite order would both cost a read and populate the cache
        on the way to raising.
        """
        service.categories.create("Alpha")
        missing: UUID = uuid4()

        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.graph(root=missing)

        assert loader_cache_size(service) == 0
