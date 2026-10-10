"""``Direction`` as a named type.

Relation direction is declared ``Literal["outgoing", "incoming", "both"]`` in the public
signatures. A domain-meaningful value is a named constant, not a bare literal.

The constraint that shapes the choice: **the literal form must stay legal.** Every existing
call site passes a plain string, and so does every stored value. A plain ``Enum`` would break
both. ``StrEnum`` members *are* their string values, so the constant becomes available without
the literal becoming illegal.
"""

from enum import StrEnum

from taxomesh.domain.types import Direction


class TestDirectionMembers:
    """The three directions, and only those three."""

    def test_has_exactly_the_three_documented_directions(self) -> None:
        """No member is added beyond what the service accepts."""
        assert {member.value for member in Direction} == {"outgoing", "incoming", "both"}

    def test_is_a_str_enum(self) -> None:
        """``StrEnum``, so members are usable anywhere a ``str`` is."""
        assert issubclass(Direction, StrEnum)
        assert issubclass(Direction, str)


class TestLiteralsStayLegal:
    """The plain strings keep working wherever a direction is taken."""

    def test_members_equal_their_string_values(self) -> None:
        """``Direction.OUTGOING == "outgoing"`` — so no existing comparison breaks.

        The comparison goes through ``str``-annotated variables on purpose. Comparing a member
        directly against a string *literal* is rejected by ``mypy --strict`` as a
        "non-overlapping equality check": it narrows the operands to
        ``Literal[Direction.OUTGOING]`` and ``Literal['outgoing']`` and treats those as
        disjoint, even though ``StrEnum`` makes them equal at runtime.

        So at a call site, ``direction == "outgoing"`` against a literal is flagged, while a
        comparison against a ``str``-typed value, which is what real call sites have, is fine.
        """
        outgoing: str = "outgoing"
        incoming: str = "incoming"
        both: str = "both"

        assert outgoing == Direction.OUTGOING
        assert incoming == Direction.INCOMING
        assert both == Direction.BOTH

    def test_a_plain_string_round_trips_to_a_member(self) -> None:
        """A caller passing the literal gets the member, so the two forms are interchangeable."""
        assert Direction("outgoing") is Direction.OUTGOING
        assert Direction("both") is Direction.BOTH

    def test_members_serialize_as_their_value(self) -> None:
        """Formatting and JSON produce the bare string, so a member and its value store the same text."""
        assert f"{Direction.BOTH}" == "both"
        assert str(Direction.INCOMING) == "incoming"

    def test_members_work_as_mapping_keys_alongside_strings(self) -> None:
        """A member and its literal are the same key.

        Relation code groups results by direction in dicts; if the two forms hashed
        differently, a member-keyed write would be invisible to a literal-keyed read.
        """
        by_direction = {"outgoing": 1}

        assert by_direction[Direction.OUTGOING] == 1
        assert hash(Direction.OUTGOING) == hash("outgoing")
