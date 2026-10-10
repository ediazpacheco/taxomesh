"""Every ``update`` field defaults to ``UNSET``, which leaves the field as it is.

Any other value replaces the field. ``None`` is a value only where the field is nullable, which is
``external_id`` alone, and there it clears the field. For every other field ``None`` is the wrong
type, refused with ``TypeError`` as ``int(None)`` is, and the update stores nothing.
"""

import inspect
import re
from collections.abc import Callable
from typing import Any

import pytest

from taxomesh import UNSET
from taxomesh.application.collections.categories import CategoryCollection
from taxomesh.application.collections.items import ItemCollection
from taxomesh.application.collections.tags import TagCollection
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Category, Item, Tag

# Any: the fields are passed by name from a table, as a caller spreading its own mapping would.
type Update = Callable[[TaxomeshService, dict[str, Any]], object]
type Read = Callable[[TaxomeshService], object]


def _category(service: TaxomeshService) -> Category:
    """A category with every field set, so a field left alone is distinguishable from a default."""
    row = service.categories.create(
        "Music", description="All music", slug="music", external_id="cat:music", metadata={"k": 1}
    )
    return service.categories.update(row.category_id, enabled=False)


def _item(service: TaxomeshService) -> Item:
    """An item with every field set."""
    row = service.items.create("Song", slug="song", external_id="item:song", metadata={"k": 1})
    return service.items.update(row.item_id, enabled=False)


def _tag(service: TaxomeshService) -> Tag:
    """A tag with every field set."""
    return service.tags.create("live", metadata={"k": 1})


FIELDS: dict[str, tuple[str, ...]] = {
    "categories": ("name", "description", "slug", "external_id", "enabled", "metadata"),
    "items": ("name", "slug", "external_id", "enabled", "metadata"),
    "tags": ("name", "metadata"),
}

# A value different from the one each row above holds.
NEW_VALUE: dict[str, object] = {
    "name": "Renamed",
    "description": "Changed",
    "slug": "changed",
    "external_id": "changed",
    "enabled": True,
    "metadata": {"k": 2},
}


def _cases() -> list[tuple[str, Callable[[TaxomeshService], tuple[Update, Read]]]]:
    """For each collection, a builder returning its update and its read of the stored row."""

    def categories(service: TaxomeshService) -> tuple[Update, Read]:
        row = _category(service)
        return (
            lambda s, fields: s.categories.update(row.category_id, **fields),
            lambda s: s.repository.find_category(row.category_id),
        )

    def items(service: TaxomeshService) -> tuple[Update, Read]:
        row = _item(service)
        return (
            lambda s, fields: s.items.update(row.item_id, **fields),
            lambda s: s.repository.find_item(row.item_id),
        )

    def tags(service: TaxomeshService) -> tuple[Update, Read]:
        row = _tag(service)
        return (
            lambda s, fields: s.tags.update(row.tag_id, **fields),
            lambda s: s.repository.find_tag(row.tag_id),
        )

    return [("categories", categories), ("items", items), ("tags", tags)]


CASES = _cases()
FIELD_CASES = [(name, build, field) for name, build in CASES for field in FIELDS[name]]
FIELD_IDS = [f"{name}.{field}" for name, _, field in FIELD_CASES]
NOT_NULLABLE = [case for case in FIELD_CASES if case[2] != "external_id"]
NOT_NULLABLE_IDS = [f"{name}.{field}" for name, _, field in NOT_NULLABLE]
NULLABLE = [case for case in FIELD_CASES if case[2] == "external_id"]
NULLABLE_IDS = [f"{name}.{field}" for name, _, field in NULLABLE]

UPDATES: list[tuple[str, Callable[..., object]]] = [
    ("categories", CategoryCollection.update),
    ("items", ItemCollection.update),
    ("tags", TagCollection.update),
]


@pytest.mark.parametrize(("name", "update"), UPDATES, ids=[name for name, _ in UPDATES])
def test_every_field_defaults_to_unset(name: str, update: Callable[..., object]) -> None:
    """The signature says it: every field's default is ``UNSET``, and nothing else is."""
    parameters = inspect.signature(update).parameters

    assert {field: parameters[field].default for field in FIELDS[name]} == dict.fromkeys(FIELDS[name], UNSET)


@pytest.mark.parametrize(("name", "build", "field"), FIELD_CASES, ids=FIELD_IDS)
def test_only_the_field_given_changes(
    service: TaxomeshService, name: str, build: Callable[[TaxomeshService], tuple[Update, Read]], field: str
) -> None:
    update, read = build(service)
    before = read(service)
    assert isinstance(before, (Category, Item, Tag))

    update(service, {field: NEW_VALUE[field]})

    after = read(service)
    assert isinstance(after, (Category, Item, Tag))
    fields_before = before.model_dump()
    changed = {key for key, value in after.model_dump().items() if fields_before[key] != value}
    assert changed - {"updated_at", "version"} == {field}


@pytest.mark.parametrize(("name", "build", "field"), NULLABLE, ids=NULLABLE_IDS)
def test_none_clears_the_nullable_field(
    service: TaxomeshService, name: str, build: Callable[[TaxomeshService], tuple[Update, Read]], field: str
) -> None:
    update, read = build(service)

    update(service, {field: None})

    after = read(service)
    assert isinstance(after, (Category, Item))
    assert after.external_id is None


@pytest.mark.parametrize(("name", "build", "field"), NOT_NULLABLE, ids=NOT_NULLABLE_IDS)
def test_none_is_refused_for_every_other_field(
    service: TaxomeshService, name: str, build: Callable[[TaxomeshService], tuple[Update, Read]], field: str
) -> None:
    update, read = build(service)
    before = read(service)

    with pytest.raises(TypeError, match=re.escape(f"{field} cannot be None: UNSET keeps the stored value")):
        update(service, {field: None})

    assert read(service) == before
