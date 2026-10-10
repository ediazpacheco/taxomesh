"""One ``enabled`` rule, asserted on the signatures themselves.

The rule exists so that two members of the same collection never disagree about which rows
they mean:

====================================  =================  ==========================
member kind                           default            meaning
====================================  =================  ==========================
``list``, ``roots``, ``search``,      ``enabled=True``   enabled rows only
``list_related``,
``get_many_related``
``get_many``, ``get_many_by_*``       ``enabled=None``   unfiltered — agrees with ``get``
``get``, ``get_by_*``, ``[...]``,     *no parameter*     unfiltered, always
``in``, ``len``
====================================  =================  ==========================

**It is a regression guard.** A default silently flipping, ``get_many`` acquiring
``enabled=True`` say, would change which rows a caller gets back while every behavioural test
still passed, because each of those tests passes the filter it cares about explicitly.

It reads the signatures rather than calling the members, because the defect it guards against
*is* a signature: a default is the value a caller never writes down and therefore never checks.

Members are referenced directly rather than through ``getattr`` so the whole file is precisely
typed.
"""

import inspect
from collections.abc import Callable

import pytest

from taxomesh.application.collections.categories import CategoryCollection
from taxomesh.application.collections.items import ItemCollection
from taxomesh.application.collections.tags import TagCollection

type Member = tuple[str, Callable[..., object]]

# Filtering members: the caller asked for a subset, so the useful default is the enabled subset.
FILTERING: list[Member] = [
    ("CategoryCollection.list", CategoryCollection.list),
    ("CategoryCollection.roots", CategoryCollection.roots),
    ("CategoryCollection.search", CategoryCollection.search),
    ("ItemCollection.list", ItemCollection.list),
    ("ItemCollection.search", ItemCollection.search),
    ("ItemCollection.list_related", ItemCollection.list_related),
    ("ItemCollection.get_many_related", ItemCollection.get_many_related),
]

# Bulk lookups: the plural of ``get``, so they must answer as ``get`` answers — unfiltered.
BULK_LOOKUPS: list[Member] = [
    ("CategoryCollection.get_many", CategoryCollection.get_many),
    ("CategoryCollection.get_many_by_external_id", CategoryCollection.get_many_by_external_id),
    ("ItemCollection.get_many", ItemCollection.get_many),
    ("ItemCollection.get_many_by_external_id", ItemCollection.get_many_by_external_id),
]

# Single-row lookups and the container builtins: the container is the whole store.
UNFILTERED: list[Member] = [
    ("CategoryCollection.get", CategoryCollection.get),
    ("CategoryCollection.__getitem__", CategoryCollection.__getitem__),
    ("CategoryCollection.__contains__", CategoryCollection.__contains__),
    ("CategoryCollection.__len__", CategoryCollection.__len__),
    ("CategoryCollection.get_by_slug", CategoryCollection.get_by_slug),
    ("CategoryCollection.get_by_external_id", CategoryCollection.get_by_external_id),
    ("ItemCollection.get", ItemCollection.get),
    ("ItemCollection.__getitem__", ItemCollection.__getitem__),
    ("ItemCollection.__contains__", ItemCollection.__contains__),
    ("ItemCollection.__len__", ItemCollection.__len__),
    ("ItemCollection.get_by_slug", ItemCollection.get_by_slug),
    ("ItemCollection.get_by_external_id", ItemCollection.get_by_external_id),
    ("TagCollection.get", TagCollection.get),
    ("TagCollection.__getitem__", TagCollection.__getitem__),
    ("TagCollection.__contains__", TagCollection.__contains__),
    ("TagCollection.__len__", TagCollection.__len__),
]

# Every public member of the tag collection. ``Tag`` has no ``enabled`` field, so none of them
# may grow the parameter — a filter that cannot filter is a lie in a signature.
TAG_MEMBERS: list[Member] = [
    ("TagCollection.list", TagCollection.list),
    ("TagCollection.create", TagCollection.create),
    ("TagCollection.update", TagCollection.update),
    ("TagCollection.delete", TagCollection.delete),
    ("TagCollection.get_many", TagCollection.get_many),
    *UNFILTERED[-4:],
]


def _enabled(member: Callable[..., object]) -> inspect.Parameter | None:
    """Return the member's ``enabled`` parameter, or ``None`` when it has none."""
    return inspect.signature(member).parameters.get("enabled")


def _ids(members: list[Member]) -> list[str]:
    """Render the parametrization ids from the member labels."""
    return [label for label, _ in members]


@pytest.mark.parametrize(("label", "member"), FILTERING, ids=_ids(FILTERING))
def test_filtering_members_default_to_enabled_only(label: str, member: Callable[..., object]) -> None:
    """``list``, ``roots``, ``search`` and the two related reads return enabled rows unless asked otherwise."""
    parameter = _enabled(member)

    assert parameter is not None, f"{label} must accept an enabled filter"
    assert parameter.default is True, f"{label} must default to enabled=True, not {parameter.default!r}"


@pytest.mark.parametrize(("label", "member"), BULK_LOOKUPS, ids=_ids(BULK_LOOKUPS))
def test_bulk_lookups_default_to_unfiltered(label: str, member: Callable[..., object]) -> None:
    """``get_many`` is the plural of ``get``, so it must not filter by default.

    A ``True`` default here would make ``coll.get_many([x])`` and ``coll.get(x)`` disagree
    about the same row, the inconsistency the rule exists to prevent.
    """
    parameter = _enabled(member)

    assert parameter is not None, f"{label} must accept an enabled filter"
    assert parameter.default is None, f"{label} must default to enabled=None, not {parameter.default!r}"


@pytest.mark.parametrize(("label", "member"), UNFILTERED, ids=_ids(UNFILTERED))
def test_single_row_lookups_take_no_filter(label: str, member: Callable[..., object]) -> None:
    """Subscript, ``in``, ``len``, ``get`` and ``get_by_*`` see every stored row.

    The container is the whole store; filtering is what ``list()`` is for.
    """
    assert _enabled(member) is None, f"{label} must not accept an enabled filter"


@pytest.mark.parametrize(("label", "member"), TAG_MEMBERS, ids=_ids(TAG_MEMBERS))
def test_no_tag_member_accepts_the_filter(label: str, member: Callable[..., object]) -> None:
    """``Tag`` has no ``enabled`` field, so no tag member may advertise the filter.

    Not an oversight to be corrected later: the port's ``list_tags()`` accepts no filter
    either, and a parameter that cannot do anything is worse than a missing one.
    """
    assert _enabled(member) is None, f"{label} must not accept an enabled filter"


@pytest.mark.parametrize(("label", "member"), FILTERING + BULK_LOOKUPS, ids=_ids(FILTERING + BULK_LOOKUPS))
def test_the_filter_is_always_keyword_only(label: str, member: Callable[..., object]) -> None:
    """``enabled`` is never positional — the subject is the only positional parameter.

        Also a cache-key constraint, not only a style rule: the memoisation key is built from the
        call shape, so a parameter moving between positional and keyword changes the key
    .
    """
    parameter = _enabled(member)

    assert parameter is not None, f"{label} must accept an enabled filter"
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY, f"{label} must take enabled as keyword-only"
