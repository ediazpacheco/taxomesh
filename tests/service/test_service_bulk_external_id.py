"""Tests for TaxomeshService bulk external-id lookup methods."""

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Category, Item

# ---------------------------------------------------------------------------
# items.get_many_by_external_id — normalisation + basic
# ---------------------------------------------------------------------------


def test_items_whitespace_is_part_of_the_id(service: TaxomeshService) -> None:
    """Surrounding whitespace is kept, as it is when an external id is stored.

    Stripping each input first would let ``" id-1 "`` find the row stored as ``"id-1"`` while
    ``get_by_external_id(" id-1 ")`` did not. One conversion rule serves writes and lookups
    alike, so the batch answers as the single lookup does.
    """
    service.items.create("Widget", external_id="id-1")

    result = service.items.get_many_by_external_id([" id-1 "])

    assert result == {}
    assert service.items.get_by_external_id(" id-1 ") is None


def test_items_blank_is_not_collapsed_to_empty(service: TaxomeshService) -> None:
    """``"  "`` and ``""`` are two values, as they are when stored.

    Dropping both would leave a row carrying either unreachable through the batch.
    """
    empty = service.items.create("Empty", external_id="")

    result = service.items.get_many_by_external_id(["  ", ""])

    assert set(result) == {""}
    assert result[""].item_id == empty.item_id


def test_items_duplicates_deduplicated(service: TaxomeshService) -> None:
    item = service.items.create("Widget", external_id="dup-id")
    result = service.items.get_many_by_external_id(["dup-id", "dup-id", "dup-id"])
    assert set(result.keys()) == {"dup-id"}
    assert result["dup-id"].item_id == item.item_id


def test_items_take_any_collection(service: TaxomeshService) -> None:
    """A collection that is not a sequence, such as a mapping's keys, serves as a list does."""
    item = service.items.create("Widget", external_id="keys-id")

    result = service.items.get_many_by_external_id({"keys-id": 1}.keys())
    assert "keys-id" in result
    assert result["keys-id"].item_id == item.item_id


def test_items_missing_ids_no_exception(service: TaxomeshService) -> None:
    result = service.items.get_many_by_external_id(["no-such-id"])
    assert result == {}


def test_items_result_values_are_item_instances(service: TaxomeshService) -> None:
    service.items.create("Widget", external_id="inst-id")
    result = service.items.get_many_by_external_id(["inst-id"])
    assert "inst-id" in result
    assert isinstance(result["inst-id"], Item)


def test_items_empty_input_returns_empty(service: TaxomeshService) -> None:
    result = service.items.get_many_by_external_id([])
    assert result == {}


# ---------------------------------------------------------------------------
# items.get_many_by_external_id — enabled filter
# ---------------------------------------------------------------------------


def test_items_enabled_filter_true(service: TaxomeshService) -> None:
    enabled_item = service.items.create("Enabled", external_id="svc-enabled")
    disabled_item = service.items.create("Disabled", external_id="svc-disabled")
    service.items.update(disabled_item.item_id, enabled=False)
    result = service.items.get_many_by_external_id(["svc-enabled", "svc-disabled"], enabled=True)
    assert set(result.keys()) == {"svc-enabled"}
    assert result["svc-enabled"].item_id == enabled_item.item_id


def test_items_enabled_filter_false(service: TaxomeshService) -> None:
    service.items.create("Enabled", external_id="svc-enabled2")
    disabled_item = service.items.create("Disabled", external_id="svc-disabled2")
    service.items.update(disabled_item.item_id, enabled=False)
    result = service.items.get_many_by_external_id(["svc-enabled2", "svc-disabled2"], enabled=False)
    assert set(result.keys()) == {"svc-disabled2"}


def test_items_enabled_filter_none(service: TaxomeshService) -> None:
    service.items.create("Enabled", external_id="svc-enabled3")
    disabled_item = service.items.create("Disabled", external_id="svc-disabled3")
    service.items.update(disabled_item.item_id, enabled=False)
    result = service.items.get_many_by_external_id(["svc-enabled3", "svc-disabled3"], enabled=None)
    assert set(result.keys()) == {"svc-enabled3", "svc-disabled3"}


# ---------------------------------------------------------------------------
# categories.get_many_by_external_id — root exclusion + basic
# ---------------------------------------------------------------------------


def test_categories_root_excluded(service: TaxomeshService) -> None:
    """Root category external_id in input is absent from result."""
    # Assign external_id to root category directly via the repository
    root_cats = [c for c in service.repository.list_categories(enabled=None) if c.name == "__root__"]
    assert len(root_cats) == 1
    root_cat = root_cats[0]
    service.repository.save_category(root_cat.model_copy(update={"external_id": "root-ext"}))

    non_root = service.categories.create("Real Cat", external_id="real-cat-ext")
    result = service.categories.get_many_by_external_id(["root-ext", "real-cat-ext"])
    assert "root-ext" not in result
    assert "real-cat-ext" in result
    assert result["real-cat-ext"].category_id == non_root.category_id


def test_categories_root_excluded_when_only_id(service: TaxomeshService) -> None:
    """If only the root ID is supplied, result is empty."""
    root_cats = [c for c in service.repository.list_categories(enabled=None) if c.name == "__root__"]
    root_cat = root_cats[0]
    service.repository.save_category(root_cat.model_copy(update={"external_id": "only-root-ext"}))

    result = service.categories.get_many_by_external_id(["only-root-ext"])
    assert result == {}


def test_categories_enabled_filter_true(service: TaxomeshService) -> None:
    enabled_cat = service.categories.create("Enabled", external_id="cat-svc-enabled")
    disabled_cat = service.categories.create("Disabled", external_id="cat-svc-disabled")
    service.categories.update(disabled_cat.category_id, enabled=False)
    result = service.categories.get_many_by_external_id(["cat-svc-enabled", "cat-svc-disabled"], enabled=True)
    assert set(result.keys()) == {"cat-svc-enabled"}
    assert result["cat-svc-enabled"].category_id == enabled_cat.category_id


def test_categories_enabled_filter_false(service: TaxomeshService) -> None:
    service.categories.create("Enabled", external_id="cat-svc-enabled2")
    disabled_cat = service.categories.create("Disabled", external_id="cat-svc-disabled2")
    service.categories.update(disabled_cat.category_id, enabled=False)
    result = service.categories.get_many_by_external_id(["cat-svc-enabled2", "cat-svc-disabled2"], enabled=False)
    assert set(result.keys()) == {"cat-svc-disabled2"}


def test_categories_enabled_filter_none(service: TaxomeshService) -> None:
    service.categories.create("Enabled", external_id="cat-svc-enabled3")
    disabled_cat = service.categories.create("Disabled", external_id="cat-svc-disabled3")
    service.categories.update(disabled_cat.category_id, enabled=False)
    result = service.categories.get_many_by_external_id(["cat-svc-enabled3", "cat-svc-disabled3"], enabled=None)
    assert set(result.keys()) == {"cat-svc-enabled3", "cat-svc-disabled3"}


def test_categories_missing_ids_no_exception(service: TaxomeshService) -> None:
    result = service.categories.get_many_by_external_id(["no-such-cat-id"])
    assert result == {}


def test_categories_take_any_collection(service: TaxomeshService) -> None:
    """A collection that is not a sequence, such as a mapping's keys, serves as a list does."""
    cat = service.categories.create("Widget Cat", external_id="cat-keys-id")

    result = service.categories.get_many_by_external_id({"cat-keys-id": 1}.keys())
    assert "cat-keys-id" in result
    assert result["cat-keys-id"].category_id == cat.category_id


def test_categories_result_values_are_category_instances(service: TaxomeshService) -> None:
    service.categories.create("Widget Cat", external_id="cat-inst-id")
    result = service.categories.get_many_by_external_id(["cat-inst-id"])
    assert "cat-inst-id" in result
    assert isinstance(result["cat-inst-id"], Category)


# ---------------------------------------------------------------------------
# both collections — ``None`` is dropped, never stringified
# ---------------------------------------------------------------------------


def test_items_none_is_dropped_not_looked_up_as_text(service: TaxomeshService) -> None:
    """A ``None`` in the batch contributes no key, so it cannot match the text ``"None"``.

    ``ExternalId`` admits ``None``, and the single conversion rule refuses to turn it into the
    string ``"None"`` (``taxomesh/domain/types.py``). The batch helper must defer to that rule
    rather than apply its own ``str(value)``, which would let ``None`` address a real row — the
    opposite of the "no match, without a storage read" meaning ``get_by_external_id`` gives it.
    """
    service.items.create("Decoy", external_id="None")

    result = service.items.get_many_by_external_id([None])

    assert result == {}


def test_categories_none_is_dropped_not_looked_up_as_text(service: TaxomeshService) -> None:
    """The category batch lookup drops ``None`` for the same reason."""
    service.categories.create("Decoy", external_id="None")

    result = service.categories.get_many_by_external_id([None])

    assert result == {}


# ---------------------------------------------------------------------------
# both collections — the batch uses the one conversion rule
# ---------------------------------------------------------------------------

# Stored exactly as written by the one rule; a batch that stripped or dropped them would miss them.
_KEPT_AS_WRITTEN = [" 42 ", "", "  "]
_KEPT_AS_WRITTEN_IDS = ["padded", "empty", "blank"]


class TestTheBatchUsesTheOneRule:
    """A value written is found again by the batch, exactly as by the single lookup.

    One conversion rule, shared by writes and lookups, means a value written and a value looked up
    can never normalise differently. A second step of the batch's own, stripping and then dropping
    what was left blank, would let ``get_by_external_id`` find a row stored as ``" 42 "`` or ``""``
    that ``get_many_by_external_id`` missed. Each case stores a
    row carrying the value, because a sentinel lookup against a store without one proves nothing.
    """

    @pytest.mark.parametrize("value", _KEPT_AS_WRITTEN, ids=_KEPT_AS_WRITTEN_IDS)
    def test_items(self, service: TaxomeshService, value: str) -> None:
        """The item batch finds the row the single item lookup finds."""
        item = service.items.create("Stored", external_id=value)

        result = service.items.get_many_by_external_id([value])

        assert set(result) == {value}
        assert result[value].item_id == item.item_id
        single = service.items.get_by_external_id(value)
        assert single is not None and single.item_id == item.item_id

    @pytest.mark.parametrize("value", _KEPT_AS_WRITTEN, ids=_KEPT_AS_WRITTEN_IDS)
    def test_categories(self, service: TaxomeshService, value: str) -> None:
        """The category batch finds the row the single category lookup finds."""
        category = service.categories.create("Stored", external_id=value)

        result = service.categories.get_many_by_external_id([value])

        assert set(result) == {value}
        assert result[value].category_id == category.category_id
        single = service.categories.get_by_external_id(value)
        assert single is not None and single.category_id == category.category_id
