"""Tests for clearing external_id via update_item and update_category (spec 043)."""

from taxomesh.application.service import TaxomeshService


def test_update_item_clear_sets_none(service: TaxomeshService) -> None:
    """update_item(id, external_id=None) sets external_id to None."""
    item = service.create_item("Widget", external_id="ext-001")
    updated = service.update_item(item.item_id, external_id=None)
    assert updated.external_id is None


def test_update_item_clear_lookup_returns_none(service: TaxomeshService) -> None:
    """After clearing external_id, get_item_by_external_id returns None."""
    item = service.create_item("Widget", external_id="ext-002")
    service.update_item(item.item_id, external_id=None)
    assert service.get_item_by_external_id("ext-002") is None


def test_update_item_reassign_after_clear(service: TaxomeshService) -> None:
    """After clearing A's external_id, assigning it to B succeeds."""
    item_a = service.create_item("A", external_id="shared-id")
    item_b = service.create_item("B")
    service.update_item(item_a.item_id, external_id=None)
    updated_b = service.update_item(item_b.item_id, external_id="shared-id")
    assert updated_b.external_id == "shared-id"


def test_update_category_clear_sets_none(service: TaxomeshService) -> None:
    """update_category(id, external_id=None) sets external_id to None."""
    cat = service.create_category("Gadgets", external_id="cat-ext-001")
    updated = service.update_category(cat.category_id, external_id=None)
    assert updated.external_id is None


def test_update_category_clear_lookup_returns_none(service: TaxomeshService) -> None:
    """After clearing external_id, get_category_by_external_id returns None."""
    cat = service.create_category("Gadgets", external_id="cat-ext-002")
    service.update_category(cat.category_id, external_id=None)
    assert service.get_category_by_external_id("cat-ext-002") is None


def test_update_category_reassign_after_clear(service: TaxomeshService) -> None:
    """After clearing A's external_id, assigning it to B succeeds."""
    cat_a = service.create_category("A", external_id="shared-cat-id")
    cat_b = service.create_category("B")
    service.update_category(cat_a.category_id, external_id=None)
    updated_b = service.update_category(cat_b.category_id, external_id="shared-cat-id")
    assert updated_b.external_id == "shared-cat-id"


def test_update_item_omit_external_id_unchanged(service: TaxomeshService) -> None:
    """Omitting external_id from update_item leaves the field unchanged."""
    item = service.create_item("Widget", external_id="keep-me")
    updated = service.update_item(item.item_id, name="Widget v2")
    assert updated.external_id == "keep-me"


def test_update_category_omit_external_id_unchanged(service: TaxomeshService) -> None:
    """Omitting external_id from update_category leaves the field unchanged."""
    cat = service.create_category("Gadgets", external_id="keep-cat")
    updated = service.update_category(cat.category_id, name="Gadgets v2")
    assert updated.external_id == "keep-cat"


def test_update_item_set_external_id(service: TaxomeshService) -> None:
    """update_item(id, external_id='x') sets external_id to 'x'."""
    item = service.create_item("Widget")
    updated = service.update_item(item.item_id, external_id="new-ext")
    assert updated.external_id == "new-ext"


def test_update_category_set_external_id(service: TaxomeshService) -> None:
    """update_category(id, external_id='x') sets external_id to 'x'."""
    cat = service.create_category("Gadgets")
    updated = service.update_category(cat.category_id, external_id="new-cat-ext")
    assert updated.external_id == "new-cat-ext"
