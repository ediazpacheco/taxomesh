"""The container law, asserted on every collection and every backend.

> **Subscript raises. Anything named ``get*`` never does.**

``tests/surface/test_api_law.py`` states the same law once, on categories, as a statement of
intent. This file is the behavioural counterpart: the law holds for **all three** collections
on **all four** backends, or it is not a law but a coincidence of one code path.

Two choices here are deliberate and would be wrong to "tidy":

* **Length is asserted relatively**: ``before + 1``, never ``== 1``. The implicit root is a
  stored ``Category`` (``_ensure_root``) that the container does not show, and a relative
  assertion does not depend on how the root is counted. ``tests/surface/test_api_law.py`` states
  the absolute count.
* **The collection is held as** ``EntityCollectionBase[object, UUID]``. The row type ``T``
  appears only in return position and the key type ``K`` only in parameters, so mypy infers the
  one covariant and the other contravariant, and every concrete collection is a subtype — which
  is what lets one parametrized test cover three entity types with no ``Any``, no cast and no
  ``type: ignore``.
"""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from taxomesh.application.collections.base import EntityCollectionBase
from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import (
    TaxomeshCategoryNotFoundError,
    TaxomeshItemNotFoundError,
    TaxomeshNotFoundError,
    TaxomeshTagNotFoundError,
)
from tests.service.conftest import CountedService


@dataclass(frozen=True, slots=True)
class LawCase:
    """One entity's answers to the questions the law asks of every collection.

    ``select`` reaches the collection by **direct attribute access** rather than ``getattr``,
    which is what keeps the whole file precisely typed.
    """

    name: str
    select: Callable[[TaxomeshService], EntityCollectionBase[object, UUID]]
    create: Callable[[TaxomeshService], UUID]
    not_found: type[TaxomeshNotFoundError]


CASES: list[LawCase] = [
    LawCase(
        name="categories",
        select=lambda svc: svc.categories,
        create=lambda svc: svc.categories.create("Alpha").category_id,
        not_found=TaxomeshCategoryNotFoundError,
    ),
    LawCase(
        name="items",
        select=lambda svc: svc.items,
        create=lambda svc: svc.items.create(name="Alpha").item_id,
        not_found=TaxomeshItemNotFoundError,
    ),
    LawCase(
        name="tags",
        select=lambda svc: svc.tags,
        create=lambda svc: svc.tags.create("Alpha").tag_id,
        not_found=TaxomeshTagNotFoundError,
    ),
]

CASE_IDS: list[str] = [case.name for case in CASES]


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
class TestContainerLaw:
    """Every collection answers the same six questions the same way."""

    def test_subscript_raises_the_entity_not_found_error(self, service: TaxomeshService, case: LawCase) -> None:
        """``coll[missing]`` raises that entity's own ``NotFoundError`` subclass.

        The subclass matters: a caller catching ``TaxomeshItemNotFoundError`` must not be
        handed a category's error because the base raised something generic.
        """
        collection = case.select(service)

        with pytest.raises(case.not_found):
            collection[uuid4()]

    def test_get_returns_none_on_a_missing_key(self, service: TaxomeshService, case: LawCase) -> None:
        """``coll.get(missing)`` answers ``None`` and raises nothing."""
        collection = case.select(service)

        assert collection.get(uuid4()) is None

    def test_get_returns_the_supplied_default(self, service: TaxomeshService, case: LawCase) -> None:
        """``coll.get(missing, default)`` returns the default object itself, not a copy."""
        collection = case.select(service)
        fallback = object()

        assert collection.get(uuid4(), fallback) is fallback

    def test_get_returns_the_row_when_present(self, service: TaxomeshService, case: LawCase) -> None:
        """``coll.get(present)`` and ``coll[present]`` agree — ``get`` is not a separate lookup."""
        collection = case.select(service)
        key = case.create(service)

        assert collection.get(key) == collection[key]

    def test_membership_agrees_with_subscript(self, service: TaxomeshService, case: LawCase) -> None:
        """``key in coll`` is ``True`` exactly when ``coll[key]`` does not raise.

        Structural rather than coincidental: both are built on the same subscript in the base,
        so the two cannot drift apart the way two independent lookups would.
        """
        collection = case.select(service)
        key = case.create(service)

        assert key in collection
        assert uuid4() not in collection

    def test_length_counts_the_rows_membership_sees(self, service: TaxomeshService, case: LawCase) -> None:
        """Creating one row raises ``len`` by exactly one.

        Relative, not absolute — see the module docstring on the implicit root.
        """
        collection = case.select(service)
        before = len(collection)

        case.create(service)

        assert len(collection) == before + 1

    def test_delitem_removes_the_row(self, service: TaxomeshService, case: LawCase) -> None:
        """``del coll[key]`` deletes, and the key stops being a member."""
        collection = case.select(service)
        key = case.create(service)

        del collection[key]

        assert key not in collection
        with pytest.raises(case.not_found):
            collection[key]

    def test_delitem_raises_on_a_missing_key(self, service: TaxomeshService, case: LawCase) -> None:
        """``del coll[missing]`` raises rather than passing silently."""
        collection = case.select(service)

        with pytest.raises(case.not_found):
            del collection[uuid4()]

    def test_get_many_omits_absent_keys(self, service: TaxomeshService, case: LawCase) -> None:
        """An absent key is simply not in the returned mapping.

        Not raising, and not present with a ``None`` value — either would force every caller
        to write the same guard, which is the defect ``get_many`` exists to remove.
        """
        collection = case.select(service)
        key = case.create(service)
        absent = uuid4()

        found = collection.get_many([key, absent])

        assert key in found
        assert absent not in found
        assert found[key] == collection[key]

    def test_get_many_of_nothing_is_empty(self, service: TaxomeshService, case: LawCase) -> None:
        """An empty request returns an empty mapping."""
        collection = case.select(service)

        assert collection.get_many([]) == {}

    def test_get_many_of_nothing_costs_no_read(self, counting_service: CountedService, case: LawCase) -> None:
        """An empty request is answered without a storage read.

        Counted as every read gate counts, one repository call per read. Django issues no SQL
        for an empty ``__in`` either way; the call is what a custom backend would pay for.
        """
        collection = case.select(counting_service.service)
        counting_service.cold()

        assert collection.get_many([]) == {}
        assert counting_service.reads.total == 0
