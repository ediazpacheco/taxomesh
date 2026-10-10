"""What only ``DjangoRepository`` does: its tables, its queries and its database errors.

The port's behaviour is asserted for every implementation, Django included, in
``tests/adapters/repositories/test_repository_contract.py``.
"""

import builtins
import re
import sys
from types import ModuleType
from typing import Any
from unittest.mock import patch

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.db import DatabaseError, connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.contrib.django.models import CategoryModel, ItemModel  # noqa: E402
from taxomesh.domain.models import Category, Item, ItemRelationLink  # noqa: E402
from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: E402

pytestmark = pytest.mark.django_db


def test_the_migrations_create_every_table() -> None:
    expected = {
        "taxomesh_category",
        "taxomesh_item",
        "taxomesh_tag",
        "taxomesh_category_parent_link",
        "taxomesh_item_parent_link",
        "taxomesh_item_tag_link",
        "taxomesh_item_relation_link",
    }
    table_names = set(connection.introspection.table_names())
    assert expected <= table_names, f"Missing tables: {expected - table_names}"


def test_external_ids_are_unique_columns() -> None:
    assert ItemModel._meta.get_field("external_id").unique is True
    assert CategoryModel._meta.get_field("external_id").unique is True


def test_opening_without_django_names_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    # Any: the arguments of builtins.__import__, which it stands in for, passed through unread.
    def fake_import(name: str, *args: Any, **kwargs: Any) -> ModuleType:
        if name == "django" or name.startswith("django."):
            raise ImportError("mocked: django not found")
        return real_import(name, *args, **kwargs)

    # Remove cached django and taxomesh.contrib.django modules so the deferred import triggers the fake
    evict = [
        k for k in sys.modules if k == "django" or k.startswith("django.") or k.startswith("taxomesh.contrib.django")
    ]
    saved = {k: sys.modules.pop(k) for k in evict}

    import taxomesh.adapters.repositories.django_repository as dr_mod  # noqa: PLC0415

    try:
        monkeypatch.setattr(builtins, "__import__", fake_import)
        with pytest.raises(TaxomeshRepositoryError, match="pip install taxomesh\\[django\\]"):
            dr_mod.DjangoRepository()
    finally:
        sys.modules.update(saved)
        monkeypatch.undo()


def test_the_summary_names_the_alias_and_no_credential() -> None:
    summary = DjangoRepository().config_summary
    assert re.match(r"^django:\w+/\w+$", summary), f"Unexpected format: {summary!r}"
    lower = summary.lower()
    assert "password" not in lower
    assert "host" not in lower
    assert "port" not in lower


def test_describe_reports_no_path_and_the_database_alias() -> None:
    info = DjangoRepository().describe()
    assert info.backend == "DjangoRepository"
    assert info.path is None
    assert info.diagnostics == {"database_alias": "default"}


class TestOneQuery:
    """A batch read costs one query, whatever it resolves."""

    def test_items_by_external_id(self) -> None:
        repo = DjangoRepository()
        external_ids = [f"item-{n}" for n in range(25)]
        for external_id in external_ids:
            repo.save_item(Item(name="Item", external_id=external_id))

        with CaptureQueriesContext(connection) as ctx:
            result = repo.map_items_by_external_id(external_ids)

        assert len(ctx.captured_queries) == 1
        assert set(result) == set(external_ids)

    def test_categories_by_external_id(self) -> None:
        repo = DjangoRepository()
        external_ids = [f"cat-{n}" for n in range(25)]
        for external_id in external_ids:
            repo.save_category(Category(name=f"Category {external_id}", external_id=external_id))

        with CaptureQueriesContext(connection) as ctx:
            result = repo.map_categories_by_external_id(external_ids)

        assert len(ctx.captured_queries) == 1
        assert set(result) == set(external_ids)

    def test_the_relation_links_of_many_items(self) -> None:
        repo = DjangoRepository()
        source, first, second = Item(name="src"), Item(name="t1"), Item(name="t2")
        for item in (source, first, second):
            repo.save_item(item)
        for target, relation_type in ((first, "covers"), (second, "samples")):
            repo.save_item_relation_link(
                ItemRelationLink(
                    source_item_id=source.item_id, target_item_id=target.item_id, relation_type=relation_type
                )
            )

        with CaptureQueriesContext(connection) as ctx:
            links = repo.list_item_relation_links_batch([source.item_id])

        assert len(ctx.captured_queries) == 1
        assert len(links) == 2

    def test_both_directions_in_one_query(self) -> None:
        repo = DjangoRepository()
        middle, out_target, in_source = Item(name="mid"), Item(name="out"), Item(name="in")
        for item in (middle, out_target, in_source):
            repo.save_item(item)
        repo.save_item_relation_link(
            ItemRelationLink(source_item_id=middle.item_id, target_item_id=out_target.item_id, relation_type="covers")
        )
        repo.save_item_relation_link(
            ItemRelationLink(source_item_id=in_source.item_id, target_item_id=middle.item_id, relation_type="covers")
        )

        with CaptureQueriesContext(connection) as ctx:
            links = repo.list_item_relation_links_batch([middle.item_id], direction="both")

        assert len(ctx.captured_queries) == 1
        assert {(lnk.source_item_id, lnk.target_item_id) for lnk in links} == {
            (middle.item_id, out_target.item_id),
            (in_source.item_id, middle.item_id),
        }


class TestDatabaseErrors:
    """A database error leaves the port as a ``TaxomeshRepositoryError``."""

    def test_items_by_external_id(self) -> None:
        repo = DjangoRepository()
        with (
            patch.object(repo._ItemModel.objects, "using", side_effect=DatabaseError("db down")),
            pytest.raises(TaxomeshRepositoryError),
        ):
            repo.map_items_by_external_id(["some-id"])

    def test_categories_by_external_id(self) -> None:
        repo = DjangoRepository()
        with (
            patch.object(repo._CategoryModel.objects, "using", side_effect=DatabaseError("db down")),
            pytest.raises(TaxomeshRepositoryError),
        ):
            repo.map_categories_by_external_id(["some-id"])
