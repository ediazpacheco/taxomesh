"""Every failure is a stdlib exception as well as a taxomesh one, on every backend.

A miss from a container form is a ``KeyError``, and a refused value is a ``ValueError``, so a
caller who knows only the stdlib catches both. No public member lets pydantic's own error escape:
a value the model refuses reaches the caller as ``TaxomeshValidationError``, chained to pydantic's
error with ``from``, and a validation error a model raises itself, as a relation's checks do,
reaches the caller as that error.

An argument of the wrong type is a different failure, and it is Python's: ``TypeError``, as
``int(None)`` raises, where ``int("sarasa")`` raises ``ValueError``. It is not a ``TaxomeshError``,
and it is raised before anything is read or written.
"""

import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from taxomesh.application.collections.base import EntityCollectionBase
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.constants import (
    MAX_CATEGORY_NAME_LENGTH,
    MAX_ITEM_NAME_LENGTH,
    MAX_TAG_NAME_LENGTH,
    RELATION_TYPE_MAX_LENGTH,
)
from taxomesh.exceptions import TaxomeshError, TaxomeshRelationError, TaxomeshValidationError

type Select = Callable[[TaxomeshService], EntityCollectionBase[object, UUID]]

COLLECTIONS: list[Select] = [
    lambda svc: svc.categories,
    lambda svc: svc.items,
    lambda svc: svc.tags,
]
COLLECTION_IDS = ["categories", "items", "tags"]


@pytest.mark.parametrize("select", COLLECTIONS, ids=COLLECTION_IDS)
class TestAMissIsAKeyError:
    """Each container form's miss is caught by ``except KeyError`` and prints without quotes."""

    def test_subscript(self, service: TaxomeshService, select: Select) -> None:
        collection = select(service)
        key = uuid4()
        with pytest.raises(KeyError) as caught:
            collection[key]
        assert str(caught.value).endswith(str(key))
        assert not str(caught.value).startswith("'")

    def test_del(self, service: TaxomeshService, select: Select) -> None:
        collection = select(service)
        with pytest.raises(KeyError):
            del collection[uuid4()]

    def test_delete(self, service: TaxomeshService, select: Select) -> None:
        collection = select(service)
        with pytest.raises(KeyError):
            collection.delete(uuid4())


class TestAGraphMissIsAKeyError:
    """The graph answers a miss as the collections do."""

    def test_subscript(self, service: TaxomeshService) -> None:
        with pytest.raises(KeyError):
            service.graph()[uuid4()]

    def test_rooted_at_an_unknown_category(self, service: TaxomeshService) -> None:
        with pytest.raises(KeyError):
            service.graph(root=uuid4())


def _category(svc: TaxomeshService) -> UUID:
    return svc.categories.create("A").category_id


def _item(svc: TaxomeshService, name: str = "A") -> UUID:
    return svc.items.create(name).item_id


def _tag(svc: TaxomeshService) -> UUID:
    return svc.tags.create("A").tag_id


# Any: these calls pass what the annotations refuse, as an untyped caller can.
def untyped(value: object) -> Any:
    """Return ``value`` typed as anything, so a call can pass what its annotation refuses."""
    return value


@dataclass(frozen=True, slots=True)
class RefusalCase:
    """A call every backend refuses, and what the refusal carries.

    ``field`` is the model field pydantic refused, which the message opens with; ``None`` when the
    library refuses the argument itself, and there is no pydantic error to chain.
    """

    name: str
    refuse: Callable[[TaxomeshService], object]
    field: str | None


REFUSALS: list[RefusalCase] = [
    RefusalCase(
        "category name too long on create",
        lambda svc: svc.categories.create("x" * (MAX_CATEGORY_NAME_LENGTH + 1)),
        "name",
    ),
    RefusalCase(
        "category name too long on update",
        lambda svc: svc.categories.update(_category(svc), name="x" * (MAX_CATEGORY_NAME_LENGTH + 1)),
        "name",
    ),
    RefusalCase(
        "item name too long on create",
        lambda svc: svc.items.create("x" * (MAX_ITEM_NAME_LENGTH + 1)),
        "name",
    ),
    RefusalCase(
        "item name too long on update",
        lambda svc: svc.items.update(_item(svc), name="x" * (MAX_ITEM_NAME_LENGTH + 1)),
        "name",
    ),
    RefusalCase(
        "tag name too long on create",
        lambda svc: svc.tags.create("x" * (MAX_TAG_NAME_LENGTH + 1)),
        "name",
    ),
    RefusalCase(
        "tag name too long on update",
        lambda svc: svc.tags.update(_tag(svc), name="x" * (MAX_TAG_NAME_LENGTH + 1)),
        "name",
    ),
    RefusalCase(
        "relation type too long",
        lambda svc: svc.items.relate(_item(svc, "A"), _item(svc, "B"), "t" * (RELATION_TYPE_MAX_LENGTH + 1)),
        "relation_type",
    ),
    RefusalCase("category search limit 0", lambda svc: svc.categories.search("x", limit=0), None),
    RefusalCase("item search limit 0", lambda svc: svc.items.search("x", limit=0), None),
    RefusalCase(
        "category reorder with a non-child",
        lambda svc: svc.categories.reorder(_category(svc), [uuid4()]),
        None,
    ),
    RefusalCase(
        "item reorder with an item placed elsewhere",
        lambda svc: svc.items.reorder(_category(svc), [uuid4()]),
        None,
    ),
    RefusalCase(
        "add_parent with a sort index that is no number",
        lambda svc: svc.categories.add_parent(_category(svc), _category(svc), sort_index=untyped("sarasa")),
        "sort_index",
    ),
    RefusalCase(
        "place_in with a sort index that is no number",
        lambda svc: svc.items.place_in(_item(svc), _category(svc), sort_index=untyped("sarasa")),
        "sort_index",
    ),
    RefusalCase(
        "list_relations with an unknown direction",
        lambda svc: svc.items.list_relations(_item(svc), direction=untyped("sideways")),
        None,
    ),
    RefusalCase(
        "list_related with an unknown direction",
        lambda svc: svc.items.list_related(_item(svc), direction=untyped("sideways")),
        None,
    ),
    RefusalCase(
        "get_many_related with an unknown direction, asked of no item",
        lambda svc: svc.items.get_many_related([], direction=untyped("sideways")),
        None,
    ),
    RefusalCase(
        "category update with a negative expected version",
        lambda svc: svc.categories.update(_category(svc), name="B", expected_version=-1),
        None,
    ),
    RefusalCase(
        "item update with a negative expected version",
        lambda svc: svc.items.update(_item(svc), name="B", expected_version=-1),
        None,
    ),
]


@pytest.mark.parametrize("case", REFUSALS, ids=[case.name for case in REFUSALS])
def test_a_refusal_is_a_validation_error(service: TaxomeshService, case: RefusalCase) -> None:
    """Caught as ``TaxomeshValidationError`` and as ``ValueError``, and never as pydantic's error."""
    with pytest.raises(TaxomeshValidationError) as caught:
        case.refuse(service)
    refusal = caught.value
    assert isinstance(refusal, ValueError)
    assert not isinstance(refusal, ValidationError)
    if case.field is None:
        assert refusal.__cause__ is None
    else:
        assert isinstance(refusal.__cause__, ValidationError)
        assert str(refusal).startswith(f"{case.field}: ")


def test_a_none_description_says_what_no_description_is(service: TaxomeshService) -> None:
    """``""`` is no description, so the message names the value to pass."""
    with pytest.raises(TypeError, match=re.escape('description cannot be None: pass "" for no description')):
        service.categories.create("A", description=untyped(None))


class TestARelationKeepsItsOwnError:
    """The relation's own checks live in the model, and reach the caller as the error they raise."""

    def test_a_self_relation(self, service: TaxomeshService) -> None:
        item_id = _item(service)
        with pytest.raises(TaxomeshRelationError, match="An item cannot be related to itself") as caught:
            service.items.relate(item_id, item_id, "loop")
        assert isinstance(caught.value.__cause__, ValidationError)

    def test_a_blank_relation_type(self, service: TaxomeshService) -> None:
        with pytest.raises(TaxomeshRelationError, match="empty") as caught:
            service.items.relate(_item(service, "A"), _item(service, "B"), "   ")
        assert isinstance(caught.value.__cause__, ValidationError)


def _pair(svc: TaxomeshService) -> tuple[UUID, UUID]:
    return _item(svc, "A"), _item(svc, "B")


def _reorder_placed(svc: TaxomeshService, order: Callable[[UUID], object]) -> None:
    """Reorder the one item placed in a category, passing the order ``order`` builds from it."""
    category, item = _category(svc), _item(svc)
    svc.items.place_in(item, category)
    svc.items.reorder(category, untyped(order(item)))


@dataclass(frozen=True, slots=True)
class WrongTypeCase:
    """A call given an argument of the wrong type, which Python's ``TypeError`` refuses.

    ``names`` is the parameter the message opens with, where the library checks the argument
    itself rather than letting Python's own operation fail on it; ``None`` asserts no wording.
    """

    name: str
    refuse: Callable[[TaxomeshService], object]
    names: str | None = None


WRONG_TYPES: list[WrongTypeCase] = [
    # A model field, on create and on update.
    WrongTypeCase("category create, a name that is no str", lambda svc: svc.categories.create(untyped(5))),
    WrongTypeCase(
        "category create, a None description", lambda svc: svc.categories.create("A", description=untyped(None))
    ),
    WrongTypeCase("category create, a slug that is no str", lambda svc: svc.categories.create("A", slug=untyped(5))),
    WrongTypeCase(
        "category create, metadata that is no dict", lambda svc: svc.categories.create("A", metadata=untyped("x"))
    ),
    WrongTypeCase("item create, a None name", lambda svc: svc.items.create(untyped(None))),
    WrongTypeCase("item create, a None slug", lambda svc: svc.items.create("A", slug=untyped(None))),
    WrongTypeCase("tag create, a name that is no str", lambda svc: svc.tags.create(untyped(5))),
    WrongTypeCase("tag create, metadata that is a list", lambda svc: svc.tags.create("A", metadata=untyped([1]))),
    WrongTypeCase(
        "category update, a None enabled", lambda svc: svc.categories.update(_category(svc), enabled=untyped(None))
    ),
    WrongTypeCase(
        "category update, an enabled that is no bool",
        lambda svc: svc.categories.update(_category(svc), enabled=untyped(object())),
    ),
    WrongTypeCase("item update, a name that is no str", lambda svc: svc.items.update(_item(svc), name=untyped(5))),
    WrongTypeCase("tag update, a None name", lambda svc: svc.tags.update(_tag(svc), name=untyped(None))),
    WrongTypeCase(
        "category update, an expected version that is a str",
        lambda svc: svc.categories.update(_category(svc), name="B", expected_version=untyped("0")),
    ),
    WrongTypeCase(
        "item update, an expected version that is a float",
        lambda svc: svc.items.update(_item(svc), name="B", expected_version=untyped(0.0)),
    ),
    # An external id is a str, an integer, a UUID or None, and nothing else.
    WrongTypeCase(
        "category create, an external id that is a list",
        lambda svc: svc.categories.create("A", external_id=untyped([1])),
    ),
    WrongTypeCase(
        "item create, an external id that is a bool", lambda svc: svc.items.create("A", external_id=untyped(True))
    ),
    WrongTypeCase(
        "category update, an external id that is bytes",
        lambda svc: svc.categories.update(_category(svc), external_id=untyped(b"x")),
    ),
    WrongTypeCase("category get_by_external_id, a list", lambda svc: svc.categories.get_by_external_id(untyped([1]))),
    WrongTypeCase("item get_by_external_id, a bool", lambda svc: svc.items.get_by_external_id(untyped(True))),
    WrongTypeCase(
        "item get_by_external_id, a bool after its integer is cached",
        lambda svc: (
            svc.items.create("A", external_id=1),
            svc.items.get_by_external_id(1),
            svc.items.get_by_external_id(untyped(True)),
        ),
    ),
    WrongTypeCase(
        "item get_many_by_external_id, a list among the keys",
        lambda svc: svc.items.get_many_by_external_id(untyped([[1]])),
    ),
    # A slug and a search query are text.
    WrongTypeCase("category get_by_slug, an int", lambda svc: svc.categories.get_by_slug(untyped(5))),
    WrongTypeCase("item get_by_slug, None", lambda svc: svc.items.get_by_slug(untyped(None))),
    WrongTypeCase("category search, a None query", lambda svc: svc.categories.search(untyped(None))),
    WrongTypeCase("item search, a query that is no str", lambda svc: svc.items.search(untyped(5))),
    WrongTypeCase(
        "category search, a limit that is a str", lambda svc: svc.categories.search("A", limit=untyped("5"))
    ),
    # A limit is an integer, refused otherwise even when nothing matches: NaN would cap nothing.
    WrongTypeCase("category search, a float limit", lambda svc: svc.categories.search("A", limit=untyped(1.5))),
    WrongTypeCase("category search, a NaN limit", lambda svc: svc.categories.search("A", limit=untyped(math.nan))),
    WrongTypeCase(
        "category search, a blank query and a float limit",
        lambda svc: svc.categories.search("", limit=untyped(1.5)),
    ),
    WrongTypeCase("item search, a float limit", lambda svc: svc.items.search("A", limit=untyped(1.5))),
    WrongTypeCase("item search, a NaN limit", lambda svc: svc.items.search("A", limit=untyped(math.nan))),
    # An order is a sequence: a set or a mapping holds no order of the caller's, and an iterator is
    # no sequence either.
    WrongTypeCase("category reorder, a set", lambda svc: svc.categories.reorder(None, untyped({_category(svc)}))),
    WrongTypeCase("category reorder, a dict", lambda svc: svc.categories.reorder(None, untyped({_category(svc): 0}))),
    WrongTypeCase(
        "category reorder, an iterator", lambda svc: svc.categories.reorder(None, untyped(iter([_category(svc)])))
    ),
    WrongTypeCase("item reorder, a set", lambda svc: _reorder_placed(svc, lambda item: {item})),
    WrongTypeCase("item reorder, a dict", lambda svc: _reorder_placed(svc, lambda item: {item: 0})),
    # A sort index is an integer, refused before any read: before a cycle, before an unknown row.
    WrongTypeCase(
        "add_parent, a None sort index",
        lambda svc: svc.categories.add_parent(_category(svc), _category(svc), sort_index=untyped(None)),
    ),
    WrongTypeCase(
        "add_parent to itself, a None sort index",
        lambda svc: (
            category := _category(svc),
            svc.categories.add_parent(category, category, sort_index=untyped(None)),
        ),
    ),
    WrongTypeCase(
        "place_in, a None sort index",
        lambda svc: svc.items.place_in(_item(svc), _category(svc), sort_index=untyped(None)),
    ),
    WrongTypeCase(
        "place_in an unknown category, a None sort index",
        lambda svc: svc.items.place_in(_item(svc), uuid4(), sort_index=untyped(None)),
    ),
    WrongTypeCase(
        "relate, a None sort index", lambda svc: svc.items.relate(*_pair(svc), "covers", sort_index=untyped(None))
    ),
    # A relation type is text, and so is each of the relation types a read filters by.
    WrongTypeCase("relate, a relation type that is no str", lambda svc: svc.items.relate(*_pair(svc), untyped(5))),
    WrongTypeCase("unrelate, a None relation type", lambda svc: svc.items.unrelate(*_pair(svc), untyped(None))),
    WrongTypeCase(
        "list_relations, a relation type that is no str",
        lambda svc: svc.items.list_relations(_item(svc), relation_types=untyped([5])),
    ),
    WrongTypeCase(
        "list_related, relation types that are no collection",
        lambda svc: svc.items.list_related(_item(svc), relation_types=untyped(0)),
    ),
    WrongTypeCase(
        "get_many_related, a relation type that is no str, asked of no item",
        lambda svc: svc.items.get_many_related([], relation_types=untyped([5])),
    ),
    # A direction is a Direction or its text.
    WrongTypeCase(
        "list_relations, a direction that is no str",
        lambda svc: svc.items.list_relations(_item(svc), direction=untyped(5)),
    ),
    WrongTypeCase(
        "list_related, a None direction", lambda svc: svc.items.list_related(_item(svc), direction=untyped(None))
    ),
    WrongTypeCase(
        "get_many_related, a direction that is no str, asked of no item",
        lambda svc: svc.items.get_many_related([], direction=untyped(5)),
    ),
    # The enabled filter is True, False or None, checked before any read and any shortcut.
    WrongTypeCase("category list, enabled a str", lambda svc: svc.categories.list(enabled=untyped("x"))),
    WrongTypeCase("category roots, enabled a str", lambda svc: svc.categories.roots(enabled=untyped("x"))),
    WrongTypeCase(
        "category roots, enabled 1 after enabled True is cached",
        lambda svc: (svc.categories.roots(enabled=True), svc.categories.roots(enabled=untyped(1))),
    ),
    WrongTypeCase("category search, enabled a str", lambda svc: svc.categories.search("A", enabled=untyped("x"))),
    WrongTypeCase(
        "category get_many of no key, enabled a str", lambda svc: svc.categories.get_many([], enabled=untyped("x"))
    ),
    WrongTypeCase(
        "category get_many_by_external_id of no key, enabled a str",
        lambda svc: svc.categories.get_many_by_external_id([], enabled=untyped("x")),
    ),
    WrongTypeCase("item list, enabled a str", lambda svc: svc.items.list(enabled=untyped("x"))),
    WrongTypeCase("item search, enabled a str", lambda svc: svc.items.search("A", enabled=untyped("x"))),
    WrongTypeCase("item get_many of no key, enabled a str", lambda svc: svc.items.get_many([], enabled=untyped("x"))),
    WrongTypeCase(
        "item get_many_by_external_id of no key, enabled a str",
        lambda svc: svc.items.get_many_by_external_id([], enabled=untyped("x")),
    ),
    WrongTypeCase(
        "item list_related, enabled a str", lambda svc: svc.items.list_related(_item(svc), enabled=untyped("x"))
    ),
    WrongTypeCase(
        "item get_many_related of no item, enabled a str",
        lambda svc: svc.items.get_many_related([], enabled=untyped("x")),
    ),
    WrongTypeCase("graph, enabled a str", lambda svc: svc.graph(enabled=untyped("x"))),
    # A batch lookup takes one value or a collection of them, and anything else is named as refused.
    WrongTypeCase("category get_many, None", lambda svc: svc.categories.get_many(untyped(None)), "categories"),
    WrongTypeCase("category get_many, an int", lambda svc: svc.categories.get_many(untyped(5)), "categories"),
    WrongTypeCase("item get_many, None", lambda svc: svc.items.get_many(untyped(None)), "items"),
    WrongTypeCase("item get_many, an int", lambda svc: svc.items.get_many(untyped(5)), "items"),
    WrongTypeCase("tag get_many, None", lambda svc: svc.tags.get_many(untyped(None)), "tags"),
    WrongTypeCase("tag get_many, an int", lambda svc: svc.tags.get_many(untyped(5)), "tags"),
    WrongTypeCase(
        "category get_many_by_external_id, a float",
        lambda svc: svc.categories.get_many_by_external_id(untyped(5.5)),
        "external_ids",
    ),
    WrongTypeCase(
        "item get_many_by_external_id, a float",
        lambda svc: svc.items.get_many_by_external_id(untyped(5.5)),
        "external_ids",
    ),
    WrongTypeCase("item get_many_related, None", lambda svc: svc.items.get_many_related(untyped(None)), "items"),
    WrongTypeCase(
        "list_related, relation types that are no collection, named",
        lambda svc: svc.items.list_related(_item(svc), relation_types=untyped(0)),
        "relation_types",
    ),
    WrongTypeCase(
        "list_relations, a relation type that is no str, named",
        lambda svc: svc.items.list_relations(_item(svc), relation_types=untyped(["x", 5])),
        "relation_types",
    ),
]


@pytest.mark.parametrize("case", WRONG_TYPES, ids=[case.name for case in WRONG_TYPES])
def test_a_wrong_type_is_a_type_error(service: TaxomeshService, case: WrongTypeCase) -> None:
    """Caught as ``TypeError``, and as neither a taxomesh error nor pydantic's."""
    with pytest.raises(TypeError) as caught:
        case.refuse(service)
    assert not isinstance(caught.value, TaxomeshError)
    assert not isinstance(caught.value, ValueError)
    if case.names is not None:
        assert str(caught.value).startswith(f"{case.names} ")
