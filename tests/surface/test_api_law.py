"""The container law and the naming rules, asserted over the whole public surface.

> **Subscript raises. Anything named ``get*`` never does.**

This file states that law for each collection, and the naming rules for every public member: the
``_for_`` and ``_by_`` rules, no ``list*`` member returning a mapping, no name carrying two
contracts across the port and the service, no collection being a ``Mapping``, no public
parameter ending in ``_id``, one name for a container's key, a batch annotated as a ``Collection``,
and one order for a row's fields.

Why a separate file from ``test_public_surface.py``: the ledger records *what the surface is*,
signature by signature. This asserts the rules every signature must follow, so a member the
ledger records faithfully can still fail here.
"""

import inspect
import re
from collections.abc import Callable, Mapping
from types import get_original_bases
from typing import Final, get_args
from uuid import uuid4

import pytest

from taxomesh.application.collections.categories import CategoryCollection
from taxomesh.application.collections.items import ItemCollection
from taxomesh.application.collections.tags import TagCollection
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.graph import TaxomeshGraph
from taxomesh.exceptions import TaxomeshCategoryNotFoundError
from taxomesh.ports.repository import TaxomeshRepositoryBase
from tests.service.conftest import InMemoryRepository
from tests.surface._surface import SUBJECTS, public_names, render_member

COLLECTION_NAMES = ["categories", "items", "tags"]

# The unique keys a ``_by_`` name may address rows by. ``_by_id`` is the port's batch read by
# identifier (``map_items_by_id``).
UNIQUE_KEY_SUFFIXES: Final[tuple[str, ...]] = ("_by_id", "_by_slug", "_by_external_id")

# The one order the fields of a row come in, wherever a member or a request schema takes several.
FIELD_ORDER: Final[tuple[str, ...]] = (
    "name",
    "description",
    "slug",
    "external_id",
    "enabled",
    "metadata",
    "expected_version",
)

# The same three collections as callables. ``test_each_collection_is_the_same_object_every_time``
# has to name an attribute rather than a string: a string can only be resolved with ``getattr``,
# which costs the test its typing.
COLLECTION_ACCESSORS: list[tuple[str, Callable[[TaxomeshService], object]]] = [
    ("categories", lambda service: service.categories),
    ("items", lambda service: service.items),
    ("tags", lambda service: service.tags),
]


@pytest.fixture
def service() -> TaxomeshService:
    """A service on an in-memory backend.

    Deliberately not the parametrized four-backend fixture: the law is a property of the API
    shape, not of storage, and asserting it once is enough.
    """
    return TaxomeshService(repository=InMemoryRepository())


def _names_containing_for(subject: type) -> list[str]:
    """Public member names of *subject* that still spell ``_for_``."""
    return [name for name in public_names(subject) if "_for_" in name]


def _names_misusing_by(subject: type) -> list[str]:
    """Public member names of *subject* whose ``_by_`` names anything but a unique key."""
    return [name for name in public_names(subject) if "_by_" in name and not name.endswith(UNIQUE_KEY_SUFFIXES)]


def _returns_a_mapping(rendered: str) -> bool:
    """Whether a rendered member's return annotation is a mapping, ``dict[…]`` or ``Mapping[…]``.

    Reads only the text after the last ``" -> "``, so a parameter annotated with a mapping does not
    count. ``Mapping`` renders bare when the annotation was written as a string and as
    ``collections.abc.Mapping`` when it was evaluated, so the module prefix is dropped first.
    """
    _, arrow, returns = rendered.rpartition(" -> ")
    return bool(arrow) and returns.removeprefix("collections.abc.").startswith(("dict[", "Mapping["))


def _shared_names() -> list[str]:
    """Public member names carried by both the port and the service.

    ``public_names`` is ``dir()``-based, so inherited members count — which is correct here:
    a name a caller can reach on both layers is shared, however it got there.
    """
    return sorted(set(public_names(TaxomeshRepositoryBase)) & set(public_names(TaxomeshService)))


def _rendered(subject: type, name: str) -> str:
    """Render one member with its owning class name stripped, so the two layers compare directly."""
    return render_member(subject, name).removeprefix(f"{subject.__name__}.")


class TestNamingLaw:
    """Names alone must predict the return shape."""

    def test_no_port_name_contains_for(self) -> None:
        """``_for_`` appears nowhere on the port.

        The port's batch relation read is ``list_item_relation_links_batch``: ``_batch`` says it
        takes many items, where ``_for_`` could mean several things.
        """
        offenders = _names_containing_for(TaxomeshRepositoryBase)

        assert not offenders, f"_for_ must not appear in port names: {offenders}"

    def test_no_service_name_contains_for(self) -> None:
        """``_for_`` appears nowhere on the service.

        The related items of many items are ``svc.items.get_many_related``, whose prefix says it
        returns a mapping.
        """
        offenders = _names_containing_for(TaxomeshService)

        assert not offenders, f"_for_ must not appear in service names: {offenders}"

    def test_no_list_member_returns_a_mapping(self) -> None:
        """A ``list*`` member returns a sequence, never a mapping.

        The probe covers a ``dict[…]`` and a ``Mapping[…]`` return, the annotation every keyed
        read carries, on every name starting with ``list``, the collections' own ``list``
        included. A keyed result has a ``get_many*`` name instead.
        """
        offenders = [
            f"{subject.__name__}.{name}"
            for subject in SUBJECTS
            for name in public_names(subject)
            if name.startswith("list") and _returns_a_mapping(render_member(subject, name))
        ]

        assert not offenders, f"list* must not return a mapping: {offenders}"

    def test_by_names_only_a_unique_key(self) -> None:
        """``_by_`` names the unique key a lookup addresses rows by, and nothing else.

        The key is ``id``, ``slug`` or ``external_id``, and the lookup may return one row
        (``get_by_slug``) or a batch (``get_many_by_external_id``, the port's
        ``map_items_by_id``). What the rule forbids is ``_by_`` naming a filter over a relation,
        such as the categories holding an item, which ``categories.list(item=…)`` spells as a
        keyword filter.
        """
        offenders = [f"{subject.__name__}.{name}" for subject in SUBJECTS for name in _names_misusing_by(subject)]

        assert not offenders, f"_by_ must name a unique key: {offenders}"


class TestLookupKeysArePositionalOnly:
    """A single-row lookup takes its key by position only, as ``get`` and ``dict.get`` do."""

    def test_every_get_by_lookup_takes_its_key_by_position(self) -> None:
        """The key of every ``get_by_*`` member is positional-only, on every subject that has one.

        The lookups are found by name rather than listed, so a new one is held to the rule without
        editing this test; the set found is asserted too, so the test cannot pass by finding none.
        """
        found: dict[str, bool] = {}
        for subject in SUBJECTS:
            for name in public_names(subject):
                if name.startswith("get_by_"):
                    key = list(inspect.signature(getattr(subject, name)).parameters.values())[1]
                    found[f"{subject.__name__}.{name}"] = key.kind is inspect.Parameter.POSITIONAL_ONLY

        assert set(found) == {
            "CategoryCollection.get_by_external_id",
            "CategoryCollection.get_by_slug",
            "ItemCollection.get_by_external_id",
            "ItemCollection.get_by_slug",
        }
        assert all(found.values()), f"key not positional-only: {sorted(n for n, ok in found.items() if not ok)}"


class TestParametersNameRows:
    """A parameter naming a row is a noun, and takes the row or its identifier.

    The port and the HTTP request schemas keep their ``UUID`` identifiers; the service, the three
    collections and the graph take ``CategoryRef``, ``ItemRef`` or ``TagRef``. Annotations are
    read as rendered text, which is the alias's name whether the module defers its annotations or
    not.
    """

    OWNERS: Final[tuple[type, ...]] = (
        TaxomeshService,
        CategoryCollection,
        ItemCollection,
        TagCollection,
        TaxomeshGraph,
    )
    CONTAINER_FORMS: Final[tuple[str, ...]] = ("__getitem__", "__contains__", "__delitem__")
    KEY_FORMS: Final[tuple[str, ...]] = (*CONTAINER_FORMS, "get", "delete")

    # Each container, and the reference its key takes.
    KEYED: Final[Mapping[type, str]] = {
        CategoryCollection: "CategoryRef",
        ItemCollection: "ItemRef",
        TagCollection: "TagRef",
        TaxomeshGraph: "CategoryRef",
    }

    # The noun each row parameter takes, and the alias it is annotated with. ``before`` names a
    # sibling, so its alias is the namespace's own.
    REF_OF: Final[Mapping[str, str]] = {
        "category": "CategoryRef",
        "parent": "CategoryRef",
        "root": "CategoryRef",
        "from_parent": "CategoryRef",
        "to_parent": "CategoryRef",
        "from_category": "CategoryRef",
        "to_category": "CategoryRef",
        "categories": "CategoryRef",
        "item": "ItemRef",
        "source": "ItemRef",
        "target": "ItemRef",
        "items": "ItemRef",
        "tag": "TagRef",
        "tags": "TagRef",
    }
    BEFORE: Final[Mapping[str, str]] = {"CategoryCollection": "CategoryRef", "ItemCollection": "ItemRef"}
    PLURALS: Final[frozenset[str]] = frozenset({"categories", "items", "tags"})

    @classmethod
    def _parameters(cls) -> list[tuple[str, inspect.Parameter]]:
        """Every parameter of every callable member, and the container forms, as ``Owner.member``."""
        found: list[tuple[str, inspect.Parameter]] = []
        for subject in cls.OWNERS:
            names = [*public_names(subject), *(form for form in cls.CONTAINER_FORMS if hasattr(subject, form))]
            for name in names:
                member = inspect.getattr_static(subject, name)
                if isinstance(member, property) or not callable(member):
                    continue
                for parameter in list(inspect.signature(getattr(subject, name)).parameters.values())[1:]:
                    found.append((f"{subject.__name__}.{name}", parameter))
        return found

    def test_no_parameter_is_an_identifier(self) -> None:
        """No parameter ends in ``_id`` or ``_ids``, except the consumer's own ``external_id``."""
        offenders = [
            f"{owner}({parameter.name})"
            for owner, parameter in self._parameters()
            if parameter.name.endswith(("_id", "_ids")) and not parameter.name.startswith("external_")
        ]

        assert not offenders, f"a parameter naming a row is a noun: {offenders}"

    def test_each_noun_is_annotated_with_its_reference(self) -> None:
        """Each noun is its ``*Ref``, optionally ``| None``, and each plural takes several of it.

        A lookup's plural takes one row as well as a collection of them; ``reorder``'s takes a
        sequence, since one row is no order.
        """
        checked: set[str] = set()
        offenders: list[str] = []
        for owner, parameter in self._parameters():
            subject = owner.partition(".")[0]
            ref = self.BEFORE.get(subject) if parameter.name == "before" else self.REF_OF.get(parameter.name)
            if ref is None:
                continue
            checked.add(subject)
            annotation = str(parameter.annotation).replace("collections.abc.", "")
            wanted = (
                rf"({ref} \| Collection|Sequence)\[{ref}\]" if parameter.name in self.PLURALS else rf"{ref}( \| None)?"
            )
            if not re.fullmatch(wanted, annotation):
                offenders.append(f"{owner}({parameter.name}: {annotation})")

        assert not offenders, f"a parameter naming a row takes the row or its identifier: {offenders}"
        # The graph names a row only by its key, which the container-form test below holds.
        assert checked == {subject.__name__ for subject in self.OWNERS} - {TaxomeshGraph.__name__}

    @pytest.mark.parametrize(
        ("collection", "names"),
        [
            (CategoryCollection, ["Category", "CategoryRef"]),
            (ItemCollection, ["Item", "ItemRef"]),
            (TagCollection, ["Tag", "TagRef"]),
        ],
        ids=["categories", "items", "tags"],
    )
    def test_each_container_is_keyed_by_its_reference(self, collection: type, names: list[str]) -> None:
        """The shared base is parametrised by the row and its reference, so ``get`` and ``in`` take it too."""
        (base,) = get_original_bases(collection)

        assert [argument.__name__ for argument in get_args(base)] == names

    def test_every_container_form_names_its_key(self) -> None:
        """Subscript, ``get``, ``in``, ``del`` and ``delete`` call their argument ``key``, as the law's table does.

        It is annotated with the owner's reference, or with the base's ``K``, which each collection
        binds to its reference.
        """
        offenders: list[str] = []
        for subject, ref in self.KEYED.items():
            for form in self.KEY_FORMS:
                if not hasattr(subject, form):
                    continue
                key = list(inspect.signature(getattr(subject, form)).parameters.values())[1]
                if key.name != "key" or str(key.annotation) not in (ref, "K"):
                    offenders.append(f"{subject.__name__}.{form}({key.name}: {key.annotation})")

        assert not offenders, f"a container form names its key `key`: {offenders}"

    def test_a_batch_parameter_is_a_collection(self) -> None:
        """A batch takes one value or a ``Collection`` of them, never an ``Iterable``.

        ``reorder``'s plural takes a ``Sequence``, which the noun test above holds.
        """
        offenders = [
            f"{owner}({parameter.name}: {parameter.annotation})"
            for owner, parameter in self._parameters()
            if "Iterable[" in str(parameter.annotation)
        ]

        assert not offenders, f"a batch parameter is annotated as a Collection: {offenders}"

    def test_fields_come_in_one_order(self) -> None:
        """Every ``create`` and ``update`` lists the fields it takes in one order.

        ``help()``, the ledger and the request schemas then read alike across the three
        collections.
        """
        offenders: list[str] = []
        for subject in (CategoryCollection, ItemCollection, TagCollection):
            for member in ("create", "update"):
                fields = [
                    name for name in inspect.signature(getattr(subject, member)).parameters if name in FIELD_ORDER
                ]
                if fields != sorted(fields, key=FIELD_ORDER.index):
                    offenders.append(f"{subject.__name__}.{member}{tuple(fields)}")

        assert not offenders, f"fields come in the order {FIELD_ORDER}: {offenders}"


class TestPortServiceSeparation:
    """A name shared by both layers means the same thing on both.

    The port reports absence; the service turns absence into an error. That division holds as
    long as no name sits on both layers meaning two different things: a ``get_category`` that
    returned ``None`` on the port and raised on the service would leave a reader unable to tell
    which contract they held without checking the import.
    """

    def test_no_shared_lookup_inversion(self) -> None:
        """No shared name reports absence with ``None`` on the port while the service raises.

        **The offender list is empty for a structural reason, not a measured one: read this
        before trusting it as evidence.** Every nullable port member is ``find_*``
        (``find_category``, ``find_item``, ``find_tag``, ...) and the service has no ``find_*``
        member at all, so the nullable sets of the two layers are disjoint and this probe cannot
        fire while the naming holds.

        It fires the moment a port ``get_category -> Category | None`` sits beside a raising
        service member of that name.

        ``endswith("| None")`` is the right probe rather than a substring search: ``_surface``
        renders a ``-> None`` annotation as the bare four-character ``None``, so a method
        returning nothing is not mistaken for one returning an optional.
        """
        offenders = [
            name
            for name in _shared_names()
            if _rendered(TaxomeshRepositoryBase, name).endswith("| None")
            and not _rendered(TaxomeshService, name).endswith("| None")
        ]

        assert not offenders, f"port reports absence where the service raises, under one name: {offenders}"

    def test_shared_names_have_identical_contracts(self) -> None:
        """A name on both layers renders identically on both.

        Like ``test_no_shared_lookup_inversion`` above, it passes over an empty candidate set,
        since the service keeps its members on the collections. It fires the moment a name sits
        on both layers carrying two contracts, as a ``delete_category`` answering ``bool`` on the
        port and ``None`` on the service would.
        """
        offenders = [
            f"{name}: port {_rendered(TaxomeshRepositoryBase, name)} != service {_rendered(TaxomeshService, name)}"
            for name in _shared_names()
            if _rendered(TaxomeshRepositoryBase, name) != _rendered(TaxomeshService, name)
        ]

        assert not offenders, f"a shared name must mean one thing: {offenders}"


class TestCollectionsExist:
    """Operations are reached through the noun they act on."""

    def test_service_exposes_the_three_collections(self, service: TaxomeshService) -> None:
        """``svc.categories``, ``svc.items`` and ``svc.tags`` exist."""
        missing = [name for name in COLLECTION_NAMES if not hasattr(service, name)]

        assert not missing, f"missing collections: {missing}"

    @pytest.mark.parametrize(
        "accessor",
        [accessor for _, accessor in COLLECTION_ACCESSORS],
        ids=[name for name, _ in COLLECTION_ACCESSORS],
    )
    def test_each_collection_is_the_same_object_every_time(
        self, service: TaxomeshService, accessor: Callable[[TaxomeshService], object]
    ) -> None:
        """Accessing a collection twice yields the identical object.

        The service builds each collection once and hands it the service's cache, root and
        corpus. A property minting a fresh collection per access would build one on every read,
        and ``svc.categories is svc.categories`` would be false.
        """
        assert accessor(service) is accessor(service), "a collection must be built once, not per access"

    @pytest.mark.parametrize(
        "accessor",
        [accessor for _, accessor in COLLECTION_ACCESSORS],
        ids=[name for name, _ in COLLECTION_ACCESSORS],
    )
    def test_no_collection_is_a_mapping(
        self, service: TaxomeshService, accessor: Callable[[TaxomeshService], object]
    ) -> None:
        """No collection is a ``collections.abc.Mapping``.

        A ``Mapping`` requires an ``__iter__`` that yields keys, so iterating a collection would
        hand back identifiers rather than entities, and it builds ``keys()``, ``items()``,
        ``values()`` and ``==`` on that ``__iter__``: iterating a view, or comparing with another
        mapping, reads every row behind an innocent-looking call.

        ``isinstance`` is the right probe: unlike ``Collection``, ``Mapping`` has no structural
        check — a class defining every mapping method but inheriting nothing is not one — so it
        answers ``True`` only for a subclass or a class registered with it, the two ways the ban
        could be broken.
        """
        assert not isinstance(accessor(service), Mapping), "a collection must not be a Mapping"

    @pytest.mark.parametrize(
        "accessor",
        [accessor for _, accessor in COLLECTION_ACCESSORS],
        ids=[name for name, _ in COLLECTION_ACCESSORS],
    )
    def test_no_collection_is_iterable(
        self, service: TaxomeshService, accessor: Callable[[TaxomeshService], object]
    ) -> None:
        """``iter()`` on a collection raises ``TypeError``.

        Defining no ``__iter__`` is not enough. A class with ``__getitem__`` and no ``__iter__``
        is iterable anyway, through Python's old sequence protocol: ``iter()`` succeeds, and the
        first ``next()`` calls ``coll[0]``, which raises ``TypeError`` for an integer key that the
        caller did not give.

        ``pytest.raises`` takes the call rather than a ``with`` block because ``mypy`` rejects the
        statement ``iter(coll)`` too, which is the same rule stated statically.
        """
        pytest.raises(TypeError, iter, accessor(service))

    @pytest.mark.parametrize(
        "accessor",
        [accessor for _, accessor in COLLECTION_ACCESSORS],
        ids=[name for name, _ in COLLECTION_ACCESSORS],
    )
    def test_no_collection_is_reversible(
        self, service: TaxomeshService, accessor: Callable[[TaxomeshService], object]
    ) -> None:
        """``reversed()`` on a collection raises ``TypeError``.

        The old sequence protocol has a second door. A class with ``__len__`` and
        ``__getitem__`` is reversible without a ``__reversed__``: ``reversed()`` succeeds, a
        collection's by reading every row to take the length, and the first ``next()`` calls
        ``coll[len(coll) - 1]``, which raises ``TypeError`` for an integer key that the caller
        did not give, while over an empty store it yields nothing.

        The call form of ``pytest.raises``, for the reason the test above gives: ``mypy`` rejects
        the statement ``reversed(coll)``.
        """
        pytest.raises(TypeError, reversed, accessor(service))


class TestContainerLaw:
    """Subscript raises; ``get*`` never does."""

    def test_subscript_raises_on_a_missing_key(self, service: TaxomeshService) -> None:
        """``coll[missing]`` raises the entity's not-found error."""
        categories = service.categories

        with pytest.raises(TaxomeshCategoryNotFoundError):
            categories[uuid4()]

    def test_get_returns_none_on_a_missing_key(self, service: TaxomeshService) -> None:
        """``coll.get(missing)`` returns ``None`` and raises nothing."""
        categories = service.categories

        assert categories.get(uuid4()) is None

    def test_get_returns_the_supplied_default(self, service: TaxomeshService) -> None:
        """``coll.get(missing, default)`` returns the default."""
        categories = service.categories
        sentinel = object()

        assert categories.get(uuid4(), sentinel) is sentinel

    def test_membership_agrees_with_subscript(self, service: TaxomeshService) -> None:
        """``in`` is true exactly when subscript succeeds.

        Split from the length assertion below, which fails for an entirely different reason —
        the implicit root — and would otherwise mask this one.
        """
        categories = service.categories
        created = service.categories.create("Alpha")

        assert created.category_id in categories
        assert uuid4() not in categories

    def test_length_counts_only_the_categories_the_caller_created(self, service: TaxomeshService) -> None:
        """``len`` counts one category after one create: the implicit root is not a row.

        The root is a stored ``Category`` (``_ensure_root``) that the container does not show:
        ``len`` does not count it, ``in`` is ``False`` for it, and subscript raises.

        ``tests/service/test_collection_law.py`` asserts length *relatively* (``before + 1``).
        This one states the absolute count.
        """
        categories = service.categories
        service.categories.create("Alpha")

        assert len(categories) == 1

    def test_get_many_omits_absent_keys(self, service: TaxomeshService) -> None:
        """``get_many`` returns a mapping in which an absent key simply is not there."""
        categories = service.categories
        created = service.categories.create("Alpha")
        absent = uuid4()

        found = categories.get_many([created.category_id, absent])

        assert created.category_id in found
        assert absent not in found

    def test_get_by_slug_returns_none_rather_than_raising(self, service: TaxomeshService) -> None:
        """``get_by_slug`` answers with ``None``, as ``get_by_external_id`` does, under the law."""
        categories = service.categories

        assert categories.get_by_slug("no-such-slug") is None
