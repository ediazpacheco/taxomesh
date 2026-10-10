"""Tests for clearing external_id via items.update and categories.update."""

from taxomesh.application.service import TaxomeshService


def test_items_update_clear_sets_none(service: TaxomeshService) -> None:
    """items.update(id, external_id=None) sets external_id to None."""
    item = service.items.create("Widget", external_id="ext-001")
    updated = service.items.update(item.item_id, external_id=None)
    assert updated.external_id is None


def test_items_update_clear_lookup_returns_none(service: TaxomeshService) -> None:
    """After clearing external_id, items.get_by_external_id returns None."""
    item = service.items.create("Widget", external_id="ext-002")
    service.items.update(item.item_id, external_id=None)
    assert service.items.get_by_external_id("ext-002") is None


def test_items_update_reassign_after_clear(service: TaxomeshService) -> None:
    """After clearing A's external_id, assigning it to B succeeds."""
    item_a = service.items.create("A", external_id="shared-id")
    item_b = service.items.create("B")
    service.items.update(item_a.item_id, external_id=None)
    updated_b = service.items.update(item_b.item_id, external_id="shared-id")
    assert updated_b.external_id == "shared-id"


def test_categories_update_clear_sets_none(service: TaxomeshService) -> None:
    """categories.update(id, external_id=None) sets external_id to None."""
    cat = service.categories.create("Gadgets", external_id="cat-ext-001")
    updated = service.categories.update(cat.category_id, external_id=None)
    assert updated.external_id is None


def test_categories_update_clear_lookup_returns_none(service: TaxomeshService) -> None:
    """After clearing external_id, categories.get_by_external_id returns None."""
    cat = service.categories.create("Gadgets", external_id="cat-ext-002")
    service.categories.update(cat.category_id, external_id=None)
    assert service.categories.get_by_external_id("cat-ext-002") is None


def test_categories_update_reassign_after_clear(service: TaxomeshService) -> None:
    """After clearing A's external_id, assigning it to B succeeds."""
    cat_a = service.categories.create("A", external_id="shared-cat-id")
    cat_b = service.categories.create("B")
    service.categories.update(cat_a.category_id, external_id=None)
    updated_b = service.categories.update(cat_b.category_id, external_id="shared-cat-id")
    assert updated_b.external_id == "shared-cat-id"


def test_items_update_omit_external_id_unchanged(service: TaxomeshService) -> None:
    """Omitting external_id from items.update leaves the field unchanged."""
    item = service.items.create("Widget", external_id="keep-me")
    updated = service.items.update(item.item_id, name="Widget v2")
    assert updated.external_id == "keep-me"


def test_categories_update_omit_external_id_unchanged(service: TaxomeshService) -> None:
    """Omitting external_id from categories.update leaves the field unchanged."""
    cat = service.categories.create("Gadgets", external_id="keep-cat")
    updated = service.categories.update(cat.category_id, name="Gadgets v2")
    assert updated.external_id == "keep-cat"


def test_items_update_set_external_id(service: TaxomeshService) -> None:
    """items.update(id, external_id='x') sets external_id to 'x'."""
    item = service.items.create("Widget")
    updated = service.items.update(item.item_id, external_id="new-ext")
    assert updated.external_id == "new-ext"


def test_categories_update_set_external_id(service: TaxomeshService) -> None:
    """categories.update(id, external_id='x') sets external_id to 'x'."""
    cat = service.categories.create("Gadgets")
    updated = service.categories.update(cat.category_id, external_id="new-cat-ext")
    assert updated.external_id == "new-cat-ext"
