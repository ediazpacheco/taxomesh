"""The public ``UNSET`` sentinel.

``categories.update`` and ``items.update`` must distinguish three caller intentions:

* pass a value      → set the field to it
* pass ``None``     → set the field to ``None`` (clear it)
* pass **nothing**  → leave the field alone

``None`` cannot mean both of the last two, so a sentinel is required: ``UNSET``, of type
``UnsetType``. Both appear in the public annotations of the update methods, so both are public
and exported, and a caller can spell the type out.
"""

from taxomesh.domain.types import UNSET, UnsetType


class TestSentinelIdentity:
    """``UNSET`` is a singleton, so ``is`` comparison is reliable."""

    def test_unset_is_an_instance_of_its_type(self) -> None:
        """The exported value and the exported type belong together."""
        assert isinstance(UNSET, UnsetType)

    def test_there_is_exactly_one_of_it(self) -> None:
        """The type has a single member, so a second sentinel cannot be built.

        This is why ``UnsetType`` is a one-member ``Enum`` rather than a hand-rolled singleton:
        a caller who tried to construct their own sentinel would get one that fails every
        ``is UNSET`` check and silently reads as "leave alone" nowhere. ``Enum`` makes that
        impossible by construction instead of by convention.
        """
        assert len(UnsetType) == 1
        assert UnsetType("UNSET") is UNSET
        assert list(UnsetType) == [UNSET]

    def test_is_distinguishable_from_none(self) -> None:
        """The whole reason the sentinel exists."""
        assert UNSET is not None
        assert UNSET != None  # noqa: E711 — deliberate: identity and equality must both separate them

    def test_the_three_intentions_are_pairwise_distinct(self) -> None:
        """``UNSET``, ``None`` and ``""`` are three different answers, and stay so.

        Recorded so nobody "simplifies" an update check to ``if external_id:``. Truthiness
        cannot tell these apart — ``None`` and ``""`` are both falsy — and collapsing them
        would silently turn "clear this field" and "leave it alone" into the same operation.
        Only an identity check against the sentinel separates all three.
        """
        values = [UNSET, None, ""]

        for index, left in enumerate(values):
            for right in values[index + 1 :]:
                assert left is not right
                assert left != right


class TestSentinelRepr:
    """The sentinel reads well wherever it is printed."""

    def test_repr_is_stable_and_has_no_memory_address(self) -> None:
        """``repr(UNSET)`` must not embed an object address.

        Not cosmetic. The public-surface ledger in ``tests/surface/`` renders parameter
        defaults with ``repr``, and this sentinel is the default of two public methods. A
        default that renders ``<... object at 0x7f...>`` changes on every interpreter run, so
        the ledger could never match twice. ``tests/surface/_surface.py`` currently normalises
        that away; a stable ``repr`` here means it does not have to.
        """
        assert repr(UNSET) == "UNSET"
        assert "0x" not in repr(UNSET)
