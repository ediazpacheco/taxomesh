"""Tests for TaxomeshService bulk external-id lookup methods (spec 052)."""

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Category, Item

# ---------------------------------------------------------------------------
# get_items_by_external_ids — normalisation + basic (US1)
# ---------------------------------------------------------------------------


def test_items_whitespace_stripped(service: TaxomeshService) -> None:
    item = service.create_item("Widget", external_id="id-1")
    result = service.get_items_by_external_ids([" id-1 "])
    assert "id-1" in result
    assert result["id-1"].item_id == item.item_id


def test_items_blank_skipped(service: TaxomeshService) -> None:
    result = service.get_items_by_external_ids(["  "])
    assert result == {}


def test_items_duplicates_deduplicated(service: TaxomeshService) -> None:
    item = service.create_item("Widget", external_id="dup-id")
    result = service.get_items_by_external_ids(["dup-id", "dup-id", "dup-id"])
    assert set(result.keys()) == {"dup-id"}
    assert result["dup-id"].item_id == item.item_id


def test_items_generator_input(service: TaxomeshService) -> None:
    item = service.create_item("Widget", external_id="gen-id")

    def id_gen() -> "object":
        yield "gen-id"
        yield "gen-id"

    result = service.get_items_by_external_ids(id_gen())  # type: ignore[arg-type]
    assert "gen-id" in result
    assert result["gen-id"].item_id == item.item_id


def test_items_missing_ids_no_exception(service: TaxomeshService) -> None:
    result = service.get_items_by_external_ids(["no-such-id"])
    assert result == {}


def test_items_result_values_are_item_instances(service: TaxomeshService) -> None:
    service.create_item("Widget", external_id="inst-id")
    result = service.get_items_by_external_ids(["inst-id"])
    assert "inst-id" in result
    assert isinstance(result["inst-id"], Item)


def test_items_empty_input_returns_empty(service: TaxomeshService) -> None:
    result = service.get_items_by_external_ids([])
    assert result == {}


# ---------------------------------------------------------------------------
# get_items_by_external_ids — enabled filter (US2)
# ---------------------------------------------------------------------------


def test_items_enabled_filter_true(service: TaxomeshService) -> None:
    enabled_item = service.create_item("Enabled", external_id="svc-enabled")
    disabled_item = service.create_item("Disabled", external_id="svc-disabled")
    service.update_item(disabled_item.item_id, enabled=False)
    result = service.get_items_by_external_ids(["svc-enabled", "svc-disabled"], enabled=True)
    assert set(result.keys()) == {"svc-enabled"}
    assert result["svc-enabled"].item_id == enabled_item.item_id


def test_items_enabled_filter_false(service: TaxomeshService) -> None:
    service.create_item("Enabled", external_id="svc-enabled2")
    disabled_item = service.create_item("Disabled", external_id="svc-disabled2")
    service.update_item(disabled_item.item_id, enabled=False)
    result = service.get_items_by_external_ids(["svc-enabled2", "svc-disabled2"], enabled=False)
    assert set(result.keys()) == {"svc-disabled2"}


def test_items_enabled_filter_none(service: TaxomeshService) -> None:
    service.create_item("Enabled", external_id="svc-enabled3")
    disabled_item = service.create_item("Disabled", external_id="svc-disabled3")
    service.update_item(disabled_item.item_id, enabled=False)
    result = service.get_items_by_external_ids(["svc-enabled3", "svc-disabled3"], enabled=None)
    assert set(result.keys()) == {"svc-enabled3", "svc-disabled3"}


# ---------------------------------------------------------------------------
# get_categories_by_external_ids — root exclusion + basic (US3)
# ---------------------------------------------------------------------------


def test_categories_root_excluded(service: TaxomeshService) -> None:
    """Root category external_id in input is absent from result."""
    # Assign external_id to root category directly via the repository
    root_cats = [c for c in service.repository.list_categories(enabled=None) if c.name == "__root__"]
    assert len(root_cats) == 1
    root_cat = root_cats[0]
    root_cat.external_id = "root-ext"
    service.repository.save_category(root_cat)

    non_root = service.create_category("Real Cat", external_id="real-cat-ext")
    result = service.get_categories_by_external_ids(["root-ext", "real-cat-ext"])
    assert "root-ext" not in result
    assert "real-cat-ext" in result
    assert result["real-cat-ext"].category_id == non_root.category_id


def test_categories_root_excluded_when_only_id(service: TaxomeshService) -> None:
    """If only the root ID is supplied, result is empty."""
    root_cats = [c for c in service.repository.list_categories(enabled=None) if c.name == "__root__"]
    root_cat = root_cats[0]
    root_cat.external_id = "only-root-ext"
    service.repository.save_category(root_cat)

    result = service.get_categories_by_external_ids(["only-root-ext"])
    assert result == {}


def test_categories_enabled_filter_true(service: TaxomeshService) -> None:
    enabled_cat = service.create_category("Enabled", external_id="cat-svc-enabled")
    disabled_cat = service.create_category("Disabled", external_id="cat-svc-disabled")
    service.update_category(disabled_cat.category_id, enabled=False)
    result = service.get_categories_by_external_ids(["cat-svc-enabled", "cat-svc-disabled"], enabled=True)
    assert set(result.keys()) == {"cat-svc-enabled"}
    assert result["cat-svc-enabled"].category_id == enabled_cat.category_id


def test_categories_enabled_filter_false(service: TaxomeshService) -> None:
    service.create_category("Enabled", external_id="cat-svc-enabled2")
    disabled_cat = service.create_category("Disabled", external_id="cat-svc-disabled2")
    service.update_category(disabled_cat.category_id, enabled=False)
    result = service.get_categories_by_external_ids(["cat-svc-enabled2", "cat-svc-disabled2"], enabled=False)
    assert set(result.keys()) == {"cat-svc-disabled2"}


def test_categories_enabled_filter_none(service: TaxomeshService) -> None:
    service.create_category("Enabled", external_id="cat-svc-enabled3")
    disabled_cat = service.create_category("Disabled", external_id="cat-svc-disabled3")
    service.update_category(disabled_cat.category_id, enabled=False)
    result = service.get_categories_by_external_ids(["cat-svc-enabled3", "cat-svc-disabled3"], enabled=None)
    assert set(result.keys()) == {"cat-svc-enabled3", "cat-svc-disabled3"}


def test_categories_missing_ids_no_exception(service: TaxomeshService) -> None:
    result = service.get_categories_by_external_ids(["no-such-cat-id"])
    assert result == {}


def test_categories_generator_input(service: TaxomeshService) -> None:
    cat = service.create_category("Widget Cat", external_id="cat-gen-id")

    def id_gen() -> "object":
        yield "cat-gen-id"

    result = service.get_categories_by_external_ids(id_gen())  # type: ignore[arg-type]
    assert "cat-gen-id" in result
    assert result["cat-gen-id"].category_id == cat.category_id


def test_categories_result_values_are_category_instances(service: TaxomeshService) -> None:
    service.create_category("Widget Cat", external_id="cat-inst-id")
    result = service.get_categories_by_external_ids(["cat-inst-id"])
    assert "cat-inst-id" in result
    assert isinstance(result["cat-inst-id"], Category)
