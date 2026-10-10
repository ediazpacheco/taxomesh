"""Integration tests for the item relation members.

``items.relate``, ``items.list_relations``, ``items.list_related``, ``items.unrelate``, the
relations a deleted item takes with it, and ``items.get_many_related``.

Most tests run on the four-backend ``service`` fixture from conftest.py.
"""

from collections.abc import Collection
from typing import Final, Literal
from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import ItemRelationLink
from taxomesh.domain.types import Direction
from taxomesh.exceptions import TaxomeshItemNotFoundError, TaxomeshRelationError
from tests.service.conftest import InMemoryRepository

# The backends that can store a relation link naming an absent item. Django's foreign keys
# refuse one, so a dangling link cannot exist there.
DANGLING_LINK_BACKENDS: Final = ("in_memory", "json", "yaml")

# ---------------------------------------------------------------------------
# items.relate
# ---------------------------------------------------------------------------


class TestRelate:
    """Tests for service.items.relate."""

    def test_creates_relation(self, service: TaxomeshService) -> None:
        src = service.items.create(name="A")
        tgt = service.items.create(name="B")
        link = service.items.relate(src.item_id, tgt.item_id, "covers")
        assert isinstance(link, ItemRelationLink)
        assert link.source_item_id == src.item_id
        assert link.target_item_id == tgt.item_id
        assert link.relation_type == "covers"
        assert link.sort_index == 0
        assert link.metadata == {}

    def test_upsert_updates_sort_index_and_metadata(self, service: TaxomeshService) -> None:
        src = service.items.create(name="A")
        tgt = service.items.create(name="B")
        service.items.relate(src.item_id, tgt.item_id, "covers")
        updated = service.items.relate(src.item_id, tgt.item_id, "covers", sort_index=5, metadata={"k": "v"})
        assert updated.sort_index == 5
        assert updated.metadata == {"k": "v"}
        # Only one relation should exist
        relations = service.items.list_relations(src.item_id)
        assert len(relations) == 1

    def test_case_normalisation_on_write(self, service: TaxomeshService) -> None:
        src = service.items.create(name="A")
        tgt = service.items.create(name="B")
        link = service.items.relate(src.item_id, tgt.item_id, "COVERS")
        assert link.relation_type == "covers"

    def test_case_normalised_upsert(self, service: TaxomeshService) -> None:
        src = service.items.create(name="A")
        tgt = service.items.create(name="B")
        service.items.relate(src.item_id, tgt.item_id, "covers")
        service.items.relate(src.item_id, tgt.item_id, "COVERS", sort_index=9)
        relations = service.items.list_relations(src.item_id)
        assert len(relations) == 1
        assert relations[0].sort_index == 9

    def test_nonexistent_source_raises(self, service: TaxomeshService) -> None:
        tgt = service.items.create(name="B")
        with pytest.raises(TaxomeshItemNotFoundError):
            service.items.relate(uuid4(), tgt.item_id, "covers")

    def test_nonexistent_target_raises(self, service: TaxomeshService) -> None:
        src = service.items.create(name="A")
        with pytest.raises(TaxomeshItemNotFoundError):
            service.items.relate(src.item_id, uuid4(), "covers")

    def test_self_relation_raises(self, service: TaxomeshService) -> None:
        item = service.items.create(name="A")
        with pytest.raises(TaxomeshRelationError, match="An item cannot be related to itself"):
            service.items.relate(item.item_id, item.item_id, "loop")

    def test_empty_relation_type_raises(self, service: TaxomeshService) -> None:
        src = service.items.create(name="A")
        tgt = service.items.create(name="B")
        with pytest.raises(TaxomeshRelationError, match="empty"):
            service.items.relate(src.item_id, tgt.item_id, "")

    def test_whitespace_relation_type_raises(self, service: TaxomeshService) -> None:
        src = service.items.create(name="A")
        tgt = service.items.create(name="B")
        with pytest.raises(TaxomeshRelationError):
            service.items.relate(src.item_id, tgt.item_id, "   ")

    def test_with_metadata(self, service: TaxomeshService) -> None:
        src = service.items.create(name="A")
        tgt = service.items.create(name="B")
        link = service.items.relate(src.item_id, tgt.item_id, "covers", metadata={"confidence": "high"})
        assert link.metadata == {"confidence": "high"}


# ---------------------------------------------------------------------------
# items.list_relations and items.list_related
# ---------------------------------------------------------------------------


class TestListRelations:
    """Tests for service.items.list_relations."""

    def test_outgoing_default(self, service: TaxomeshService) -> None:
        a = service.items.create(name="A")
        b = service.items.create(name="B")
        c = service.items.create(name="C")
        service.items.relate(a.item_id, b.item_id, "covers")
        service.items.relate(a.item_id, c.item_id, "samples")
        links = service.items.list_relations(a.item_id)
        assert len(links) == 2
        targets = {lnk.target_item_id for lnk in links}
        assert targets == {b.item_id, c.item_id}

    def test_filter_by_relation_type(self, service: TaxomeshService) -> None:
        a = service.items.create(name="A")
        b = service.items.create(name="B")
        c = service.items.create(name="C")
        service.items.relate(a.item_id, b.item_id, "covers")
        service.items.relate(a.item_id, c.item_id, "samples")
        links = service.items.list_relations(a.item_id, relation_types=["covers"])
        assert len(links) == 1
        assert links[0].target_item_id == b.item_id

    def test_filter_case_insensitive(self, service: TaxomeshService) -> None:
        a = service.items.create(name="A")
        b = service.items.create(name="B")
        service.items.relate(a.item_id, b.item_id, "covers")
        links = service.items.list_relations(a.item_id, relation_types=["COVERS"])
        assert len(links) == 1

    def test_incoming_direction(self, service: TaxomeshService) -> None:
        a = service.items.create(name="A")
        b = service.items.create(name="B")
        c = service.items.create(name="C")
        service.items.relate(a.item_id, b.item_id, "covers")
        service.items.relate(c.item_id, b.item_id, "covers")
        links = service.items.list_relations(b.item_id, direction="incoming")
        assert len(links) == 2
        sources = {lnk.source_item_id for lnk in links}
        assert sources == {a.item_id, c.item_id}

    def test_empty_result_when_no_relations(self, service: TaxomeshService) -> None:
        item = service.items.create(name="A")
        assert service.items.list_relations(item.item_id) == ()

    def test_outgoing_does_not_return_incoming(self, service: TaxomeshService) -> None:
        a = service.items.create(name="A")
        b = service.items.create(name="B")
        service.items.relate(b.item_id, a.item_id, "covers")
        assert service.items.list_relations(a.item_id) == ()


class TestListRelationsBothDirection:
    """Tests for the ``direction="both"`` option of items.list_relations.

    An author item is the *source* of ``worked_with`` edges but the *target* of ``lyrics_by`` /
    ``music_by`` credits (stored work→author). Querying only outgoing relations silently drops
    every incoming credit, making such an author look orphaned.
    """

    def test_both_returns_union_of_outgoing_and_incoming(self, service: TaxomeshService) -> None:
        author = service.items.create(name="Author")
        peer = service.items.create(name="Peer")
        work = service.items.create(name="Work")
        # outgoing: author --worked_with--> peer
        service.items.relate(author.item_id, peer.item_id, "worked_with")
        # incoming: work --lyrics_by--> author
        service.items.relate(work.item_id, author.item_id, "lyrics_by")

        both = service.items.list_relations(author.item_id, direction="both")
        triples = {(lnk.source_item_id, lnk.target_item_id, lnk.relation_type) for lnk in both}
        assert triples == {
            (author.item_id, peer.item_id, "worked_with"),
            (work.item_id, author.item_id, "lyrics_by"),
        }

    def test_a_target_only_item_appears_in_incoming_and_both_not_outgoing(self, service: TaxomeshService) -> None:
        author = service.items.create(name="Author")
        work = service.items.create(name="Work")
        # The credit is stored work→author, so the author is ONLY ever a target.
        service.items.relate(work.item_id, author.item_id, "lyrics_by")

        # The outgoing read does not hold the credit.
        assert service.items.list_relations(author.item_id, direction="outgoing") == ()
        # incoming and both both surface it.
        incoming = service.items.list_relations(author.item_id, direction="incoming")
        both = service.items.list_relations(author.item_id, direction="both")
        assert len(incoming) == 1
        assert incoming[0].source_item_id == work.item_id
        assert {(lnk.source_item_id, lnk.target_item_id) for lnk in both} == {(work.item_id, author.item_id)}

    def test_both_with_bidirectional_worked_with_returns_both_rows(self, service: TaxomeshService) -> None:
        # worked_with stored as two distinct directed rows.
        a = service.items.create(name="A")
        b = service.items.create(name="B")
        service.items.relate(a.item_id, b.item_id, "worked_with")
        service.items.relate(b.item_id, a.item_id, "worked_with")

        both = service.items.list_relations(a.item_id, direction="both")
        # Two genuinely distinct directed edges — returned as-is, not deduplicated.
        assert len(both) == 2
        triples = {(lnk.source_item_id, lnk.target_item_id) for lnk in both}
        assert triples == {(a.item_id, b.item_id), (b.item_id, a.item_id)}

    def test_both_respects_relation_type_filter(self, service: TaxomeshService) -> None:
        author = service.items.create(name="Author")
        peer = service.items.create(name="Peer")
        work = service.items.create(name="Work")
        service.items.relate(author.item_id, peer.item_id, "worked_with")
        service.items.relate(work.item_id, author.item_id, "lyrics_by")

        filtered = service.items.list_relations(author.item_id, relation_types=["lyrics_by"], direction="both")
        assert len(filtered) == 1
        assert filtered[0].relation_type == "lyrics_by"
        assert filtered[0].source_item_id == work.item_id

    def test_both_empty_when_no_relations(self, service: TaxomeshService) -> None:
        item = service.items.create(name="Lonely")
        assert service.items.list_relations(item.item_id, direction="both") == ()


class TestListRelated:
    """Tests for service.items.list_related."""

    def test_returns_item_objects(self, service: TaxomeshService) -> None:
        a = service.items.create(name="A")
        b = service.items.create(name="B")
        service.items.relate(a.item_id, b.item_id, "covers")
        items = service.items.list_related(a.item_id)
        assert len(items) == 1
        assert items[0].item_id == b.item_id

    def test_incoming_direction(self, service: TaxomeshService) -> None:
        a = service.items.create(name="A")
        b = service.items.create(name="B")
        service.items.relate(a.item_id, b.item_id, "covers")
        items = service.items.list_related(b.item_id, direction="incoming")
        assert len(items) == 1
        assert items[0].item_id == a.item_id

    def test_both_direction_returns_other_endpoint(self, service: TaxomeshService) -> None:
        author = service.items.create(name="Author")
        peer = service.items.create(name="Peer")
        work = service.items.create(name="Work")
        service.items.relate(author.item_id, peer.item_id, "worked_with")  # outgoing → peer
        service.items.relate(work.item_id, author.item_id, "lyrics_by")  # incoming ← work
        items = service.items.list_related(author.item_id, direction="both")
        assert {it.item_id for it in items} == {peer.item_id, work.item_id}

    def test_filter_by_relation_type(self, service: TaxomeshService) -> None:
        a = service.items.create(name="A")
        b = service.items.create(name="B")
        c = service.items.create(name="C")
        service.items.relate(a.item_id, b.item_id, "covers")
        service.items.relate(a.item_id, c.item_id, "samples")
        items = service.items.list_related(a.item_id, relation_types=["samples"])
        assert len(items) == 1
        assert items[0].item_id == c.item_id

    def test_empty_when_no_relations(self, service: TaxomeshService) -> None:
        item = service.items.create(name="A")
        assert service.items.list_related(item.item_id) == ()


# ---------------------------------------------------------------------------
# items.unrelate
# ---------------------------------------------------------------------------


class TestUnrelate:
    """Tests for service.items.unrelate."""

    def test_removes_relation(self, service: TaxomeshService) -> None:
        a = service.items.create(name="A")
        b = service.items.create(name="B")
        service.items.relate(a.item_id, b.item_id, "covers")
        service.items.unrelate(a.item_id, b.item_id, "covers")
        assert service.items.list_relations(a.item_id) == ()

    def test_only_removes_matching_triple(self, service: TaxomeshService) -> None:
        a = service.items.create(name="A")
        b = service.items.create(name="B")
        service.items.relate(a.item_id, b.item_id, "covers")
        service.items.relate(a.item_id, b.item_id, "samples")
        service.items.unrelate(a.item_id, b.item_id, "covers")
        remaining = service.items.list_relations(a.item_id)
        assert len(remaining) == 1
        assert remaining[0].relation_type == "samples"

    def test_removing_a_relation_not_stored_changes_nothing(self, service: TaxomeshService) -> None:
        a = service.items.create(name="A")
        b = service.items.create(name="B")
        service.items.relate(b.item_id, a.item_id, "covers")

        service.items.unrelate(a.item_id, b.item_id, "covers")

        assert [(lnk.source_item_id, lnk.target_item_id) for lnk in service.items.list_relations(b.item_id)] == [
            (b.item_id, a.item_id)
        ]

    def test_case_normalised_removal(self, service: TaxomeshService) -> None:
        a = service.items.create(name="A")
        b = service.items.create(name="B")
        service.items.relate(a.item_id, b.item_id, "covers")
        service.items.unrelate(a.item_id, b.item_id, "COVERS")
        assert service.items.list_relations(a.item_id) == ()


# ---------------------------------------------------------------------------
# Cascade delete on item deletion
# ---------------------------------------------------------------------------


class TestCascadeDeleteOnItemDeletion:
    """Tests for cascade relation removal when an item is deleted."""

    def test_deleting_source_removes_outgoing_relations(self, service: TaxomeshService) -> None:
        a = service.items.create(name="A")
        b = service.items.create(name="B")
        c = service.items.create(name="C")
        service.items.relate(a.item_id, b.item_id, "covers")
        service.items.relate(a.item_id, c.item_id, "samples")
        service.items.delete(a.item_id)
        assert service.items.list_relations(b.item_id, direction="incoming") == ()
        assert service.items.list_relations(c.item_id, direction="incoming") == ()

    def test_deleting_target_removes_incoming_relations(self, service: TaxomeshService) -> None:
        a = service.items.create(name="A")
        b = service.items.create(name="B")
        c = service.items.create(name="C")
        service.items.relate(a.item_id, b.item_id, "covers")
        service.items.relate(c.item_id, b.item_id, "covers")
        service.items.delete(b.item_id)
        assert service.items.list_relations(a.item_id) == ()
        assert service.items.list_relations(c.item_id) == ()

    def test_unrelated_items_relations_unaffected(self, service: TaxomeshService) -> None:
        a = service.items.create(name="A")
        b = service.items.create(name="B")
        c = service.items.create(name="C")
        d = service.items.create(name="D")
        service.items.relate(a.item_id, b.item_id, "covers")
        service.items.relate(c.item_id, d.item_id, "samples")
        service.items.delete(a.item_id)
        remaining = service.items.list_relations(c.item_id)
        assert len(remaining) == 1
        assert remaining[0].target_item_id == d.item_id


# ---------------------------------------------------------------------------
# items.get_many_related (batch)
# ---------------------------------------------------------------------------


class TestGetManyRelated:
    """Tests for service.items.get_many_related."""

    def test_returns_grouped_dict(self, service: TaxomeshService) -> None:
        src1 = service.items.create(name="src1")
        src2 = service.items.create(name="src2")
        tgt1 = service.items.create(name="tgt1")
        tgt2 = service.items.create(name="tgt2")
        service.items.relate(src1.item_id, tgt1.item_id, "covers")
        service.items.relate(src2.item_id, tgt2.item_id, "covers")

        result = service.items.get_many_related([src1.item_id, src2.item_id])
        assert set(result.keys()) == {src1.item_id, src2.item_id}
        assert len(result[src1.item_id].of_type("covers")) == 1
        assert result[src1.item_id].of_type("covers")[0].item_id == tgt1.item_id
        assert len(result[src2.item_id].of_type("covers")) == 1
        assert result[src2.item_id].of_type("covers")[0].item_id == tgt2.item_id

    def test_empty_source_ids_returns_empty_dict(self, service: TaxomeshService) -> None:
        result = service.items.get_many_related([])
        assert result == {}

    def test_source_with_no_links_absent_from_result(self, service: TaxomeshService) -> None:
        src = service.items.create(name="src")
        result = service.items.get_many_related([src.item_id])
        assert result == {}

    def test_deduplicates_source_ids(self, service: TaxomeshService) -> None:
        src = service.items.create(name="src")
        tgt = service.items.create(name="tgt")
        service.items.relate(src.item_id, tgt.item_id, "covers")

        result_once = service.items.get_many_related([src.item_id])
        result_dup = service.items.get_many_related([src.item_id, src.item_id])
        assert result_once == result_dup

    def test_filters_by_relation_types(self, service: TaxomeshService) -> None:
        src = service.items.create(name="src")
        t1 = service.items.create(name="T1")
        t2 = service.items.create(name="T2")
        service.items.relate(src.item_id, t1.item_id, "covers")
        service.items.relate(src.item_id, t2.item_id, "samples")

        result = service.items.get_many_related([src.item_id], relation_types=["covers"])
        assert "covers" in result[src.item_id].relation_types
        assert "samples" not in result[src.item_id].relation_types

    def test_case_normalization_in_filter(self, service: TaxomeshService) -> None:
        src = service.items.create(name="src")
        tgt = service.items.create(name="tgt")
        service.items.relate(src.item_id, tgt.item_id, "covers")

        result = service.items.get_many_related([src.item_id], relation_types=["COVERS"])
        assert src.item_id in result
        assert "covers" in result[src.item_id].relation_types

    def test_preserves_sort_index_order(self, service: TaxomeshService) -> None:
        src = service.items.create(name="src")
        t1 = service.items.create(name="T1")
        t2 = service.items.create(name="T2")
        service.items.relate(src.item_id, t1.item_id, "covers", sort_index=5)
        service.items.relate(src.item_id, t2.item_id, "covers", sort_index=1)

        result = service.items.get_many_related([src.item_id])
        items = result[src.item_id].of_type("covers")
        assert items[0].item_id == t2.item_id
        assert items[1].item_id == t1.item_id

    @pytest.mark.parametrize("service", DANGLING_LINK_BACKENDS, indirect=True)
    def test_skips_a_missing_target_item(self, service: TaxomeshService) -> None:
        src = service.items.create(name="src")
        # Save a relation link pointing to a non-existent target directly in the repo
        orphan_link = ItemRelationLink(
            source_item_id=src.item_id,
            target_item_id=uuid4(),
            relation_type="covers",
        )
        service.repository.save_item_relation_link(orphan_link)

        assert service.items.get_many_related([src.item_id]) == {}


# ---------------------------------------------------------------------------
# 056 — direction-aware batched traversal: incoming
# ---------------------------------------------------------------------------


class TestGetManyRelatedIncoming:
    """Tests for service.items.get_many_related(direction="incoming")."""

    def test_returns_grouped_dict(self, service: TaxomeshService) -> None:
        src1 = service.items.create(name="src1")
        src2 = service.items.create(name="src2")
        tgt1 = service.items.create(name="tgt1")
        tgt2 = service.items.create(name="tgt2")
        service.items.relate(src1.item_id, tgt1.item_id, "covers")
        service.items.relate(src2.item_id, tgt2.item_id, "covers")

        # Query the targets; incoming returns the source-side items grouped by target.
        result = service.items.get_many_related([tgt1.item_id, tgt2.item_id], direction="incoming")
        assert set(result.keys()) == {tgt1.item_id, tgt2.item_id}
        assert [i.item_id for i in result[tgt1.item_id].of_type("covers")] == [src1.item_id]
        assert [i.item_id for i in result[tgt2.item_id].of_type("covers")] == [src2.item_id]

    def test_multiple_sources_under_one_target(self, service: TaxomeshService) -> None:
        s1 = service.items.create(name="s1")
        s2 = service.items.create(name="s2")
        tgt = service.items.create(name="tgt")
        service.items.relate(s1.item_id, tgt.item_id, "covers", sort_index=1)
        service.items.relate(s2.item_id, tgt.item_id, "covers", sort_index=0)

        result = service.items.get_many_related([tgt.item_id], direction="incoming")
        # ordered by (sort_index, source_item_id): s2 (sort 0) before s1 (sort 1)
        assert [i.item_id for i in result[tgt.item_id].of_type("covers")] == [s2.item_id, s1.item_id]

    def test_empty_input_returns_empty_dict(self, service: TaxomeshService) -> None:
        assert service.items.get_many_related([], direction="incoming") == {}

    def test_item_with_no_incoming_absent(self, service: TaxomeshService) -> None:
        # src has only an OUTGOING link; queried as a target it has no incoming links.
        src = service.items.create(name="src")
        tgt = service.items.create(name="tgt")
        service.items.relate(src.item_id, tgt.item_id, "covers")
        result = service.items.get_many_related([src.item_id], direction="incoming")
        assert result == {}

    def test_deduplicates_input_ids(self, service: TaxomeshService) -> None:
        src = service.items.create(name="src")
        tgt = service.items.create(name="tgt")
        service.items.relate(src.item_id, tgt.item_id, "covers")
        once = service.items.get_many_related([tgt.item_id], direction="incoming")
        dup = service.items.get_many_related([tgt.item_id, tgt.item_id], direction="incoming")
        assert once == dup

    def test_filters_by_relation_types_case_insensitive(self, service: TaxomeshService) -> None:
        s1 = service.items.create(name="s1")
        s2 = service.items.create(name="s2")
        tgt = service.items.create(name="tgt")
        service.items.relate(s1.item_id, tgt.item_id, "covers")
        service.items.relate(s2.item_id, tgt.item_id, "samples")

        result = service.items.get_many_related([tgt.item_id], relation_types=["COVERS"], direction="incoming")
        assert "covers" in result[tgt.item_id].relation_types
        assert "samples" not in result[tgt.item_id].relation_types

    @pytest.mark.parametrize("service", DANGLING_LINK_BACKENDS, indirect=True)
    def test_skips_a_missing_source_item(self, service: TaxomeshService) -> None:
        tgt = service.items.create(name="tgt")
        orphan_link = ItemRelationLink(
            source_item_id=uuid4(),
            target_item_id=tgt.item_id,
            relation_type="covers",
        )
        service.repository.save_item_relation_link(orphan_link)

        assert service.items.get_many_related([tgt.item_id], direction="incoming") == {}


# ---------------------------------------------------------------------------
# 056 — direction-aware batched traversal: default outgoing preserved
# ---------------------------------------------------------------------------


class TestGetManyRelatedDefaultEquivalence:
    """The default (no direction arg) must equal direction="outgoing"."""

    def test_default_equals_explicit_outgoing(self, service: TaxomeshService) -> None:
        src = service.items.create(name="src")
        t1 = service.items.create(name="t1")
        t2 = service.items.create(name="t2")
        service.items.relate(src.item_id, t1.item_id, "covers", sort_index=0)
        service.items.relate(src.item_id, t2.item_id, "samples", sort_index=1)

        default = service.items.get_many_related([src.item_id])
        explicit = service.items.get_many_related([src.item_id], direction="outgoing")
        assert default == explicit
        assert [i.item_id for i in default[src.item_id].of_type("covers")] == [t1.item_id]


# ---------------------------------------------------------------------------
# 056 — direction-aware batched traversal: both
# ---------------------------------------------------------------------------


class TestGetManyRelatedBoth:
    """Tests for service.items.get_many_related(direction="both")."""

    def test_unions_outgoing_and_incoming(self, service: TaxomeshService) -> None:
        mid = service.items.create(name="mid")
        out_tgt = service.items.create(name="out_tgt")
        in_src = service.items.create(name="in_src")
        # mid --covers--> out_tgt   (outgoing for mid)
        # in_src --covers--> mid    (incoming for mid)
        service.items.relate(mid.item_id, out_tgt.item_id, "covers")
        service.items.relate(in_src.item_id, mid.item_id, "covers")

        result = service.items.get_many_related([mid.item_id], direction="both")
        related_ids = [i.item_id for i in result[mid.item_id].of_type("covers")]
        # Documented union order: outgoing-derived first, then incoming-derived.
        assert related_ids == [out_tgt.item_id, in_src.item_id]

    def test_empty_input_returns_empty_dict(self, service: TaxomeshService) -> None:
        assert service.items.get_many_related([], direction="both") == {}

    def test_filters_by_relation_types(self, service: TaxomeshService) -> None:
        mid = service.items.create(name="mid")
        out_tgt = service.items.create(name="out_tgt")
        in_src = service.items.create(name="in_src")
        service.items.relate(mid.item_id, out_tgt.item_id, "covers")
        service.items.relate(in_src.item_id, mid.item_id, "samples")

        result = service.items.get_many_related([mid.item_id], relation_types=["covers"], direction="both")
        assert "covers" in result[mid.item_id].relation_types
        assert "samples" not in result[mid.item_id].relation_types

    def test_link_with_both_endpoints_queried_appears_on_both_sides(self, service: TaxomeshService) -> None:
        """A single link A→B, querying [A, B] with both, yields A's outgoing (B) and B's incoming (A)."""
        a = service.items.create(name="A")
        b = service.items.create(name="B")
        service.items.relate(a.item_id, b.item_id, "covers")

        result = service.items.get_many_related([a.item_id, b.item_id], direction="both")
        assert [i.item_id for i in result[a.item_id].of_type("covers")] == [b.item_id]
        assert [i.item_id for i in result[b.item_id].of_type("covers")] == [a.item_id]


# ---------------------------------------------------------------------------
# A Direction member is accepted wherever a direction is
# ---------------------------------------------------------------------------


def _related_around(service: TaxomeshService) -> UUID:
    """Relate a middle item to one target and from one source, and return the middle item."""
    mid = service.items.create(name="mid")
    target = service.items.create(name="target")
    source = service.items.create(name="source")
    service.items.relate(mid.item_id, target.item_id, "covers")
    service.items.relate(source.item_id, mid.item_id, "samples")
    return mid.item_id


@pytest.mark.parametrize("direction", list(Direction), ids=[member.value for member in Direction])
class TestADirectionMemberIsAccepted:
    """Each relation read answers a ``Direction`` member exactly as it answers the member's value.

    The cache is cleared between the two calls: a member and its value are one cache key, so
    without it the second call would be served the first call's answer and prove nothing.
    """

    def test_list_relations(self, service: TaxomeshService, direction: Direction) -> None:
        mid = _related_around(service)
        by_member = service.items.list_relations(mid, direction=direction)
        service._cache.clear()
        assert by_member == service.items.list_relations(mid, direction=direction.value)
        assert by_member

    def test_list_related(self, service: TaxomeshService, direction: Direction) -> None:
        mid = _related_around(service)
        by_member = service.items.list_related(mid, direction=direction)
        service._cache.clear()
        assert by_member == service.items.list_related(mid, direction=direction.value)
        assert by_member

    def test_get_many_related(self, service: TaxomeshService, direction: Direction) -> None:
        mid = _related_around(service)
        by_member = service.items.get_many_related([mid], direction=direction)
        service._cache.clear()
        by_value = service.items.get_many_related([mid], direction=direction.value)
        assert {item_id: group.by_type for item_id, group in by_member.items()} == {
            item_id: group.by_type for item_id, group in by_value.items()
        }
        assert by_member


class _DirectionRecordingRepository(InMemoryRepository):
    """Records the direction each relation read hands the port."""

    def __init__(self) -> None:
        super().__init__()
        self.directions: list[object] = []

    def list_item_relation_links(
        self,
        item_id: UUID,
        *,
        relation_types: Collection[str] | None = None,
        direction: Literal["outgoing", "incoming", "both"] = "outgoing",
    ) -> list[ItemRelationLink]:
        self.directions.append(direction)
        return super().list_item_relation_links(item_id, relation_types=relation_types, direction=direction)

    def list_item_relation_links_batch(
        self,
        item_ids: Collection[UUID],
        *,
        relation_types: Collection[str] | None = None,
        direction: Literal["outgoing", "incoming", "both"] = "outgoing",
    ) -> list[ItemRelationLink]:
        self.directions.append(direction)
        return super().list_item_relation_links_batch(item_ids, relation_types=relation_types, direction=direction)


def test_a_direction_member_reaches_the_port_as_its_value() -> None:
    """The port's parameter is a ``Literal`` of the three strings, so a member arrives as its string."""
    repository = _DirectionRecordingRepository()
    service = TaxomeshService(repository=repository)
    mid = _related_around(service)

    service.items.list_relations(mid, direction=Direction.INCOMING)
    service.items.list_related(mid, direction=Direction.BOTH)
    service.items.get_many_related([mid], direction=Direction.OUTGOING)

    assert repository.directions == ["incoming", "both", "outgoing"]
    assert all(type(direction) is str for direction in repository.directions)
