"""One conversion rule for external ids.

``ExternalId`` is ``str | int | UUID | None``, but what is *stored* is ``str | None``. Every
external-id parameter takes the wide type, because the common real-world external id is an
integer primary key from another system, and converting once in the library beats making every
consumer write ``str(pk)`` at every call.

The cost is contained, and asserted here:

* the conversion happens in **one** place, shared by writes, lookups and the models' own
  coercers, so a value written can always be found again;
* ``None`` is preserved, never stringified into ``"None"``;
* values sharing a string form are the **same row**, which collides under the one-row-per-value
  uniqueness of external ids.
"""

import numbers
from types import ModuleType
from typing import Any
from uuid import UUID, uuid4

import pytest

from taxomesh.domain.models import Category, Item
from taxomesh.domain.models import category as category_module
from taxomesh.domain.models import item as item_module
from taxomesh.domain.types import ExternalId, normalise_external_id


class TestNoneIsPreserved:
    """``None`` means "no external id" and must survive as ``None``."""

    def test_none_normalises_to_none(self) -> None:
        """The failure mode a naive ``str()`` introduces is ``"None"`` as a real id."""
        assert normalise_external_id(None) is None

    def test_none_never_becomes_the_string_none(self) -> None:
        """Stated separately because it is the specific bug being prevented."""
        assert normalise_external_id(None) != "None"


class TestEachAcceptedValueBecomesItsStringForm:
    """What is stored is the string form of the text, integer or UUID passed in."""

    def test_a_string_is_unchanged(self) -> None:
        """The common case is a no-op."""
        assert normalise_external_id("abc-123") == "abc-123"

    def test_an_int_becomes_its_digits(self) -> None:
        """The integer primary key this widening exists to serve."""
        assert normalise_external_id(42) == "42"

    def test_a_uuid_becomes_lowercase_hyphenated_text(self) -> None:
        """The canonical UUID text form.

        Documented because it is the one conversion a caller can get wrong from the outside: a
        consumer holding an uppercase or hyphen-less spelling of the same UUID will not match.
        """
        value = UUID("0f9a4b2c-1111-2222-3333-444455556666")

        assert normalise_external_id(value) == "0f9a4b2c-1111-2222-3333-444455556666"

    def test_an_empty_string_is_preserved_and_is_not_none(self) -> None:
        """Empty string is a value, not an absence: ``""`` and ``None`` stay distinguishable."""
        assert normalise_external_id("") == ""
        assert normalise_external_id("") is not None


class TestValuesSharingAStringFormCollide:
    """The accepted cost of widening, asserted rather than assumed."""

    @pytest.mark.parametrize(
        ("left", "right"),
        [
            (42, "42"),
            (0, "0"),
            (-1, "-1"),
        ],
        ids=["positive", "zero", "negative"],
    )
    def test_an_int_and_its_text_are_the_same_row(self, left: int, right: str) -> None:
        """``42`` and ``"42"`` address one row, so creating both is a conflict, not two rows."""
        assert normalise_external_id(left) == normalise_external_id(right)

    def test_a_uuid_and_its_text_are_the_same_row(self) -> None:
        """Same for a UUID and its canonical spelling."""
        value = uuid4()

        assert normalise_external_id(value) == normalise_external_id(str(value))


class PrimaryKey:
    """An integer that is not an ``int``, as a numpy integer is: registered as ``numbers.Integral``."""

    def __init__(self, value: int) -> None:
        self.value = value

    def __str__(self) -> str:
        return str(self.value)


numbers.Integral.register(PrimaryKey)


# Any: the refused values are what the annotation refuses, passed as an untyped caller can.
def untyped(value: object) -> Any:
    """Return ``value`` typed as anything, so a call can pass what its annotation refuses."""
    return value


class TestAnythingElseIsATypeError:
    """Only text, an integer, a UUID or ``None`` is an external id; anything else is the wrong type.

    ``str()`` of anything would be stored without complaint: a list would become the text
    ``"[1]"``, and ``True``, an ``int`` to Python, would become ``"True"`` while comparing equal to
    ``1``.
    """

    @pytest.mark.parametrize(
        "value", [[1], True, b"x", 1.5, object()], ids=["list", "bool", "bytes", "float", "object"]
    )
    def test_the_value_is_refused(self, value: object) -> None:
        with pytest.raises(TypeError, match="external id"):
            normalise_external_id(untyped(value))

    def test_an_integral_that_is_not_an_int_is_an_integer(self) -> None:
        """A primary key read through numpy or pandas is an integer, so it is accepted."""
        assert normalise_external_id(untyped(PrimaryKey(42))) == "42"

    def test_a_model_refuses_it_too(self) -> None:
        """The models convert through the same rule, so the refusal reaches a row built directly."""
        with pytest.raises(TypeError, match="external id"):
            Category.model_validate({"name": "Named", "external_id": [1]})


class TestTheRuleIsOneRule:
    """Writes and lookups must normalise identically."""

    def test_normalising_twice_changes_nothing(self) -> None:
        """Idempotent, so a value that has already been through the rule is unharmed.

        This is what lets the normaliser be applied at any boundary without tracking whether
        some earlier layer already applied it.
        """
        for value in ("abc", 42, uuid4(), None, ""):
            once = normalise_external_id(value)
            assert normalise_external_id(once) == once

    @pytest.mark.parametrize(
        ("module", "model"),
        [(item_module, Item), (category_module, Category)],
        ids=["Item", "Category"],
    )
    def test_the_models_convert_through_the_rule(
        self, monkeypatch: pytest.MonkeyPatch, module: ModuleType, model: type[Item] | type[Category]
    ) -> None:
        """A model built with an ``int`` external id converts it through the one rule.

        Every row loaded from storage and every model a caller constructs passes through the
        model's own coercer, which calls the one rule rather than repeating its body.
        """
        seen: list[object] = []

        def spy(value: ExternalId) -> str | None:
            seen.append(value)
            return normalise_external_id(value)

        monkeypatch.setattr(module, "normalise_external_id", spy, raising=False)

        assert model.model_validate({"name": "Named", "external_id": 42}).external_id == "42"
        assert seen == [42]
