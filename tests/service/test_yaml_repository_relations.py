"""Persistence round-trip tests for ItemRelationLink in YAMLRepository (US5)."""

from pathlib import Path
from uuid import uuid4

import pytest
import yaml

from taxomesh.adapters.repositories.yaml_repository import YAMLRepository
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import ItemRelationLink


@pytest.fixture
def tmp_yaml_path(tmp_path: Path) -> Path:
    """Return a path for a YAML repo file that does not exist yet."""
    return tmp_path / "taxomesh_test.yaml"


def _fresh(path: Path) -> TaxomeshService:
    """Return a new TaxomeshService backed by a fresh load of the YAML file."""
    return TaxomeshService(repository=YAMLRepository(path))


class TestYAMLRelationRoundTrip:
    """All five fields survive a save → reload cycle."""

    def test_all_fields_survive_reload(self, tmp_yaml_path: Path) -> None:
        svc = _fresh(tmp_yaml_path)
        src = svc.create_item(name="A")
        tgt = svc.create_item(name="B")
        svc.relate_items(src.item_id, tgt.item_id, "covers", sort_index=7, metadata={"k": "v"})

        svc2 = _fresh(tmp_yaml_path)
        links = svc2.list_item_relations(src.item_id)
        assert len(links) == 1
        lnk = links[0]
        assert lnk.source_item_id == src.item_id
        assert lnk.target_item_id == tgt.item_id
        assert lnk.relation_type == "covers"
        assert lnk.sort_index == 7
        assert lnk.metadata == {"k": "v"}

    def test_multiple_relations_survive_reload(self, tmp_yaml_path: Path) -> None:
        svc = _fresh(tmp_yaml_path)
        a = svc.create_item(name="A")
        b = svc.create_item(name="B")
        c = svc.create_item(name="C")
        svc.relate_items(a.item_id, b.item_id, "covers")
        svc.relate_items(a.item_id, c.item_id, "samples")

        svc2 = _fresh(tmp_yaml_path)
        links = svc2.list_item_relations(a.item_id)
        assert len(links) == 2
        types = {lnk.relation_type for lnk in links}
        assert types == {"covers", "samples"}

    def test_upsert_survives_reload(self, tmp_yaml_path: Path) -> None:
        svc = _fresh(tmp_yaml_path)
        src = svc.create_item(name="A")
        tgt = svc.create_item(name="B")
        svc.relate_items(src.item_id, tgt.item_id, "covers", sort_index=1)
        svc.relate_items(src.item_id, tgt.item_id, "covers", sort_index=9, metadata={"updated": True})

        svc2 = _fresh(tmp_yaml_path)
        links = svc2.list_item_relations(src.item_id)
        assert len(links) == 1
        assert links[0].sort_index == 9
        assert links[0].metadata == {"updated": True}

    def test_relation_written_to_yaml_file(self, tmp_yaml_path: Path) -> None:
        svc = _fresh(tmp_yaml_path)
        src = svc.create_item(name="A")
        tgt = svc.create_item(name="B")
        svc.relate_items(src.item_id, tgt.item_id, "covers")

        raw = yaml.safe_load(tmp_yaml_path.read_text())
        assert "item_relation_links" in raw
        assert len(raw["item_relation_links"]) == 1
        assert raw["item_relation_links"][0]["relation_type"] == "covers"

    def test_cascade_delete_survives_reload(self, tmp_yaml_path: Path) -> None:
        svc = _fresh(tmp_yaml_path)
        src = svc.create_item(name="A")
        tgt = svc.create_item(name="B")
        svc.relate_items(src.item_id, tgt.item_id, "covers")
        svc.delete_item(src.item_id)

        svc2 = _fresh(tmp_yaml_path)
        links = svc2.list_item_relations(tgt.item_id, direction="incoming")
        assert links == []


class TestYAMLBackwardCompat:
    """Files without 'item_relation_links' key load as empty list."""

    def test_missing_key_loads_as_empty(self, tmp_yaml_path: Path) -> None:
        minimal: dict[str, object] = {
            "categories": {},
            "items": {},
            "tags": {},
            "item_tag_links": [],
            "category_parent_links": [],
            "item_parent_links": [],
        }
        tmp_yaml_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_yaml_path.write_text(yaml.safe_dump(minimal), encoding="utf-8")

        repo = YAMLRepository(tmp_yaml_path)
        item_id = uuid4()
        assert repo.list_item_relation_links(item_id) == []

    def test_returned_type_is_list_of_item_relation_link(self, tmp_yaml_path: Path) -> None:
        svc = _fresh(tmp_yaml_path)
        src = svc.create_item(name="A")
        tgt = svc.create_item(name="B")
        svc.relate_items(src.item_id, tgt.item_id, "covers")

        svc2 = _fresh(tmp_yaml_path)
        links = svc2.list_item_relations(src.item_id)
        assert all(isinstance(lnk, ItemRelationLink) for lnk in links)


class TestYAMLBatchRelationLookup:
    """Tests for YAMLRepository.list_item_relation_links_for_sources."""

    def test_returns_links_for_multiple_sources(self, tmp_yaml_path: Path) -> None:
        svc = _fresh(tmp_yaml_path)
        a = svc.create_item(name="A")
        b = svc.create_item(name="B")
        c = svc.create_item(name="C")
        t1 = svc.create_item(name="T1")
        t2 = svc.create_item(name="T2")
        svc.relate_items(a.item_id, t1.item_id, "x")
        svc.relate_items(b.item_id, t2.item_id, "y")

        repo = _fresh(tmp_yaml_path)._repo
        links = repo.list_item_relation_links_for_sources([a.item_id, b.item_id])
        assert len(links) == 2
        source_ids = {lnk.source_item_id for lnk in links}
        assert source_ids == {a.item_id, b.item_id}
        assert all(lnk.source_item_id != c.item_id for lnk in links)

    def test_empty_source_ids_returns_empty(self, tmp_yaml_path: Path) -> None:
        repo = YAMLRepository(tmp_yaml_path)
        assert repo.list_item_relation_links_for_sources([]) == []

    def test_filters_by_relation_types(self, tmp_yaml_path: Path) -> None:
        svc = _fresh(tmp_yaml_path)
        src = svc.create_item(name="src")
        t1 = svc.create_item(name="T1")
        t2 = svc.create_item(name="T2")
        svc.relate_items(src.item_id, t1.item_id, "music_by")
        svc.relate_items(src.item_id, t2.item_id, "lyrics_by")

        repo = _fresh(tmp_yaml_path)._repo
        links = repo.list_item_relation_links_for_sources([src.item_id], relation_types=["music_by"])
        assert len(links) == 1
        assert links[0].relation_type == "music_by"

    def test_none_filter_returns_all_types(self, tmp_yaml_path: Path) -> None:
        svc = _fresh(tmp_yaml_path)
        src = svc.create_item(name="src")
        t1 = svc.create_item(name="T1")
        t2 = svc.create_item(name="T2")
        svc.relate_items(src.item_id, t1.item_id, "music_by")
        svc.relate_items(src.item_id, t2.item_id, "lyrics_by")

        repo = _fresh(tmp_yaml_path)._repo
        links = repo.list_item_relation_links_for_sources([src.item_id], relation_types=None)
        assert len(links) == 2

    def test_empty_filter_returns_all_types(self, tmp_yaml_path: Path) -> None:
        svc = _fresh(tmp_yaml_path)
        src = svc.create_item(name="src")
        t1 = svc.create_item(name="T1")
        t2 = svc.create_item(name="T2")
        svc.relate_items(src.item_id, t1.item_id, "music_by")
        svc.relate_items(src.item_id, t2.item_id, "lyrics_by")

        repo = _fresh(tmp_yaml_path)._repo
        links = repo.list_item_relation_links_for_sources([src.item_id], relation_types=[])
        assert len(links) == 2

    def test_ordering(self, tmp_yaml_path: Path) -> None:
        svc = _fresh(tmp_yaml_path)
        src = svc.create_item(name="src")
        t1 = svc.create_item(name="T1")
        t2 = svc.create_item(name="T2")
        svc.relate_items(src.item_id, t1.item_id, "covers", sort_index=5)
        svc.relate_items(src.item_id, t2.item_id, "covers", sort_index=1)

        repo = _fresh(tmp_yaml_path)._repo
        links = repo.list_item_relation_links_for_sources([src.item_id])
        assert links[0].sort_index == 1
        assert links[1].sort_index == 5

    def test_stable_tiebreak_by_target_id(self, tmp_yaml_path: Path) -> None:
        svc = _fresh(tmp_yaml_path)
        src = svc.create_item(name="src")
        t1 = svc.create_item(name="T1")
        t2 = svc.create_item(name="T2")
        svc.relate_items(src.item_id, t1.item_id, "covers", sort_index=0)
        svc.relate_items(src.item_id, t2.item_id, "covers", sort_index=0)

        repo = _fresh(tmp_yaml_path)._repo
        links = repo.list_item_relation_links_for_sources([src.item_id])
        target_ids = [str(lnk.target_item_id) for lnk in links]
        assert target_ids == sorted(target_ids)
