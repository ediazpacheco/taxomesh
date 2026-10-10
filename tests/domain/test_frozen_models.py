"""Rows are frozen: a field refuses assignment, and ``metadata`` refuses change all the way down.

A row a caller holds is never changed in place. ``model_copy(update=…)`` is how a changed row is
made, and it leaves the original as it was. ``metadata`` is the caller's own JSON: its dicts and
lists refuse every in-place change with ``TypeError``, while staying a ``dict`` and a ``list`` to
every reader, so equality with a literal, ``json.dumps``, pickling and ``model_dump`` behave as
they would for plain containers.
"""

import copy
import json
import pickle
import re
from collections.abc import Callable
from enum import IntEnum, StrEnum
from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel

from taxomesh.domain.models import (
    Category,
    CategoryParentLink,
    Item,
    ItemParentLink,
    ItemRelationLink,
    ItemTagLink,
    Tag,
)
from taxomesh.domain.types import FrozenList


class Mood(StrEnum):
    CALM = "calm"
    LOUD = "loud"


class Rank(IntEnum):
    FIRST = 1


class Meters(float):
    """A ``float`` subclass, as a unit type might be."""


ROWS: dict[str, Callable[[], BaseModel]] = {
    "Category": lambda: Category(name="Tango"),
    "Item": lambda: Item(name="Percanta"),
    "Tag": lambda: Tag(name="lunfardo"),
    "CategoryParentLink": lambda: CategoryParentLink(category_id=uuid4(), parent_category_id=uuid4()),
    "ItemParentLink": lambda: ItemParentLink(item_id=uuid4(), category_id=uuid4()),
    "ItemRelationLink": lambda: ItemRelationLink(
        source_item_id=uuid4(), target_item_id=uuid4(), relation_type="covers"
    ),
    "ItemTagLink": lambda: ItemTagLink(tag_id=uuid4(), item_id=uuid4()),
}

# The field each model is assigned to, and a value of the right type for it.
ASSIGNMENTS: dict[str, tuple[str, object]] = {
    "Category": ("name", "Milonga"),
    "Item": ("enabled", False),
    "Tag": ("name", "slang"),
    "CategoryParentLink": ("sort_index", 3),
    "ItemParentLink": ("sort_index", 3),
    "ItemRelationLink": ("sort_index", 3),
    "ItemTagLink": ("item_id", uuid4()),
}


# Any: a metadata payload, whose values the tests index as the nested JSON they are.
def _payload() -> dict[str, Any]:
    """Return a fresh nested payload, so that no test can change another's."""
    return {
        "lunfardo": {"headword": "percanta", "regions": ["Argentina", "Uruguay"], "senses": [{"id": "s1"}]},
        "count": 2,
    }


type MetadataRow = Category | Item | Tag | ItemRelationLink

# Any: each model's metadata field is dict[str, Any].
METADATA_ROWS: dict[str, Callable[[dict[str, Any]], MetadataRow]] = {
    "Category": lambda metadata: Category(name="Tango", metadata=metadata),
    "Item": lambda metadata: Item(name="Percanta", metadata=metadata),
    "Tag": lambda metadata: Tag(name="lunfardo", metadata=metadata),
    "ItemRelationLink": lambda metadata: ItemRelationLink(
        source_item_id=uuid4(), target_item_id=uuid4(), relation_type="covers", metadata=metadata
    ),
}

DEFAULT_METADATA_ROWS: dict[str, Callable[[], MetadataRow]] = {
    "Category": lambda: Category(name="Tango"),
    "Item": lambda: Item(name="Percanta"),
    "Tag": lambda: Tag(name="lunfardo"),
    "ItemRelationLink": lambda: ItemRelationLink(
        source_item_id=uuid4(), target_item_id=uuid4(), relation_type="covers"
    ),
}


@pytest.mark.parametrize("model", ROWS)
class TestAFrozenRow:
    """Each of the seven models refuses assignment and makes a changed copy instead."""

    def test_assigning_a_field_raises_a_value_error(self, model: str) -> None:
        """Pydantic's own frozen-instance error, which is a ``ValueError``."""
        row = ROWS[model]()
        field, value = ASSIGNMENTS[model]
        with pytest.raises(ValueError, match="frozen"):
            setattr(row, field, value)

    def test_a_refused_assignment_leaves_the_row_as_it_was(self, model: str) -> None:
        """The field keeps its value after the refusal."""
        row = ROWS[model]()
        field, value = ASSIGNMENTS[model]
        before = getattr(row, field)
        with pytest.raises(ValueError, match="frozen"):
            setattr(row, field, value)
        assert getattr(row, field) == before

    def test_model_copy_returns_a_new_row_and_leaves_the_original(self, model: str) -> None:
        """The stdlib's value idiom, as ``dataclasses.replace`` is."""
        row = ROWS[model]()
        field, value = ASSIGNMENTS[model]
        before = getattr(row, field)
        changed = row.model_copy(update={field: value})
        assert changed is not row
        assert getattr(changed, field) == value
        assert getattr(row, field) == before


@pytest.mark.parametrize("model", METADATA_ROWS)
class TestFrozenMetadata:
    """``metadata`` refuses change at every depth, and still reads as plain JSON containers."""

    def test_a_top_level_change_raises(self, model: str) -> None:
        metadata = METADATA_ROWS[model](_payload()).metadata
        message = "metadata is frozen: change a copy, made with dict() or list(), and save the copy"
        with pytest.raises(TypeError, match=re.escape(message)):
            metadata["added"] = 1
        with pytest.raises(TypeError):
            del metadata["count"]
        with pytest.raises(TypeError):
            metadata.update({"added": 1})
        with pytest.raises(TypeError):
            metadata.pop("count")
        with pytest.raises(TypeError):
            metadata.setdefault("added", 1)
        with pytest.raises(TypeError):
            metadata.clear()
        assert metadata == _payload()

    def test_a_nested_dict_change_raises(self, model: str) -> None:
        metadata = METADATA_ROWS[model](_payload()).metadata
        with pytest.raises(TypeError):
            metadata["lunfardo"]["headword"] = "mina"
        with pytest.raises(TypeError):
            metadata["lunfardo"]["senses"][0]["id"] = "s2"
        assert metadata == _payload()

    def test_a_nested_list_change_raises(self, model: str) -> None:
        metadata = METADATA_ROWS[model](_payload()).metadata
        regions = metadata["lunfardo"]["regions"]
        with pytest.raises(TypeError):
            regions.append("Chile")
        with pytest.raises(TypeError):
            regions[0] = "Chile"
        with pytest.raises(TypeError):
            regions.extend(["Chile"])
        with pytest.raises(TypeError):
            regions.sort()
        with pytest.raises(TypeError):
            regions += ["Chile"]
        assert metadata == _payload()

    def test_the_callers_dict_is_not_aliased(self, model: str) -> None:
        """Changing the dict passed in, at any depth, does not reach the row."""
        passed = _payload()
        row = METADATA_ROWS[model](passed)
        passed["count"] = 3
        passed["lunfardo"]["regions"].append("Chile")
        assert row.metadata == _payload()

    def test_it_reads_as_plain_containers(self, model: str) -> None:
        """A dict and a list to every reader: equality, ``isinstance`` and ``json.dumps``."""
        metadata = METADATA_ROWS[model](_payload()).metadata
        assert metadata == _payload()
        assert isinstance(metadata, dict)
        assert isinstance(metadata["lunfardo"]["regions"], list)
        assert json.loads(json.dumps(metadata)) == _payload()

    def test_a_copy_is_the_callers_to_change(self, model: str) -> None:
        """``dict(…)`` and ``.copy()`` give a plain, changeable dict, as for any mapping."""
        metadata = METADATA_ROWS[model](_payload()).metadata
        for mutable in (dict(metadata), metadata.copy()):
            mutable["added"] = 1
            assert type(mutable) is dict
        assert metadata == _payload()

    def test_a_row_pickles_and_copies(self, model: str) -> None:
        """A pickled row comes back equal and still frozen, and copies are equal."""
        row = METADATA_ROWS[model](_payload())
        restored = pickle.loads(pickle.dumps(row))
        assert restored == row
        with pytest.raises(TypeError):
            restored.metadata["lunfardo"]["regions"].append("Chile")
        assert copy.copy(row) == row
        assert copy.deepcopy(row) == row

    def test_model_dump_gives_plain_containers(self, model: str) -> None:
        """What a serializer or a file adapter receives is plain JSON."""
        row = METADATA_ROWS[model](_payload())
        for dumped in (row.model_dump()["metadata"], row.model_dump(mode="json")["metadata"]):
            assert type(dumped) is dict
            assert type(dumped["lunfardo"]) is dict
            assert type(dumped["lunfardo"]["regions"]) is list
            assert dumped == _payload()

    def test_a_tuple_becomes_a_frozen_list_and_its_elements_are_frozen(self, model: str) -> None:
        """A tuple is held as the list every backend reads it back as, so a row equals its stored self."""
        pair = METADATA_ROWS[model]({"pair": ({"a": 1}, [2])}).metadata["pair"]
        assert type(pair) is FrozenList
        assert pair == [{"a": 1}, [2]]
        with pytest.raises(TypeError):
            pair.append(3)
        with pytest.raises(TypeError):
            pair[0]["a"] = 2
        with pytest.raises(TypeError):
            pair[1].append(3)

    def test_a_str_int_or_float_subclass_becomes_its_plain_value(self, model: str) -> None:
        """An enum member is held as the value every backend reads back, a key as well as a value."""
        metadata = METADATA_ROWS[model](
            {"mood": Mood.CALM, "rank": [Rank.FIRST], Mood.LOUD: Meters(1.5), "on": True, "in": {Mood.CALM: 1}}
        ).metadata
        assert metadata == {"mood": "calm", "rank": [1], "loud": 1.5, "on": True, "in": {"calm": 1}}
        assert [type(key) for key in (*metadata, *metadata["in"])] == [str] * 6
        assert [type(metadata["mood"]), type(metadata["rank"][0]), type(metadata["loud"])] == [str, int, float]
        assert metadata["on"] is True

    def test_the_default_is_frozen_too(self, model: str) -> None:
        """A row built without metadata refuses a change to its empty dict."""
        row = DEFAULT_METADATA_ROWS[model]()
        with pytest.raises(TypeError):
            row.metadata["added"] = 1
