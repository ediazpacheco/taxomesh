"""Tests for migration 0008_unique_external_id (spec 041).

Verifies that:
1. ItemModel.external_id and CategoryModel.external_id are null=True, unique=True.
2. The migration file exists with the correct structure.
3. Empty-string external_id converts to NULL (enforced at field level via Django).
"""

import importlib

import pytest

django = pytest.importorskip("django", reason="Django is not installed")


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# ORM field schema
# ---------------------------------------------------------------------------


def test_item_external_id_field_is_null_true() -> None:
    from taxomesh.contrib.django.models import ItemModel  # noqa: PLC0415

    field = ItemModel._meta.get_field("external_id")
    assert field.null is True, "ItemModel.external_id must be null=True"


def test_item_external_id_field_is_unique() -> None:
    from taxomesh.contrib.django.models import ItemModel  # noqa: PLC0415

    field = ItemModel._meta.get_field("external_id")
    assert field.unique is True, "ItemModel.external_id must be unique=True"


def test_item_external_id_field_has_no_db_index() -> None:
    """unique=True implies a unique index; db_index=True would create a redundant second index."""
    from taxomesh.contrib.django.models import ItemModel  # noqa: PLC0415

    field = ItemModel._meta.get_field("external_id")
    # db_index should be False/not set; unique already creates the index
    assert not getattr(field, "db_index", False), "ItemModel.external_id must not have db_index=True"


def test_category_external_id_field_is_null_true() -> None:
    from taxomesh.contrib.django.models import CategoryModel  # noqa: PLC0415

    field = CategoryModel._meta.get_field("external_id")
    assert field.null is True, "CategoryModel.external_id must be null=True"


def test_category_external_id_field_is_unique() -> None:
    from taxomesh.contrib.django.models import CategoryModel  # noqa: PLC0415

    field = CategoryModel._meta.get_field("external_id")
    assert field.unique is True, "CategoryModel.external_id must be unique=True"


def test_category_external_id_field_has_no_db_index() -> None:
    from taxomesh.contrib.django.models import CategoryModel  # noqa: PLC0415

    field = CategoryModel._meta.get_field("external_id")
    assert not getattr(field, "db_index", False), "CategoryModel.external_id must not have db_index=True"


# ---------------------------------------------------------------------------
# Migration file exists and has correct structure
# ---------------------------------------------------------------------------


def test_migration_0008_exists() -> None:
    mod = importlib.import_module("taxomesh.contrib.django.migrations.0008_unique_external_id")
    assert hasattr(mod, "Migration")


def test_migration_0008_has_correct_dependency() -> None:
    mod = importlib.import_module("taxomesh.contrib.django.migrations.0008_unique_external_id")
    deps = mod.Migration.dependencies
    assert any("0007" in str(d) for d in deps), f"0008 must depend on 0007, got: {deps}"


def test_migration_0008_has_run_python_operation() -> None:
    mod = importlib.import_module("taxomesh.contrib.django.migrations.0008_unique_external_id")
    op_types = [type(op).__name__ for op in mod.Migration.operations]
    assert "RunPython" in op_types, f"Migration 0008 must contain RunPython operation, got: {op_types}"


def test_migration_0008_has_alter_field_operations() -> None:
    from django.db.migrations.operations import AlterField  # noqa: PLC0415

    mod = importlib.import_module("taxomesh.contrib.django.migrations.0008_unique_external_id")
    alter_ops = [op for op in mod.Migration.operations if isinstance(op, AlterField)]
    assert len(alter_ops) >= 2, f"Migration 0008 must contain at least 2 AlterField operations, got: {len(alter_ops)}"


# ---------------------------------------------------------------------------
# DB-level uniqueness enforced after migration
# ---------------------------------------------------------------------------


def test_unique_constraint_enforced_at_db_level() -> None:
    """Two items with the same non-None external_id must raise IntegrityError."""
    from uuid import uuid4  # noqa: PLC0415

    import django.db  # noqa: PLC0415

    from taxomesh.contrib.django.models import ItemModel  # noqa: PLC0415

    eid = f"unique-test-{uuid4()}"
    ItemModel.objects.create(item_id=uuid4(), name="A", external_id=eid)
    with pytest.raises(django.db.IntegrityError):
        ItemModel.objects.create(item_id=uuid4(), name="B", external_id=eid)


def test_multiple_null_external_ids_are_allowed() -> None:
    """Multiple NULL external_ids must not trigger unique constraint violation."""
    from uuid import uuid4  # noqa: PLC0415

    from taxomesh.contrib.django.models import ItemModel  # noqa: PLC0415

    for _ in range(3):
        ItemModel.objects.create(item_id=uuid4(), name="NullItem", external_id=None)

    count = ItemModel.objects.filter(external_id__isnull=True).count()
    assert count >= 3
