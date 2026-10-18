"""What only ``DjangoRepository`` does: its tables, its queries and its database errors.

The port's behaviour is asserted for every implementation, Django included, in
``tests/adapters/repositories/test_repository_contract.py``.
"""

import builtins
import inspect
import re
import sys
from collections.abc import Callable
from types import ModuleType
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.db import DatabaseError, IntegrityError, connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.contrib.django import get_taxomesh_service_with_django  # noqa: E402
from taxomesh.contrib.django.models import CategoryModel, ItemModel  # noqa: E402
from taxomesh.domain.constants import ROOT_CATEGORY_NAME  # noqa: E402
from taxomesh.domain.models import Category, Item, ItemRelationLink  # noqa: E402
from taxomesh.exceptions import (  # noqa: E402
    TaxomeshDuplicateSlugError,
    TaxomeshExternalIdConflictError,
    TaxomeshRepositoryError,
)

pytestmark = pytest.mark.django_db


# Any: these calls pass what the annotations refuse, as an untyped caller can.
def untyped(value: object) -> Any:
    """Return ``value`` typed as anything, so a call can pass what its annotation refuses."""
    return value


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


def test_the_service_builder_and_the_repository_default_to_the_same_alias() -> None:
    """The alias has one default: a signature that says ``None`` for ``"default"`` would be a second."""
    builder = inspect.signature(get_taxomesh_service_with_django).parameters["using"].default
    repository = inspect.signature(DjangoRepository).parameters["using"].default
    assert builder == repository == "default"
    assert get_taxomesh_service_with_django().repository.describe().diagnostics["database_alias"] == "default"


@pytest.mark.parametrize(
    "build", [DjangoRepository, get_taxomesh_service_with_django], ids=["repository", "service builder"]
)
def test_an_alias_that_is_not_a_str_raises_type_error(build: Callable[..., object]) -> None:
    """Django reads a ``None`` alias as ``"default"``, so it is refused before Django reads it."""
    with pytest.raises(TypeError, match="^using must be a str, not NoneType$"):
        build(using=untyped(None))


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
        with pytest.raises(TaxomeshRepositoryError, match="pip install 'taxomesh\\[django\\]'"):
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


def test_a_block_starts_by_locking_the_implicit_roots_row() -> None:
    """The lock comes before any read of the block, so a second block reads after the first commits."""
    repo = DjangoRepository()
    repo.save_category(Category(name=ROOT_CATEGORY_NAME))

    with CaptureQueriesContext(connection) as ctx, repo.atomic():
        repo.find_category(uuid4())

    statements = [query["sql"] for query in ctx.captured_queries if "SAVEPOINT" not in query["sql"]]
    assert statements[0].startswith('UPDATE "taxomesh_category" SET "name"')
    assert statements[0].endswith(f'"taxomesh_category"."name" = \'{ROOT_CATEGORY_NAME}\'')
    assert statements[1].startswith("SELECT")


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
            patch.object(repo._items, "get_queryset", side_effect=DatabaseError("db down")),
            pytest.raises(TaxomeshRepositoryError),
        ):
            repo.map_items_by_external_id(["some-id"])

    def test_categories_by_external_id(self) -> None:
        repo = DjangoRepository()
        with (
            patch.object(repo._categories, "get_queryset", side_effect=DatabaseError("db down")),
            pytest.raises(TaxomeshRepositoryError),
        ):
            repo.map_categories_by_external_id(["some-id"])

    def test_the_lock_a_block_starts_with(self) -> None:
        repo = DjangoRepository()
        with (
            patch.object(repo._categories, "get_queryset", side_effect=DatabaseError("db down")),
            pytest.raises(TaxomeshRepositoryError),
            repo.atomic(),
        ):
            pass


def _save_item(repo: DjangoRepository, slug: str, external_id: str | None) -> object:
    return repo.save_item(Item(name="row", slug=slug, external_id=external_id))


def _save_category(repo: DjangoRepository, slug: str, external_id: str | None) -> object:
    return repo.save_category(Category(name="row", slug=slug, external_id=external_id))


SAVES: dict[str, Callable[[DjangoRepository, str, str | None], object]] = {
    "item": _save_item,
    "category": _save_category,
}


@pytest.mark.parametrize("kind", SAVES)
class TestUniqueKeys:
    """A save that a unique column refuses raises the error of the key that another row holds."""

    def test_a_slug_that_another_row_holds(self, kind: str) -> None:
        repo = DjangoRepository()
        SAVES[kind](repo, "s", None)
        with pytest.raises(TaxomeshDuplicateSlugError, match=f"^Slug 's' is already used by another {kind}$"):
            SAVES[kind](repo, "s", None)

    def test_an_external_id_that_another_row_holds(self, kind: str) -> None:
        repo = DjangoRepository()
        SAVES[kind](repo, "", "e")
        with pytest.raises(
            TaxomeshExternalIdConflictError, match=f"^External id 'e' is already used by another {kind}$"
        ):
            SAVES[kind](repo, "", "e")

    def test_a_refusal_that_names_no_key_another_row_holds_is_a_storage_failure(self, kind: str) -> None:
        repo = DjangoRepository()
        with (
            patch("django.db.models.query.QuerySet.get_or_create", side_effect=IntegrityError("refused")),
            pytest.raises(TaxomeshRepositoryError, match="^refused$"),
        ):
            SAVES[kind](repo, "s", "e")
