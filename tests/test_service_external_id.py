"""Tests for TaxomeshService.get_item_by_external_id and get_category_by_external_id (spec 041)."""

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
# get_item_by_external_id — found cases
# ---------------------------------------------------------------------------


def test_get_item_by_external_id_str_found(svc: TaxomeshService) -> None:
    item = svc.create_item("my-entity", external_id="my-entity-uuid")
    result = svc.get_item_by_external_id("my-entity-uuid")
    assert result is not None
    assert result.item_id == item.item_id


def test_get_item_by_external_id_int_found(svc: TaxomeshService) -> None:
    item = svc.create_item("item-42", external_id=42)
    result = svc.get_item_by_external_id(42)
    assert result is not None
    assert result.item_id == item.item_id


def test_get_item_by_external_id_uuid_found(svc: TaxomeshService) -> None:
    ext = uuid4()
    item = svc.create_item(str(ext), external_id=ext)
    result = svc.get_item_by_external_id(ext)
    assert result is not None
    assert result.item_id == item.item_id


# ---------------------------------------------------------------------------
# get_item_by_external_id — not-found cases
# ---------------------------------------------------------------------------


def test_get_item_by_external_id_not_found(svc: TaxomeshService) -> None:
    svc.create_item("other", external_id="other-id")
    result = svc.get_item_by_external_id("missing-id")
    assert result is None


def test_get_item_by_external_id_empty_store(svc: TaxomeshService) -> None:
    result = svc.get_item_by_external_id("any-id")
    assert result is None


# ---------------------------------------------------------------------------
# get_item_by_external_id — None short-circuit
# ---------------------------------------------------------------------------


def test_get_item_by_external_id_none_input_returns_none(svc: TaxomeshService) -> None:
    """None input must return None without calling repository."""
    result = svc.get_item_by_external_id(None)
    assert result is None


# ---------------------------------------------------------------------------
# get_item_by_external_id — return type
# ---------------------------------------------------------------------------


def test_get_item_by_external_id_returns_item_instance(svc: TaxomeshService) -> None:
    svc.create_item("check-type", external_id="check-type")
    result = svc.get_item_by_external_id("check-type")
    assert isinstance(result, Item)


# ---------------------------------------------------------------------------
# get_category_by_external_id — found cases
# ---------------------------------------------------------------------------


def test_get_category_by_external_id_str_found(svc: TaxomeshService) -> None:
    cat = Category(category_id=uuid4(), name="Animals", external_id="ext-animals")
    svc.repository.save_category(cat)
    result = svc.get_category_by_external_id("ext-animals")
    assert result is not None
    assert result.category_id == cat.category_id


def test_get_category_by_external_id_int_found(svc: TaxomeshService) -> None:
    cat = Category(category_id=uuid4(), name="LevelOne", external_id=7)  # type: ignore[arg-type]
    svc.repository.save_category(cat)
    result = svc.get_category_by_external_id(7)
    assert result is not None
    assert result.category_id == cat.category_id


def test_get_category_by_external_id_uuid_found(svc: TaxomeshService) -> None:
    ext = uuid4()
    cat = Category(category_id=uuid4(), name="UUIDCat", external_id=ext)  # type: ignore[arg-type]
    svc.repository.save_category(cat)
    result = svc.get_category_by_external_id(ext)
    assert result is not None
    assert result.category_id == cat.category_id


# ---------------------------------------------------------------------------
# get_category_by_external_id — not-found cases
# ---------------------------------------------------------------------------


def test_get_category_by_external_id_not_found(svc: TaxomeshService) -> None:
    cat = Category(category_id=uuid4(), name="Plants", external_id="ext-plants")
    svc.repository.save_category(cat)
    result = svc.get_category_by_external_id("nonexistent")
    assert result is None


# ---------------------------------------------------------------------------
# get_category_by_external_id — None short-circuit
# ---------------------------------------------------------------------------


def test_get_category_by_external_id_none_input_returns_none(svc: TaxomeshService) -> None:
    result = svc.get_category_by_external_id(None)
    assert result is None


# ---------------------------------------------------------------------------
# get_category_by_external_id — root category excluded
# ---------------------------------------------------------------------------


def test_get_category_by_external_id_root_not_returned(svc: TaxomeshService) -> None:
    """Root category is excluded even if it somehow had an external_id matching the query."""
    result = svc.get_category_by_external_id("any-ext")
    assert result is None


# ---------------------------------------------------------------------------
# get_category_by_external_id — return type
# ---------------------------------------------------------------------------


def test_get_category_by_external_id_returns_category_instance(svc: TaxomeshService) -> None:
    cat = Category(category_id=uuid4(), name="TypeCheck", external_id="tc-ext")
    svc.repository.save_category(cat)
    result = svc.get_category_by_external_id("tc-ext")
    assert isinstance(result, Category)


# ---------------------------------------------------------------------------
# None input for category (US4)
# ---------------------------------------------------------------------------


def test_get_category_by_external_id_none_does_not_call_repo(
    svc: TaxomeshService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Passing None must short-circuit before the repository is called."""
    called = []

    def _fake_get(external_id: str) -> Category | None:
        called.append(external_id)
        return None

    monkeypatch.setattr(svc.repository, "get_category_by_external_id", _fake_get)
    result = svc.get_category_by_external_id(None)
    assert result is None
    assert called == [], "Repository must NOT be called when external_id is None"


def test_get_item_by_external_id_none_does_not_call_repo(
    svc: TaxomeshService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Passing None must short-circuit before the repository is called."""
    called = []

    def _fake_get(external_id: str) -> Item | None:
        called.append(external_id)
        return None

    monkeypatch.setattr(svc.repository, "get_item_by_external_id", _fake_get)
    result = svc.get_item_by_external_id(None)
    assert result is None
    assert called == [], "Repository must NOT be called when external_id is None"
