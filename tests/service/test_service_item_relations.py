"""Integration tests for TaxomeshService item relation methods.

Covers US1+US2 (relate_items, list_item_relations, list_related_items),
US3 (remove_item_relation), and US4 (cascade delete on item deletion).

All tests run against the shared InMemoryRepository fixture from conftest.py.
"""

from uuid import uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import ItemRelationLink
from taxomesh.exceptions import TaxomeshItemNotFoundError, TaxomeshRelationError

# ---------------------------------------------------------------------------
# US1 — relate_items
# ---------------------------------------------------------------------------


class TestRelateItems:
    """Tests for service.relate_items."""

    def test_creates_relation(self, service: TaxomeshService) -> None:
        src = service.create_item(name="A")
        tgt = service.create_item(name="B")
        link = service.relate_items(src.item_id, tgt.item_id, "covers")
        assert isinstance(link, ItemRelationLink)
        assert link.source_item_id == src.item_id
        assert link.target_item_id == tgt.item_id
        assert link.relation_type == "covers"
        assert link.sort_index == 0
        assert link.metadata == {}

    def test_upsert_updates_sort_index_and_metadata(self, service: TaxomeshService) -> None:
        src = service.create_item(name="A")
        tgt = service.create_item(name="B")
        service.relate_items(src.item_id, tgt.item_id, "covers")
        updated = service.relate_items(src.item_id, tgt.item_id, "covers", sort_index=5, metadata={"k": "v"})
        assert updated.sort_index == 5
        assert updated.metadata == {"k": "v"}
        # Only one relation should exist
        relations = service.list_item_relations(src.item_id)
        assert len(relations) == 1

    def test_case_normalisation_on_write(self, service: TaxomeshService) -> None:
        src = service.create_item(name="A")
        tgt = service.create_item(name="B")
        link = service.relate_items(src.item_id, tgt.item_id, "COVERS")
        assert link.relation_type == "covers"

    def test_case_normalised_upsert(self, service: TaxomeshService) -> None:
        src = service.create_item(name="A")
        tgt = service.create_item(name="B")
        service.relate_items(src.item_id, tgt.item_id, "covers")
        service.relate_items(src.item_id, tgt.item_id, "COVERS", sort_index=9)
        relations = service.list_item_relations(src.item_id)
        assert len(relations) == 1
        assert relations[0].sort_index == 9

    def test_nonexistent_source_raises(self, service: TaxomeshService) -> None:
        tgt = service.create_item(name="B")
        with pytest.raises(TaxomeshItemNotFoundError):
            service.relate_items(uuid4(), tgt.item_id, "covers")

    def test_nonexistent_target_raises(self, service: TaxomeshService) -> None:
        src = service.create_item(name="A")
        with pytest.raises(TaxomeshItemNotFoundError):
            service.relate_items(src.item_id, uuid4(), "covers")

    def test_self_relation_raises(self, service: TaxomeshService) -> None:
        item = service.create_item(name="A")
        with pytest.raises(TaxomeshRelationError, match="self"):
            service.relate_items(item.item_id, item.item_id, "loop")

    def test_empty_relation_type_raises(self, service: TaxomeshService) -> None:
        src = service.create_item(name="A")
        tgt = service.create_item(name="B")
        with pytest.raises(TaxomeshRelationError, match="empty"):
            service.relate_items(src.item_id, tgt.item_id, "")

    def test_whitespace_relation_type_raises(self, service: TaxomeshService) -> None:
        src = service.create_item(name="A")
        tgt = service.create_item(name="B")
        with pytest.raises(TaxomeshRelationError):
            service.relate_items(src.item_id, tgt.item_id, "   ")

    def test_with_metadata(self, service: TaxomeshService) -> None:
        src = service.create_item(name="A")
        tgt = service.create_item(name="B")
        link = service.relate_items(src.item_id, tgt.item_id, "covers", metadata={"confidence": "high"})
        assert link.metadata == {"confidence": "high"}


# ---------------------------------------------------------------------------
# US2 — list_item_relations and list_related_items
# ---------------------------------------------------------------------------


class TestListItemRelations:
    """Tests for service.list_item_relations."""

    def test_outgoing_default(self, service: TaxomeshService) -> None:
        a = service.create_item(name="A")
        b = service.create_item(name="B")
        c = service.create_item(name="C")
        service.relate_items(a.item_id, b.item_id, "covers")
        service.relate_items(a.item_id, c.item_id, "samples")
        links = service.list_item_relations(a.item_id)
        assert len(links) == 2
        targets = {lnk.target_item_id for lnk in links}
        assert targets == {b.item_id, c.item_id}

    def test_filter_by_relation_type(self, service: TaxomeshService) -> None:
        a = service.create_item(name="A")
        b = service.create_item(name="B")
        c = service.create_item(name="C")
        service.relate_items(a.item_id, b.item_id, "covers")
        service.relate_items(a.item_id, c.item_id, "samples")
        links = service.list_item_relations(a.item_id, relation_type="covers")
        assert len(links) == 1
        assert links[0].target_item_id == b.item_id

    def test_filter_case_insensitive(self, service: TaxomeshService) -> None:
        a = service.create_item(name="A")
        b = service.create_item(name="B")
        service.relate_items(a.item_id, b.item_id, "covers")
        links = service.list_item_relations(a.item_id, relation_type="COVERS")
        assert len(links) == 1

    def test_incoming_direction(self, service: TaxomeshService) -> None:
        a = service.create_item(name="A")
        b = service.create_item(name="B")
        c = service.create_item(name="C")
        service.relate_items(a.item_id, b.item_id, "covers")
        service.relate_items(c.item_id, b.item_id, "covers")
        links = service.list_item_relations(b.item_id, direction="incoming")
        assert len(links) == 2
        sources = {lnk.source_item_id for lnk in links}
        assert sources == {a.item_id, c.item_id}

    def test_empty_result_when_no_relations(self, service: TaxomeshService) -> None:
        item = service.create_item(name="A")
        assert service.list_item_relations(item.item_id) == []

    def test_outgoing_does_not_return_incoming(self, service: TaxomeshService) -> None:
        a = service.create_item(name="A")
        b = service.create_item(name="B")
        service.relate_items(b.item_id, a.item_id, "covers")
        assert service.list_item_relations(a.item_id) == []


class TestListRelatedItems:
    """Tests for service.list_related_items."""

    def test_returns_item_objects(self, service: TaxomeshService) -> None:
        a = service.create_item(name="A")
        b = service.create_item(name="B")
        service.relate_items(a.item_id, b.item_id, "covers")
        items = service.list_related_items(a.item_id)
        assert len(items) == 1
        assert items[0].item_id == b.item_id

    def test_incoming_direction(self, service: TaxomeshService) -> None:
        a = service.create_item(name="A")
        b = service.create_item(name="B")
        service.relate_items(a.item_id, b.item_id, "covers")
        items = service.list_related_items(b.item_id, direction="incoming")
        assert len(items) == 1
        assert items[0].item_id == a.item_id

    def test_filter_by_relation_type(self, service: TaxomeshService) -> None:
        a = service.create_item(name="A")
        b = service.create_item(name="B")
        c = service.create_item(name="C")
        service.relate_items(a.item_id, b.item_id, "covers")
        service.relate_items(a.item_id, c.item_id, "samples")
        items = service.list_related_items(a.item_id, relation_type="samples")
        assert len(items) == 1
        assert items[0].item_id == c.item_id

    def test_empty_when_no_relations(self, service: TaxomeshService) -> None:
        item = service.create_item(name="A")
        assert service.list_related_items(item.item_id) == []


# ---------------------------------------------------------------------------
# US3 — remove_item_relation
# ---------------------------------------------------------------------------


class TestRemoveItemRelation:
    """Tests for service.remove_item_relation."""

    def test_removes_relation(self, service: TaxomeshService) -> None:
        a = service.create_item(name="A")
        b = service.create_item(name="B")
        service.relate_items(a.item_id, b.item_id, "covers")
        service.remove_item_relation(a.item_id, b.item_id, "covers")
        assert service.list_item_relations(a.item_id) == []

    def test_only_removes_matching_triple(self, service: TaxomeshService) -> None:
        a = service.create_item(name="A")
        b = service.create_item(name="B")
        service.relate_items(a.item_id, b.item_id, "covers")
        service.relate_items(a.item_id, b.item_id, "samples")
        service.remove_item_relation(a.item_id, b.item_id, "covers")
        remaining = service.list_item_relations(a.item_id)
        assert len(remaining) == 1
        assert remaining[0].relation_type == "samples"

    def test_remove_nonexistent_raises(self, service: TaxomeshService) -> None:
        a = service.create_item(name="A")
        b = service.create_item(name="B")
        with pytest.raises(TaxomeshRelationError):
            service.remove_item_relation(a.item_id, b.item_id, "covers")

    def test_case_normalised_removal(self, service: TaxomeshService) -> None:
        a = service.create_item(name="A")
        b = service.create_item(name="B")
        service.relate_items(a.item_id, b.item_id, "covers")
        service.remove_item_relation(a.item_id, b.item_id, "COVERS")
        assert service.list_item_relations(a.item_id) == []


# ---------------------------------------------------------------------------
# US4 — cascade delete on item deletion
# ---------------------------------------------------------------------------


class TestCascadeDeleteOnItemDeletion:
    """Tests for cascade relation removal when an item is deleted."""

    def test_deleting_source_removes_outgoing_relations(self, service: TaxomeshService) -> None:
        a = service.create_item(name="A")
        b = service.create_item(name="B")
        c = service.create_item(name="C")
        service.relate_items(a.item_id, b.item_id, "covers")
        service.relate_items(a.item_id, c.item_id, "samples")
        service.delete_item(a.item_id)
        assert service.list_item_relations(b.item_id, direction="incoming") == []
        assert service.list_item_relations(c.item_id, direction="incoming") == []

    def test_deleting_target_removes_incoming_relations(self, service: TaxomeshService) -> None:
        a = service.create_item(name="A")
        b = service.create_item(name="B")
        c = service.create_item(name="C")
        service.relate_items(a.item_id, b.item_id, "covers")
        service.relate_items(c.item_id, b.item_id, "covers")
        service.delete_item(b.item_id)
        assert service.list_item_relations(a.item_id) == []
        assert service.list_item_relations(c.item_id) == []

    def test_unrelated_items_relations_unaffected(self, service: TaxomeshService) -> None:
        a = service.create_item(name="A")
        b = service.create_item(name="B")
        c = service.create_item(name="C")
        d = service.create_item(name="D")
        service.relate_items(a.item_id, b.item_id, "covers")
        service.relate_items(c.item_id, d.item_id, "samples")
        service.delete_item(a.item_id)
        remaining = service.list_item_relations(c.item_id)
        assert len(remaining) == 1
        assert remaining[0].target_item_id == d.item_id


# ---------------------------------------------------------------------------
# US6 — list_related_items_for_sources (batch)
# ---------------------------------------------------------------------------


class TestListRelatedItemsForSources:
    """Tests for service.list_related_items_for_sources."""

    def test_returns_grouped_dict(self, service: TaxomeshService) -> None:
        src1 = service.create_item(name="src1")
        src2 = service.create_item(name="src2")
        tgt1 = service.create_item(name="tgt1")
        tgt2 = service.create_item(name="tgt2")
        service.relate_items(src1.item_id, tgt1.item_id, "covers")
        service.relate_items(src2.item_id, tgt2.item_id, "covers")

        result = service.list_related_items_for_sources([src1.item_id, src2.item_id])
        assert set(result.keys()) == {src1.item_id, src2.item_id}
        assert len(result[src1.item_id]["covers"]) == 1
        assert result[src1.item_id]["covers"][0].item_id == tgt1.item_id
        assert len(result[src2.item_id]["covers"]) == 1
        assert result[src2.item_id]["covers"][0].item_id == tgt2.item_id

    def test_empty_source_ids_returns_empty_dict(self, service: TaxomeshService) -> None:
        result = service.list_related_items_for_sources([])
        assert result == {}

    def test_source_with_no_links_absent_from_result(self, service: TaxomeshService) -> None:
        src = service.create_item(name="src")
        result = service.list_related_items_for_sources([src.item_id])
        assert result == {}

    def test_deduplicates_source_ids(self, service: TaxomeshService) -> None:
        src = service.create_item(name="src")
        tgt = service.create_item(name="tgt")
        service.relate_items(src.item_id, tgt.item_id, "covers")

        result_once = service.list_related_items_for_sources([src.item_id])
        result_dup = service.list_related_items_for_sources([src.item_id, src.item_id])
        assert result_once == result_dup

    def test_filters_by_relation_types(self, service: TaxomeshService) -> None:
        src = service.create_item(name="src")
        t1 = service.create_item(name="T1")
        t2 = service.create_item(name="T2")
        service.relate_items(src.item_id, t1.item_id, "covers")
        service.relate_items(src.item_id, t2.item_id, "samples")

        result = service.list_related_items_for_sources([src.item_id], relation_types=["covers"])
        assert "covers" in result[src.item_id]
        assert "samples" not in result.get(src.item_id, {})

    def test_case_normalization_in_filter(self, service: TaxomeshService) -> None:
        src = service.create_item(name="src")
        tgt = service.create_item(name="tgt")
        service.relate_items(src.item_id, tgt.item_id, "covers")

        result = service.list_related_items_for_sources([src.item_id], relation_types=["COVERS"])
        assert src.item_id in result
        assert "covers" in result[src.item_id]

    def test_preserves_sort_index_order(self, service: TaxomeshService) -> None:
        src = service.create_item(name="src")
        t1 = service.create_item(name="T1")
        t2 = service.create_item(name="T2")
        service.relate_items(src.item_id, t1.item_id, "covers", sort_index=5)
        service.relate_items(src.item_id, t2.item_id, "covers", sort_index=1)

        result = service.list_related_items_for_sources([src.item_id])
        items = result[src.item_id]["covers"]
        assert items[0].item_id == t2.item_id
        assert items[1].item_id == t1.item_id

    def test_raises_for_missing_target_item(self, service: TaxomeshService) -> None:
        from uuid import uuid4  # noqa: PLC0415

        from taxomesh.domain.models import ItemRelationLink  # noqa: PLC0415

        src = service.create_item(name="src")
        # Save a relation link pointing to a non-existent target directly in the repo
        orphan_link = ItemRelationLink(
            source_item_id=src.item_id,
            target_item_id=uuid4(),
            relation_type="covers",
        )
        service._repo.save_item_relation_link(orphan_link)

        with pytest.raises(TaxomeshItemNotFoundError):
            service.list_related_items_for_sources([src.item_id])
