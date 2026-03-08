"""Unit tests for the ItemRelationLink domain model.

Covers: valid construction, self-relation rejection, empty/whitespace
relation_type rejection, and case normalisation (relation_type is lowercased).
"""

from uuid import UUID, uuid4

import pytest

from taxomesh.domain.models.item_relation_link import ItemRelationLink
from taxomesh.exceptions import TaxomeshRelationError

SRC = uuid4()
TGT = uuid4()


class TestItemRelationLinkConstruction:
    """Valid construction scenarios."""

    def test_valid_minimal(self) -> None:
        link = ItemRelationLink(source_item_id=SRC, target_item_id=TGT, relation_type="covers")
        assert link.source_item_id == SRC
        assert link.target_item_id == TGT
        assert link.relation_type == "covers"
        assert link.sort_index == 0
        assert link.metadata == {}

    def test_valid_with_all_fields(self) -> None:
        link = ItemRelationLink(
            source_item_id=SRC,
            target_item_id=TGT,
            relation_type="samples",
            sort_index=3,
            metadata={"confidence": "high"},
        )
        assert link.sort_index == 3
        assert link.metadata == {"confidence": "high"}


class TestRelationTypeCaseNormalisation:
    """relation_type is normalised to lowercase before storage."""

    def test_uppercase_is_lowercased(self) -> None:
        link = ItemRelationLink(source_item_id=SRC, target_item_id=TGT, relation_type="COVERS")
        assert link.relation_type == "covers"

    def test_mixed_case_is_lowercased(self) -> None:
        link = ItemRelationLink(source_item_id=SRC, target_item_id=TGT, relation_type="Music_By")
        assert link.relation_type == "music_by"

    def test_leading_trailing_whitespace_is_stripped_then_lowercased(self) -> None:
        link = ItemRelationLink(source_item_id=SRC, target_item_id=TGT, relation_type="  Covers  ")
        assert link.relation_type == "covers"

    def test_already_lowercase_unchanged(self) -> None:
        link = ItemRelationLink(source_item_id=SRC, target_item_id=TGT, relation_type="covers")
        assert link.relation_type == "covers"


class TestSelfRelationRejection:
    """source_item_id == target_item_id must raise TaxomeshRelationError."""

    def test_self_relation_raises(self) -> None:
        same_id = uuid4()
        with pytest.raises(TaxomeshRelationError, match="self"):
            ItemRelationLink(source_item_id=same_id, target_item_id=same_id, relation_type="loop")

    def test_distinct_ids_do_not_raise(self) -> None:
        ItemRelationLink(source_item_id=uuid4(), target_item_id=uuid4(), relation_type="ok")


class TestRelationTypeValidation:
    """Empty or whitespace-only relation_type must raise TaxomeshRelationError."""

    def test_empty_string_raises(self) -> None:
        with pytest.raises(TaxomeshRelationError, match="empty"):
            ItemRelationLink(source_item_id=SRC, target_item_id=TGT, relation_type="")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(TaxomeshRelationError, match="empty"):
            ItemRelationLink(source_item_id=SRC, target_item_id=TGT, relation_type="   ")

    def test_tab_only_raises(self) -> None:
        with pytest.raises(TaxomeshRelationError, match="empty"):
            ItemRelationLink(source_item_id=SRC, target_item_id=TGT, relation_type="\t")


class TestFieldTypes:
    """Field types and defaults are correct."""

    def test_source_and_target_are_uuid(self) -> None:
        link = ItemRelationLink(source_item_id=SRC, target_item_id=TGT, relation_type="x")
        assert isinstance(link.source_item_id, UUID)
        assert isinstance(link.target_item_id, UUID)

    def test_sort_index_default_zero(self) -> None:
        link = ItemRelationLink(source_item_id=SRC, target_item_id=TGT, relation_type="x")
        assert link.sort_index == 0

    def test_metadata_default_empty_dict(self) -> None:
        link = ItemRelationLink(source_item_id=SRC, target_item_id=TGT, relation_type="x")
        assert link.metadata == {}

    def test_metadata_is_independent_per_instance(self) -> None:
        a = ItemRelationLink(source_item_id=SRC, target_item_id=TGT, relation_type="x")
        b = ItemRelationLink(source_item_id=SRC, target_item_id=TGT, relation_type="y")
        a.metadata["k"] = "v"
        assert b.metadata == {}
