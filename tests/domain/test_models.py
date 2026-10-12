from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from taxomesh.domain.models import (
    Category,
    CategoryParentLink,
    Item,
    ItemParentLink,
    ItemTagLink,
    ModelBase,
    Tag,
)


class TestModelBase:
    def test_populate_by_name_is_true(self) -> None:
        assert ModelBase.model_config["populate_by_name"] is True

    def test_frozen_is_true(self) -> None:
        assert ModelBase.model_config["frozen"] is True

    def test_assignment_is_refused(self) -> None:
        tag = Tag(tag_id=uuid4(), name="valid")
        with pytest.raises(ValidationError, match="frozen"):
            tag.name = "renamed"
        assert tag.name == "valid"


class TestItem:
    def test_construction(self) -> None:
        item = Item.model_validate({"name": "Item", "external_id": 42})
        assert item.external_id == "42"

    def test_item_id_auto_generated(self) -> None:
        item = Item(name="Item", external_id="1")
        assert isinstance(item.item_id, UUID)

    def test_item_id_unique_per_instance(self) -> None:
        a = Item(name="Item", external_id="1")
        b = Item(name="Item", external_id="1")
        assert a.item_id != b.item_id

    def test_external_id_accepts_uuid(self) -> None:
        uid = uuid4()
        item = Item.model_validate({"name": "Item", "external_id": uid})
        assert item.external_id == str(uid)

    def test_external_id_accepts_str(self) -> None:
        item = Item(name="Item", external_id="abc")
        assert item.external_id == "abc"

    def test_external_id_accepts_int(self) -> None:
        item = Item.model_validate({"name": "Item", "external_id": 99})
        assert item.external_id == "99"

    def test_external_id_str_at_max_length_is_valid(self) -> None:
        item = Item(name="Item", external_id="a" * 256)
        assert len(str(item.external_id)) == 256  # noqa: PLR2004

    def test_external_id_str_exceeding_max_length_raises(self) -> None:
        with pytest.raises(ValidationError):
            Item(name="Item", external_id="x" * 257)

    def test_enabled_defaults_true(self) -> None:
        item = Item(name="Item", external_id="1")
        assert item.enabled is True

    def test_metadata_defaults_empty_dict(self) -> None:
        item = Item(name="Item", external_id="1")
        assert item.metadata == {}

    def test_metadata_instances_are_independent(self) -> None:
        a = Item(name="Item", external_id="1")
        b = Item(name="Item", external_id="2")
        with pytest.raises(TypeError):
            a.metadata["key"] = "value"
        assert b.metadata == {}

    def test_external_id_defaults_none(self) -> None:
        item = Item(name="test")
        assert item.external_id is None

    def test_external_id_none_stays_none(self) -> None:
        item = Item(name="test", external_id=None)
        assert item.external_id is None

    def test_str_no_slug_no_external_id(self) -> None:
        uid = uuid4()
        item = Item(item_id=uid, name="Product")
        assert str(item) == f"Product (id: {uid})"

    def test_str_with_slug(self) -> None:
        uid = uuid4()
        item = Item(item_id=uid, name="Product", slug="p1")
        assert str(item) == f"Product (slug: p1, id: {uid})"

    def test_str_with_external_id(self) -> None:
        uid = uuid4()
        item = Item(item_id=uid, name="Product", external_id="EXT-1")
        assert str(item) == f"Product (id: {uid}, external_id: EXT-1)"


class TestCategory:
    def test_construction(self) -> None:
        cat = Category(category_id=uuid4(), name="Rock")
        assert cat.name == "Rock"

    def test_name_at_max_length_is_valid(self) -> None:
        cat = Category(category_id=uuid4(), name="a" * 256)
        assert len(cat.name) == 256  # noqa: PLR2004

    def test_name_exceeding_max_length_raises(self) -> None:
        with pytest.raises(ValidationError):
            Category(category_id=uuid4(), name="x" * 257)

    def test_description_defaults_empty_string(self) -> None:
        cat = Category(category_id=uuid4(), name="Jazz")
        assert cat.description == ""

    def test_description_accepts_value(self) -> None:
        cat = Category(category_id=uuid4(), name="Jazz", description="A music genre")
        assert cat.description == "A music genre"

    def test_description_at_max_length_is_valid(self) -> None:
        cat = Category(category_id=uuid4(), name="Jazz", description="a" * 100_000)
        assert len(cat.description) == 100_000  # noqa: PLR2004

    def test_description_exceeding_max_length_raises(self) -> None:
        with pytest.raises(ValidationError):
            Category(category_id=uuid4(), name="Jazz", description="x" * 100_001)

    def test_metadata_defaults_empty_dict(self) -> None:
        cat = Category(category_id=uuid4(), name="Pop")
        assert cat.metadata == {}

    def test_enabled_defaults_true(self) -> None:
        cat = Category(category_id=uuid4(), name="Rock")
        assert cat.enabled is True

    def test_external_id_defaults_none(self) -> None:
        cat = Category(category_id=uuid4(), name="Rock")
        assert cat.external_id is None

    def test_explicit_enabled_false_and_external_id(self) -> None:
        cat = Category(
            category_id=uuid4(),
            name="Jazz",
            enabled=False,
            external_id="genre-rock",
        )
        assert cat.enabled is False
        assert cat.external_id == "genre-rock"

    def test_missing_enabled_and_external_id_take_their_defaults(self) -> None:
        data = {"category_id": str(uuid4()), "name": "Plain"}
        cat = Category.model_validate(data)
        assert cat.enabled is True
        assert cat.external_id is None

    def test_round_trip_persistence(self) -> None:
        cat = Category(
            category_id=uuid4(),
            name="Rock",
            enabled=False,
            external_id="genre-rock",
        )
        dumped = cat.model_dump()
        restored = Category.model_validate(dumped)
        assert restored.enabled is False
        assert restored.external_id == "genre-rock"

    def test_str_no_slug_no_external_id(self) -> None:
        uid = uuid4()
        cat = Category(category_id=uid, name="Rock")
        assert str(cat) == f"Rock (id: {uid})"

    def test_str_with_slug(self) -> None:
        uid = uuid4()
        cat = Category(category_id=uid, name="Rock", slug="rock")
        assert str(cat) == f"Rock (slug: rock, id: {uid})"

    def test_str_with_slug_and_external_id(self) -> None:
        uid = uuid4()
        cat = Category(category_id=uid, name="Rock", slug="rock", external_id="genre-rock")
        assert str(cat) == f"Rock (slug: rock, id: {uid}, external_id: genre-rock)"

    def test_str_with_external_id_only(self) -> None:
        uid = uuid4()
        cat = Category(category_id=uid, name="Rock", external_id="genre-rock")
        assert str(cat) == f"Rock (id: {uid}, external_id: genre-rock)"


class TestTag:
    def test_construction(self) -> None:
        tag = Tag(tag_id=uuid4(), name="live")
        assert tag.name == "live"

    def test_name_at_max_length_is_valid(self) -> None:
        tag = Tag(tag_id=uuid4(), name="a" * 25)
        assert len(tag.name) == 25  # noqa: PLR2004

    def test_name_exceeding_max_length_raises(self) -> None:
        with pytest.raises(ValidationError):
            Tag(tag_id=uuid4(), name="x" * 26)

    def test_metadata_defaults_empty_dict(self) -> None:
        tag = Tag(tag_id=uuid4(), name="live")
        assert tag.metadata == {}

    def test_str_is_its_name_and_id(self) -> None:
        uid = uuid4()
        assert str(Tag(tag_id=uid, name="live")) == f"live (id: {uid})"


class TestCategoryParentLink:
    def test_construction(self) -> None:
        link = CategoryParentLink(category_id=uuid4(), parent_category_id=uuid4())
        assert isinstance(link.category_id, UUID)
        assert isinstance(link.parent_category_id, UUID)

    def test_sort_index_defaults_zero(self) -> None:
        link = CategoryParentLink(category_id=uuid4(), parent_category_id=uuid4())
        assert link.sort_index == 0

    def test_sort_index_is_int(self) -> None:
        link = CategoryParentLink(category_id=uuid4(), parent_category_id=uuid4(), sort_index=5)
        assert isinstance(link.sort_index, int)
        assert link.sort_index == 5  # noqa: PLR2004


class TestItemParentLink:
    def test_construction(self) -> None:
        link = ItemParentLink(item_id=uuid4(), category_id=uuid4())
        assert isinstance(link.item_id, UUID)
        assert isinstance(link.category_id, UUID)

    def test_item_id_is_uuid(self) -> None:
        uid = uuid4()
        link = ItemParentLink(item_id=uid, category_id=uuid4())
        assert link.item_id == uid

    def test_sort_index_defaults_zero(self) -> None:
        link = ItemParentLink(item_id=uuid4(), category_id=uuid4())
        assert link.sort_index == 0


class TestItemTagLink:
    def test_construction(self) -> None:
        link = ItemTagLink(tag_id=uuid4(), item_id=uuid4())
        assert isinstance(link.tag_id, UUID)
        assert isinstance(link.item_id, UUID)

    def test_item_id_is_uuid(self) -> None:
        uid = uuid4()
        link = ItemTagLink(tag_id=uuid4(), item_id=uid)
        assert link.item_id == uid
