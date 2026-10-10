"""A data migration brings a Django store to the top-level invariant, and leaves a normal one alone.

The invariant: a category holds a link to the implicit root exactly when it holds no other parent
link, and no item is placed in the root. The migration deletes a root link held beside another
parent, gives a category with no parent link the root link as ``create`` makes it, and deletes an
item placement in the root. Its forward function runs here with the live app registry, over rows
planted through the repository port, which is the only way to store those shapes.
"""

import importlib
from pathlib import Path
from types import ModuleType
from uuid import UUID, uuid4

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.apps import apps  # noqa: E402
from django.db import connection, migrations  # noqa: E402

from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.application.service import TaxomeshService  # noqa: E402
from taxomesh.contrib.django.models import (  # noqa: E402
    CategoryModel,
    CategoryParentLinkModel,
    ItemParentLinkModel,
)
from taxomesh.domain.models import Category, CategoryParentLink, ItemParentLink  # noqa: E402

pytestmark = pytest.mark.django_db

MIGRATION = "taxomesh.contrib.django.migrations.0011_root_invariant"
MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "taxomesh" / "contrib" / "django" / "migrations"


def _migration() -> ModuleType:
    return importlib.import_module(MIGRATION)


def _forward() -> None:
    """Run the forward function over the test database, with a schema editor built but not entered.

    The function reads only the editor's connection; SQLite refuses to enter an editor inside the
    test's transaction.
    """
    operation = _migration().Migration.operations[0]
    operation.code(apps, connection.schema_editor())


def _rows() -> tuple[set[tuple[UUID, UUID, int]], set[tuple[UUID, UUID, int]], set[tuple[UUID, str]]]:
    """Every parent link, every placement and every category, as stored."""
    return (
        set(CategoryParentLinkModel.objects.values_list("category_id", "parent_category_id", "sort_index")),
        set(ItemParentLinkModel.objects.values_list("item_id", "category_id", "sort_index")),
        set(CategoryModel.objects.values_list("category_id", "name")),
    )


def _parents(category_id: UUID) -> dict[UUID, int]:
    return dict(
        CategoryParentLinkModel.objects.filter(category_id=category_id).values_list("parent_category_id", "sort_index")
    )


class TestTheMigrationFixesAStore:
    def test_each_shape_the_invariant_forbids_is_fixed(self) -> None:
        service = TaxomeshService(repository=DjangoRepository())
        repository = service.repository
        root_id = service._root_id
        music = service.categories.create("Music")
        jazz = service.categories.create("Jazz")
        service.categories.add_parent(jazz.category_id, music.category_id)
        stray = service.categories.create("Stray")
        song = service.items.create("Song")
        service.items.place_in(song.item_id, music.category_id)
        repository.save_category_parent_link(
            CategoryParentLink(category_id=jazz.category_id, parent_category_id=root_id, sort_index=3)
        )
        repository.delete_category_parent_link(stray.category_id, root_id)
        repository.save_item_parent_link(ItemParentLink(item_id=song.item_id, category_id=root_id))

        _forward()

        assert _parents(jazz.category_id) == {music.category_id: 0}
        assert _parents(stray.category_id) == {root_id: 0}
        assert _parents(music.category_id) == {root_id: 0}
        assert set(ItemParentLinkModel.objects.filter(item_id=song.item_id).values_list("category_id", flat=True)) == {
            music.category_id
        }

    def test_a_store_that_holds_the_invariant_is_left_as_it_is(self) -> None:
        service = TaxomeshService(repository=DjangoRepository())
        music = service.categories.create("Music")
        for name in ("Jazz", "Tango"):
            child = service.categories.create(name)
            service.categories.add_parent(child.category_id, music.category_id, sort_index=2)
        song = service.items.create("Song")
        service.items.place_in(song.item_id, music.category_id, sort_index=5)
        service.categories.create("Poetry")
        before = _rows()

        _forward()

        assert _rows() == before

    def test_a_store_with_no_root_row_is_left_as_it_is(self) -> None:
        """Nothing links to a root that is not stored; the service creates it when it first opens."""
        DjangoRepository().save_category(Category(category_id=uuid4(), name="Loose"))
        before = _rows()

        _forward()

        assert _rows() == before


class TestTheMigrationFile:
    def test_it_follows_the_last_schema_migration(self) -> None:
        assert _migration().Migration.dependencies == [
            ("taxomesh_contrib_django", "0010_item_relation_link_target_type_idx")
        ]

    def test_it_is_one_data_operation_with_no_way_back(self) -> None:
        operations = _migration().Migration.operations

        assert len(operations) == 1
        assert isinstance(operations[0], migrations.RunPython)
        assert operations[0].reverse_code is migrations.RunPython.noop

    def test_it_is_the_latest_migration(self) -> None:
        numbered = sorted(path.stem for path in MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.py"))

        assert numbered[-1] == MIGRATION.rsplit(".", 1)[1]
