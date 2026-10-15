"""A data migration stores the implicit root once: it creates a missing root, and folds a second one into the first.

With the root stored by ``migrate``, two services that start at the same moment find it, and neither
stores another. A database that two such services left with two roots, before this migration, holds
one afterwards: the root that every service and ``0011`` pick, the one with the lowest key, takes the
child links of the other, and the other is deleted. Then the store is brought to the top-level
invariant, as ``0011`` brings it. The forward function runs here with the live app registry, over rows
planted through the repository port, which is the only way to store those shapes.
"""

import importlib
from pathlib import Path
from types import ModuleType
from uuid import UUID

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
from taxomesh.domain.constants import ROOT_CATEGORY_NAME  # noqa: E402
from taxomesh.domain.models import Category, CategoryParentLink, ItemParentLink  # noqa: E402

pytestmark = pytest.mark.django_db

MIGRATION = "taxomesh.contrib.django.migrations.0012_implicit_root"
MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "taxomesh" / "contrib" / "django" / "migrations"

# Two roots, the first with the lower key, as two services that started at the same moment stored them.
FIRST_ROOT = UUID("00000000-0000-4000-8000-000000000001")
SECOND_ROOT = UUID("00000000-0000-4000-8000-000000000002")


def _migration() -> ModuleType:
    return importlib.import_module(MIGRATION)


def _forward() -> None:
    """Run the forward function over the test database, with a schema editor built but not entered.

    The function reads only the editor's connection; SQLite refuses to enter an editor inside the
    test's transaction.
    """
    operation = _migration().Migration.operations[0]
    operation.code(apps, connection.schema_editor())


def _roots() -> list[UUID]:
    return list(CategoryModel.objects.filter(name=ROOT_CATEGORY_NAME).values_list("pk", flat=True))


def _parents(category: Category) -> dict[UUID, int]:
    return dict(
        CategoryParentLinkModel.objects.filter(category_id=category.category_id).values_list(
            "parent_category_id", "sort_index"
        )
    )


def _rows() -> tuple[set[tuple[UUID, UUID, int]], set[tuple[UUID, UUID, int]], set[tuple[UUID, str]]]:
    """Every parent link, every placement and every category, as stored."""
    return (
        set(CategoryParentLinkModel.objects.values_list("category_id", "parent_category_id", "sort_index")),
        set(ItemParentLinkModel.objects.values_list("item_id", "category_id", "sort_index")),
        set(CategoryModel.objects.values_list("category_id", "name")),
    )


def _without_a_root() -> DjangoRepository:
    """Delete every stored root, as on a database that no service has opened, and return a repository."""
    CategoryModel.objects.filter(name=ROOT_CATEGORY_NAME).delete()
    return DjangoRepository()


class TestTheMigrationStoresOneRoot:
    def test_a_store_with_no_root_gets_one_and_its_categories_are_at_the_top_level(self) -> None:
        repository = _without_a_root()
        loose = Category(name="Loose")
        repository.save_category(loose)

        _forward()

        roots = _roots()
        assert len(roots) == 1
        assert _parents(loose) == {roots[0]: 0}

    def test_a_store_with_one_root_is_left_as_it_is(self) -> None:
        service = TaxomeshService(repository=DjangoRepository())
        music = service.categories.create("Music")
        jazz = service.categories.create("Jazz")
        service.categories.add_parent(jazz, music, sort_index=2)
        song = service.items.create("Song")
        service.items.place_in(song, music, sort_index=5)
        before = _rows()

        _forward()

        assert _rows() == before

    def test_a_second_root_is_folded_into_the_first(self) -> None:
        repository = _without_a_root()
        first = repository.save_category(Category(category_id=FIRST_ROOT, name=ROOT_CATEGORY_NAME))
        second = repository.save_category(Category(category_id=SECOND_ROOT, name=ROOT_CATEGORY_NAME))
        service = TaxomeshService(repository, cache_ttl=0)
        jazz = service.categories.create("Jazz")
        stray = repository.save_category(Category(name="Made by the second"))
        both = repository.save_category(Category(name="Both"))
        song = service.items.create("Song")
        # The shape that two services and then 0011 left: the second root at the top level under the
        # first, its own categories under it, one of them under another category too, and an item in it.
        for child, parent, position in [(second, first, 0), (stray, second, 4), (both, second, 1), (both, jazz, 2)]:
            repository.save_category_parent_link(
                CategoryParentLink(
                    category_id=child.category_id, parent_category_id=parent.category_id, sort_index=position
                )
            )
        repository.save_item_parent_link(ItemParentLink(item_id=song.item_id, category_id=SECOND_ROOT))

        _forward()

        assert _roots() == [FIRST_ROOT]
        assert _parents(stray) == {FIRST_ROOT: 4}
        assert _parents(both) == {jazz.category_id: 2}
        assert _parents(jazz) == {FIRST_ROOT: 0}
        assert not ItemParentLinkModel.objects.filter(item_id=song.item_id).exists()
        later = TaxomeshService(DjangoRepository(), cache_ttl=0)
        assert sorted(category.name for category in later.categories.roots()) == ["Jazz", "Made by the second"]
        assert ROOT_CATEGORY_NAME not in {category.name for category in later.categories.list(enabled=None)}


class TestTheMigrationFile:
    def test_it_follows_the_root_invariant_migration(self) -> None:
        assert _migration().Migration.dependencies == [("taxomesh_contrib_django", "0011_root_invariant")]

    def test_it_is_one_data_operation_with_no_way_back(self) -> None:
        operations = _migration().Migration.operations

        assert len(operations) == 1
        assert isinstance(operations[0], migrations.RunPython)
        assert operations[0].reverse_code is migrations.RunPython.noop

    def test_it_is_the_latest_migration(self) -> None:
        numbered = sorted(path.stem for path in MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.py"))

        assert numbered[-1] == MIGRATION.rsplit(".", 1)[1]
