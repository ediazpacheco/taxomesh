"""The service, its collections, the graph and each shipped repository say what they hold.

A ``repr`` is what a REPL, a debugger and a log line show, so each names what it holds rather
than a memory address: a repository its path or its database alias, the service its repository,
a collection the service it is reached through, and a graph its size. None of them reads storage
to say so.

Every member a collection offers presents as a method too, so ``help()`` heads it as one and shows
its own signature and docstring, whether or not the member keeps its reads in the cache.
"""

import inspect
from pathlib import Path

import pytest
from pytest_django import DjangoAssertNumQueries

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YamlRepository
from taxomesh.application.service import TaxomeshService
from tests.service.conftest import CountedService


class TestTheServiceAndItsParts:
    """Each repr is stated in terms of the next one in, so it holds on every backend."""

    def test_the_service_shows_its_repository(self, service: TaxomeshService) -> None:
        assert repr(service) == f"TaxomeshService({service.repository!r})"

    def test_a_collection_shows_how_it_is_reached(self, service: TaxomeshService) -> None:
        assert repr(service.categories) == f"{service!r}.categories"
        assert repr(service.items) == f"{service!r}.items"
        assert repr(service.tags) == f"{service!r}.tags"

    def test_the_graph_shows_its_size(self, service: TaxomeshService) -> None:
        music = service.categories.create("Music")
        service.categories.create("Books")
        jazz = service.categories.create("Jazz")
        service.categories.add_parent(jazz.category_id, music.category_id)

        graph = service.graph()

        assert repr(graph) == "TaxomeshGraph(categories=3, roots=2)"
        assert (len(graph), len(graph.roots)) == (3, 2)


class TestEveryMemberIsAMethod:
    """A member reached through the service is a bound method, a cached one included."""

    @pytest.mark.parametrize("namespace", ["categories", "items", "tags"])
    def test_each_public_member(self, tmp_path: Path, namespace: str) -> None:
        service = TaxomeshService(YamlRepository(tmp_path / "catalog.yaml"))
        collection = {"categories": service.categories, "items": service.items, "tags": service.tags}[namespace]

        members = [(name, member) for name, member in inspect.getmembers(collection, callable) if name[0] != "_"]

        assert members
        assert [name for name, member in members if not inspect.ismethod(member)] == []


class TestTheShippedRepositories:
    """Each shipped repository shows the constructor call that would open the same store."""

    def test_yaml_shows_its_path(self, tmp_path: Path) -> None:
        path = tmp_path / "catalog.yaml"
        assert repr(YamlRepository(path)) == f"YamlRepository({str(path)!r})"

    def test_json_shows_its_path(self, tmp_path: Path) -> None:
        path = tmp_path / "catalog.json"
        assert repr(JsonRepository(path)) == f"JsonRepository({str(path)!r})"

    @pytest.mark.django_db
    def test_django_shows_its_database_alias(self, django_assert_num_queries: DjangoAssertNumQueries) -> None:
        pytest.importorskip("django", reason="django not installed")
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

        repository = DjangoRepository()
        with django_assert_num_queries(0):
            rendered = repr(repository)
        assert rendered == "DjangoRepository(using='default')"


def test_no_repr_reads_storage(counting_service: CountedService) -> None:
    """Taking every repr costs no storage read, on every backend."""
    service = counting_service.service
    service.categories.create("Music")
    graph = service.graph()
    counting_service.cold()

    for part in (service, service.categories, service.items, service.tags, graph):
        repr(part)

    assert counting_service.reads.total == 0
