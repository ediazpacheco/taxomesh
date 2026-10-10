"""The three domain models agree with each other.

=========================  ================
field                      rule
=========================  ================
``Category.name``          required
``Tag.name``               required
``Item.name``              required
``Category.category_id``   ``uuid4`` factory
``Item.item_id``           ``uuid4`` factory
``Tag.tag_id``             ``uuid4`` factory
=========================  ================

**Required does not mean non-empty**: ``Item(name="")`` still validates. A consumer syncing from
a system that has an identifier before it has a name can still say so; it just has to say so.

Tests are written against input **data** (``model_validate``) rather than constructor calls,
because that is what stored rows are, and because ``mypy --strict`` rightly rejects calling a
model without a required field.
"""

import pytest
from pydantic import ValidationError

from taxomesh.domain.models import Category, Item, Tag


class TestNameIsRequiredEverywhere:
    """A named thing must be named."""

    def test_item_data_without_a_name_is_rejected(self) -> None:
        """Item data with no ``name`` key is refused, as it is for the other two models.

        Written against data rather than a constructor call because that is exactly the case
        that matters: a stored row, read back off disk.
        """
        with pytest.raises(ValidationError):
            Item.model_validate({})

    @pytest.mark.parametrize("model", [Category, Tag], ids=["category", "tag"])
    def test_the_other_models_require_it_too(self, model: type[Category] | type[Tag]) -> None:
        """Category and tag data with no ``name`` key is refused."""
        with pytest.raises(ValidationError):
            model.model_validate({})

    def test_an_explicit_empty_name_is_still_accepted(self) -> None:
        """Required means *supplied*, not *non-empty*.

        The rule is that the three models agree, not a rule about content: a caller who wants
        an empty name may still say so. An absent field and an explicitly empty one are different
        inputs, and only the second is accepted.
        """
        assert Item(name="").name == ""


class TestIdentifiersAreGeneratedEverywhere:
    """Every model mints its own identifier."""

    def test_tag_generates_its_own_id(self) -> None:
        """``Tag(name=…)`` mints its own ``tag_id``, as the other two models do."""
        assert Tag(name="jazz").tag_id is not None

    def test_generated_ids_are_unique(self) -> None:
        """A factory, not a shared default — the classic mutable-default mistake."""
        assert Tag(name="a").tag_id != Tag(name="b").tag_id

    @pytest.mark.parametrize(
        ("model", "field"),
        [(Category, "category_id"), (Item, "item_id")],
        ids=["category", "item"],
    )
    def test_the_other_models_already_generated_theirs(self, model: type[Category] | type[Item], field: str) -> None:
        """Pinning the behaviour ``Tag`` is being brought into line with."""
        first = getattr(model(name="a"), field)
        second = getattr(model(name="b"), field)

        assert first is not None
        assert first != second

    def test_an_explicit_id_is_still_honoured(self) -> None:
        """Gaining a default must not stop a caller supplying one — repositories rely on it."""
        from uuid import uuid4  # noqa: PLC0415

        chosen = uuid4()

        assert Tag(tag_id=chosen, name="jazz").tag_id == chosen
