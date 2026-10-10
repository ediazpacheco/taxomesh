"""Metadata is plain JSON, refused otherwise before anything is written, on every backend.

Plain JSON is, at any depth, a dict with ``str`` keys, a list or tuple, a ``str``, an ``int``, a
finite ``float``, a ``bool`` or ``None``. Anything else would be stored differently by each
backend, or not at all: a file store would write a ``datetime`` as text, and an ``object()`` would
fail only at the file write, with the row already kept in memory and every later write failing with
it. The check runs where a caller's metadata comes in, ``create``, ``update`` and ``relate``, and
not on the model, so a store already holding such a value still loads.

A value of a ``str``, ``int`` or ``float`` subclass, an enum member say, is plain JSON held as its
plain value, and a value that contains itself is refused, as ``json.dumps`` refuses it.
"""

import math
import re
from collections import UserDict
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import IntEnum, StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any
from uuid import uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Category, Item, ItemRelationLink, Tag
from taxomesh.domain.types import FrozenList
from taxomesh.exceptions import TaxomeshValidationError
from taxomesh.repositories import JsonRepository, YamlRepository

# Any: each value is one a caller may hand in as metadata, whatever its type.
NOT_JSON: dict[str, Any] = {
    "an object": object(),
    "a set": {1, 2},
    "a datetime": datetime(2024, 1, 1, tzinfo=UTC),
    "a date": date(2024, 1, 1),
    "a UUID": uuid4(),
    "a Decimal": Decimal("1.5"),
    "bytes": b"x",
    "NaN": math.nan,
    "infinity": math.inf,
}

# Any: metadata as a caller hands it in, its values of every type.
type Write = Callable[[TaxomeshService, dict[str, Any]], object]

WRITES: dict[str, Write] = {
    "category create": lambda svc, metadata: svc.categories.create("C", metadata=metadata),
    "category update": lambda svc, metadata: svc.categories.update(svc.categories.create("C"), metadata=metadata),
    "item create": lambda svc, metadata: svc.items.create("I", metadata=metadata),
    "item update": lambda svc, metadata: svc.items.update(svc.items.create("I"), metadata=metadata),
    "tag create": lambda svc, metadata: svc.tags.create("T", metadata=metadata),
    "tag update": lambda svc, metadata: svc.tags.update(svc.tags.create("T"), metadata=metadata),
    "relate": lambda svc, metadata: svc.items.relate(
        svc.items.create("A"), svc.items.create("B"), "covers", metadata=metadata
    ),
}


# Any: a mapping that is no dict is passed where the annotation asks for a dict, as an untyped
# caller can.
def untyped(value: object) -> Any:
    """Return ``value`` typed as anything, so a call can pass what its annotation refuses."""
    return value


MAPPINGS: dict[str, Callable[[dict[str, object]], Mapping[str, object]]] = {
    "a mappingproxy": MappingProxyType,
    "a UserDict": UserDict,
}


def _stored(svc: TaxomeshService) -> list[dict[str, object]]:
    """Every row's metadata, as a plain dict, so a refused write can be shown to store nothing."""
    rows: list[Category | Item | Tag | ItemRelationLink] = [
        *svc.categories.list(enabled=None),
        *svc.items.list(enabled=None),
        *svc.tags.list(),
        *(link for item in svc.items.list(enabled=None) for link in svc.items.list_relations(item)),
    ]
    return [dict(row.metadata) for row in rows]


@pytest.mark.parametrize("write", WRITES.values(), ids=WRITES.keys())
@pytest.mark.parametrize("value", NOT_JSON.values(), ids=NOT_JSON.keys())
def test_a_value_that_is_not_json_is_refused(service: TaxomeshService, write: Write, value: object) -> None:
    """Refused with ``TaxomeshValidationError``, a value of the dict being refused, nested or not."""
    for metadata in ({"k": value}, {"outer": [{"k": value}]}):
        with pytest.raises(TaxomeshValidationError, match="metadata"):
            write(service, metadata)


@pytest.mark.parametrize("write", WRITES.values(), ids=WRITES.keys())
@pytest.mark.parametrize("mapping", MAPPINGS.values(), ids=MAPPINGS.keys())
def test_a_mapping_that_is_not_a_dict_is_checked_as_a_dict_is(
    service: TaxomeshService, write: Write, mapping: Callable[[dict[str, object]], Mapping[str, object]]
) -> None:
    """The model takes any mapping as a dict, so what it holds is checked as a dict's values are."""
    with pytest.raises(TaxomeshValidationError, match=re.escape("metadata['k'] is of type object, which is not JSON")):
        write(service, untyped(mapping({"k": object()})))
    assert service.tags.create("next").name == "next"


def test_plain_json_in_a_mapping_that_is_not_a_dict_is_stored(service: TaxomeshService) -> None:
    category = service.categories.create("C", metadata=untyped(MappingProxyType({"k": 1})))
    assert service.categories[category.category_id].metadata == {"k": 1}


@pytest.mark.parametrize("write", WRITES.values(), ids=WRITES.keys())
def test_a_key_that_is_not_text_is_refused_at_any_depth(service: TaxomeshService, write: Write) -> None:
    """JSON keys are text: a nested integer key would come back as ``"1"`` from a file store."""
    with pytest.raises(TaxomeshValidationError, match="metadata"):
        write(service, {"outer": {1: "x"}})


def test_a_refused_write_stores_nothing_and_the_store_takes_the_next(service: TaxomeshService) -> None:
    """The store is left as it was, and the next write is stored: nothing is kept half-written."""
    tag = service.tags.create("kept", metadata={"k": 1})
    before = _stored(service)

    with pytest.raises(TaxomeshValidationError):
        service.tags.create("refused", metadata={"k": object()})
    with pytest.raises(TaxomeshValidationError):
        service.tags.update(tag, metadata={"k": object()})

    assert _stored(service) == before
    assert service.items.create("next", metadata={"k": 2}).metadata == {"k": 2}


def test_plain_json_is_stored_as_given(service: TaxomeshService) -> None:
    metadata: dict[str, object] = {
        "s": "x",
        "i": 1,
        "f": 1.5,
        "b": True,
        "n": None,
        "l": [1, {"k": "v"}],
        "d": {"e": {}},
    }
    category = service.categories.create("C", metadata=metadata)
    assert service.categories[category.category_id].metadata == metadata


def _read_afresh(service: TaxomeshService) -> TaxomeshService:
    """A service reading the store afresh: a file store reopened, any other with nothing cached."""
    repository = service.repository
    path = repository.describe().path
    if isinstance(repository, JsonRepository | YamlRepository) and path is not None:
        return TaxomeshService(repository=type(repository)(path))
    return TaxomeshService(repository=repository, cache_ttl=0)


def test_a_tuple_is_held_as_a_list_at_once(service: TaxomeshService) -> None:
    """A tuple becomes the list every backend reads back, so a created row equals its stored self."""
    item = service.items.create("I", metadata={"t": (1, (2, 3))})

    held = item.metadata["t"]
    assert type(held) is FrozenList
    assert type(held[1]) is FrozenList
    assert item.metadata == {"t": [1, [2, 3]]}
    assert _read_afresh(service).items[item] == item


class Mood(StrEnum):
    CALM = "calm"


class Rank(IntEnum):
    FIRST = 1


class Meters(float):
    """A ``float`` subclass, as a unit type might be."""


def test_a_str_int_or_float_subclass_is_held_as_its_plain_value_at_once(service: TaxomeshService) -> None:
    """An enum member is plain JSON, held as the value every backend reads back, a key as well."""
    item = service.items.create("I", metadata={"mood": Mood.CALM, Mood.CALM: [Rank.FIRST, Meters(1.5)], "on": True})

    assert item.metadata == {"mood": "calm", "calm": [1, 1.5], "on": True}
    assert [type(key) for key in item.metadata] == [str, str, str]
    assert [type(value) for value in (item.metadata["mood"], *item.metadata["calm"])] == [str, int, float]
    assert item.metadata["on"] is True
    assert _read_afresh(service).items[item] == item


def _containing_itself() -> dict[str, object]:
    """Three values that contain themselves: a dict, a list, and a dict through its child."""
    looped: dict[str, object] = {}
    looped["self"] = looped
    listed: list[object] = []
    listed.append(listed)
    child: dict[str, object] = {}
    through: dict[str, object] = {"child": child}
    child["back"] = through
    return {"a dict": looped, "a list": listed, "through a child": through}


@pytest.mark.parametrize("write", WRITES.values(), ids=WRITES.keys())
@pytest.mark.parametrize("shape", ["a dict", "a list", "through a child"])
def test_a_value_that_contains_itself_is_refused(service: TaxomeshService, write: Write, shape: str) -> None:
    """JSON cannot hold it, as ``json.dumps`` refuses it: refused naming where it starts."""
    with pytest.raises(TaxomeshValidationError, match=re.escape("metadata['a'] contains itself")):
        write(service, {"a": _containing_itself()[shape]})


def test_a_refused_value_that_contains_itself_stores_nothing(service: TaxomeshService) -> None:
    tag = service.tags.create("kept", metadata={"k": 1})
    before = _stored(service)

    with pytest.raises(TaxomeshValidationError):
        service.tags.create("refused", metadata=untyped(_containing_itself()["a dict"]))
    with pytest.raises(TaxomeshValidationError):
        service.tags.update(tag, metadata=untyped(_containing_itself()["through a child"]))

    assert _stored(service) == before


def test_a_value_held_twice_is_not_a_value_that_contains_itself(service: TaxomeshService) -> None:
    """Two keys may hold one list: only a value inside itself is refused."""
    shared = [1, 2]
    item = service.items.create("I", metadata={"a": shared, "b": {"c": shared}})

    assert _read_afresh(service).items[item].metadata == {"a": [1, 2], "b": {"c": [1, 2]}}


def test_a_stored_value_that_is_not_json_still_loads(tmp_path: Path) -> None:
    """The check guards what comes in, not what is stored: a hand-edited YAML date still loads."""
    path = tmp_path / "taxomesh.yaml"
    TaxomeshService(YamlRepository(path)).categories.create("Dated", metadata={"when": "2024-01-01"})
    text = path.read_text()
    assert "'2024-01-01'" in text
    path.write_text(text.replace("'2024-01-01'", "2024-01-01"))

    (dated,) = TaxomeshService(YamlRepository(path)).categories.list()

    assert dated.metadata == {"when": date(2024, 1, 1)}
