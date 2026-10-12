"""Tests for TaxomeshService.items.get_by_external_id and categories.get_by_external_id."""

from pathlib import Path
from uuid import uuid4

import pytest

from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.domain.models import Category, Item


@pytest.fixture
def svc(tmp_path: Path) -> TaxomeshService:
    return TaxomeshService(repository=JsonRepository(tmp_path / "test.json"))


# ---------------------------------------------------------------------------
# items.get_by_external_id — found cases
# ---------------------------------------------------------------------------


def test_items_get_by_external_id_str_found(svc: TaxomeshService) -> None:
    item = svc.items.create("my-entity", external_id="my-entity-uuid")
    result = svc.items.get_by_external_id("my-entity-uuid")
    assert result is not None
    assert result.item_id == item.item_id


def test_items_get_by_external_id_int_found(svc: TaxomeshService) -> None:
    item = svc.items.create("item-42", external_id=42)
    result = svc.items.get_by_external_id(42)
    assert result is not None
    assert result.item_id == item.item_id


def test_items_get_by_external_id_uuid_found(svc: TaxomeshService) -> None:
    ext = uuid4()
    item = svc.items.create(str(ext), external_id=ext)
    result = svc.items.get_by_external_id(ext)
    assert result is not None
    assert result.item_id == item.item_id


# ---------------------------------------------------------------------------
# items.get_by_external_id — not-found cases
# ---------------------------------------------------------------------------


def test_items_get_by_external_id_not_found(svc: TaxomeshService) -> None:
    svc.items.create("other", external_id="other-id")
    result = svc.items.get_by_external_id("missing-id")
    assert result is None


def test_items_get_by_external_id_empty_store(svc: TaxomeshService) -> None:
    result = svc.items.get_by_external_id("any-id")
    assert result is None


# ---------------------------------------------------------------------------
# items.get_by_external_id — None short-circuit
# ---------------------------------------------------------------------------


def test_items_get_by_external_id_none_input_returns_none(svc: TaxomeshService) -> None:
    """None input must return None without calling repository."""
    result = svc.items.get_by_external_id(None)
    assert result is None


# ---------------------------------------------------------------------------
# items.get_by_external_id — return type
# ---------------------------------------------------------------------------


def test_items_get_by_external_id_returns_item_instance(svc: TaxomeshService) -> None:
    svc.items.create("check-type", external_id="check-type")
    result = svc.items.get_by_external_id("check-type")
    assert isinstance(result, Item)


# ---------------------------------------------------------------------------
# categories.get_by_external_id — found cases
# ---------------------------------------------------------------------------


def test_categories_get_by_external_id_str_found(svc: TaxomeshService) -> None:
    cat = Category(category_id=uuid4(), name="Animals", external_id="ext-animals")
    svc.repository.save_category(cat)
    result = svc.categories.get_by_external_id("ext-animals")
    assert result is not None
    assert result.category_id == cat.category_id


def test_categories_get_by_external_id_int_found(svc: TaxomeshService) -> None:
    cat = Category.model_validate({"category_id": uuid4(), "name": "LevelOne", "external_id": 7})
    svc.repository.save_category(cat)
    result = svc.categories.get_by_external_id(7)
    assert result is not None
    assert result.category_id == cat.category_id


def test_categories_get_by_external_id_uuid_found(svc: TaxomeshService) -> None:
    ext = uuid4()
    cat = Category.model_validate({"category_id": uuid4(), "name": "UUIDCat", "external_id": ext})
    svc.repository.save_category(cat)
    result = svc.categories.get_by_external_id(ext)
    assert result is not None
    assert result.category_id == cat.category_id


# ---------------------------------------------------------------------------
# categories.get_by_external_id — not-found cases
# ---------------------------------------------------------------------------


def test_categories_get_by_external_id_not_found(svc: TaxomeshService) -> None:
    cat = Category(category_id=uuid4(), name="Plants", external_id="ext-plants")
    svc.repository.save_category(cat)
    result = svc.categories.get_by_external_id("nonexistent")
    assert result is None


# ---------------------------------------------------------------------------
# categories.get_by_external_id — None short-circuit
# ---------------------------------------------------------------------------


def test_categories_get_by_external_id_none_input_returns_none(svc: TaxomeshService) -> None:
    result = svc.categories.get_by_external_id(None)
    assert result is None


# ---------------------------------------------------------------------------
# categories.get_by_external_id — root category excluded
# ---------------------------------------------------------------------------


def test_categories_get_by_external_id_root_not_returned(svc: TaxomeshService) -> None:
    """Root category is excluded even if it somehow had an external_id matching the query."""
    result = svc.categories.get_by_external_id("any-ext")
    assert result is None


# ---------------------------------------------------------------------------
# categories.get_by_external_id — return type
# ---------------------------------------------------------------------------


def test_categories_get_by_external_id_returns_category_instance(svc: TaxomeshService) -> None:
    cat = Category(category_id=uuid4(), name="TypeCheck", external_id="tc-ext")
    svc.repository.save_category(cat)
    result = svc.categories.get_by_external_id("tc-ext")
    assert isinstance(result, Category)


# ---------------------------------------------------------------------------
# None input for category
# ---------------------------------------------------------------------------


def test_categories_get_by_external_id_none_does_not_call_repo(
    svc: TaxomeshService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Passing None must short-circuit before the repository is called."""
    called = []

    def _fake_get(external_id: str) -> Category | None:
        called.append(external_id)
        return None

    monkeypatch.setattr(svc.repository, "find_category_by_external_id", _fake_get)
    result = svc.categories.get_by_external_id(None)
    assert result is None
    assert called == [], "Repository must NOT be called when external_id is None"


def test_items_get_by_external_id_none_does_not_call_repo(
    svc: TaxomeshService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Passing None must short-circuit before the repository is called."""
    called = []

    def _fake_get(external_id: str) -> Item | None:
        called.append(external_id)
        return None

    monkeypatch.setattr(svc.repository, "find_item_by_external_id", _fake_get)
    result = svc.items.get_by_external_id(None)
    assert result is None
    assert called == [], "Repository must NOT be called when external_id is None"


# ---------------------------------------------------------------------------
# the widened writes — int and UUID reach every external-id parameter
# ---------------------------------------------------------------------------


def test_categories_create_accepts_an_int_and_stores_its_string_form(svc: TaxomeshService) -> None:
    """``categories.create`` declares ``ExternalId``, so an int needs no ``str()`` at the call site."""
    created = svc.categories.create("IntCat", external_id=42)

    assert created.external_id == "42"
    assert svc.categories.get_by_external_id(42) is not None


def test_categories_update_accepts_a_uuid_and_stores_its_string_form(svc: TaxomeshService) -> None:
    """``categories.update`` takes the same wide type, storing the hyphenated lowercase text."""
    ext = uuid4()
    created = svc.categories.create("UUIDUpdate")

    updated = svc.categories.update(created.category_id, external_id=ext)

    assert updated.external_id == str(ext)


def test_items_update_accepts_an_int_and_stores_its_string_form(svc: TaxomeshService) -> None:
    """``items.update`` completes the set — every external-id parameter admits the wide type."""
    created = svc.items.create("IntItem")

    updated = svc.items.update(created.item_id, external_id=7)

    assert updated.external_id == "7"
