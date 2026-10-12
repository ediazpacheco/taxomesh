"""A database failure leaves every member of the three collections as a ``TaxomeshRepositoryError``.

Each case builds a service over Django, stores a few rows, then makes every query fail and calls one
member. The error is a ``TaxomeshRepositoryError`` and its cause is the database's own error.
"""

from collections.abc import Callable, Iterator
from typing import Any
from unittest.mock import patch

import pytest

pytest.importorskip("django", reason="Django is not installed")

from django.db import OperationalError  # noqa: E402
from django.db.models.sql.compiler import SQLCompiler, SQLInsertCompiler  # noqa: E402

from taxomesh import TaxomeshService  # noqa: E402
from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: E402

pytestmark = pytest.mark.django_db

_Case = Callable[[TaxomeshService, dict[str, Any]], object]

# Each member of the collections, with the rows it needs. A write reads its rows first, so a read
# that fails stops it before it writes.
_CASES: dict[str, _Case] = {
    "categories.get": lambda s, r: s.categories.get(r["c"].category_id),
    "categories.get_many": lambda s, r: s.categories.get_many([r["c"].category_id]),
    "categories.get_by_slug": lambda s, r: s.categories.get_by_slug("c"),
    "categories.get_by_external_id": lambda s, r: s.categories.get_by_external_id("x"),
    "categories.get_many_by_external_id": lambda s, r: s.categories.get_many_by_external_id(["x"]),
    "categories.list": lambda s, r: s.categories.list(),
    "categories.roots": lambda s, r: s.categories.roots(),
    "categories.search": lambda s, r: s.categories.search("c"),
    "categories.create": lambda s, r: s.categories.create(name="n"),
    "categories.update": lambda s, r: s.categories.update(r["c"], name="c2"),
    "categories.add_parent": lambda s, r: s.categories.add_parent(r["c"], r["p"]),
    "categories.remove_parent": lambda s, r: s.categories.remove_parent(r["c"], r["p"]),
    "categories.move": lambda s, r: s.categories.move(r["c"], from_parent=None, to_parent=r["p"]),
    "categories.reorder": lambda s, r: s.categories.reorder(None, [r["c"], r["p"]]),
    "categories.delete": lambda s, r: s.categories.delete(r["c"]),
    "items.get": lambda s, r: s.items.get(r["i"].item_id),
    "items.get_many": lambda s, r: s.items.get_many([r["i"].item_id]),
    "items.get_by_slug": lambda s, r: s.items.get_by_slug("i"),
    "items.get_by_external_id": lambda s, r: s.items.get_by_external_id("x"),
    "items.get_many_by_external_id": lambda s, r: s.items.get_many_by_external_id(["x"]),
    "items.list": lambda s, r: s.items.list(),
    "items.search": lambda s, r: s.items.search("i"),
    "items.create": lambda s, r: s.items.create(name="n"),
    "items.update": lambda s, r: s.items.update(r["i"], name="i2"),
    "items.place_in": lambda s, r: s.items.place_in(r["i"], r["p"]),
    "items.remove_from": lambda s, r: s.items.remove_from(r["j"], r["p"]),
    "items.move": lambda s, r: s.items.move(r["j"], from_category=r["p"], to_category=r["c"]),
    "items.reorder": lambda s, r: s.items.reorder(r["p"], [r["j"]]),
    "items.tag": lambda s, r: s.items.tag(r["i"], r["t"]),
    "items.untag": lambda s, r: s.items.untag(r["i"], r["t"]),
    "items.relate": lambda s, r: s.items.relate(r["i"], r["j"], "x"),
    "items.unrelate": lambda s, r: s.items.unrelate(r["i"], r["j"], "x"),
    "items.list_relations": lambda s, r: s.items.list_relations(r["i"]),
    "items.list_related": lambda s, r: s.items.list_related(r["i"]),
    "items.get_many_related": lambda s, r: s.items.get_many_related([r["i"]]),
    "items.delete": lambda s, r: s.items.delete(r["i"]),
    "tags.get": lambda s, r: s.tags.get(r["t"].tag_id),
    "tags.get_many": lambda s, r: s.tags.get_many([r["t"].tag_id]),
    "tags.list": lambda s, r: s.tags.list(),
    "tags.list_for_item": lambda s, r: s.tags.list(item=r["i"]),
    "tags.create": lambda s, r: s.tags.create(name="n"),
    "tags.update": lambda s, r: s.tags.update(r["t"], name="t2"),
    "tags.delete": lambda s, r: s.tags.delete(r["t"]),
}


@pytest.fixture
def service() -> TaxomeshService:
    return TaxomeshService(DjangoRepository(), cache_ttl=0)


@pytest.fixture
def rows(service: TaxomeshService) -> dict[str, Any]:
    c = service.categories.create(name="c")
    p = service.categories.create(name="p")
    i = service.items.create(name="i")
    j = service.items.create(name="j")
    t = service.tags.create(name="t")
    service.items.place_in(j, p)
    return {"c": c, "p": p, "i": i, "j": j, "t": t}


def _fail(*_args: object, **_kwargs: object) -> object:
    raise OperationalError("no such table")


@pytest.fixture
def queries_fail() -> Iterator[None]:
    with (
        patch.object(SQLCompiler, "execute_sql", _fail),
        patch.object(SQLInsertCompiler, "execute_sql", _fail),
    ):
        yield


@pytest.mark.parametrize("case", _CASES)
def test_a_database_error_is_a_repository_error(
    case: str, service: TaxomeshService, rows: dict[str, Any], queries_fail: None
) -> None:
    with pytest.raises(TaxomeshRepositoryError) as caught:
        _CASES[case](service, rows)
    assert isinstance(caught.value.__cause__, OperationalError)
