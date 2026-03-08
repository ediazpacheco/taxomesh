"""Persistence round-trip tests for ItemRelationLink in JsonRepository (US5)."""

import json
from pathlib import Path
from uuid import uuid4

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import ItemRelationLink


def _fresh(path: Path) -> TaxomeshService:
    """Return a new TaxomeshService backed by a fresh load of the JSON file."""
    return TaxomeshService(repository=JsonRepository(path))


class TestJsonRelationRoundTrip:
    """All five fields survive a save → reload cycle."""

    def test_all_fields_survive_reload(self, tmp_json_path: Path) -> None:
        svc = _fresh(tmp_json_path)
        src = svc.create_item(name="A")
        tgt = svc.create_item(name="B")
        svc.relate_items(src.item_id, tgt.item_id, "covers", sort_index=7, metadata={"k": "v"})

        svc2 = _fresh(tmp_json_path)
        links = svc2.list_item_relations(src.item_id)
        assert len(links) == 1
        lnk = links[0]
        assert lnk.source_item_id == src.item_id
        assert lnk.target_item_id == tgt.item_id
        assert lnk.relation_type == "covers"
        assert lnk.sort_index == 7
        assert lnk.metadata == {"k": "v"}

    def test_multiple_relations_survive_reload(self, tmp_json_path: Path) -> None:
        svc = _fresh(tmp_json_path)
        a = svc.create_item(name="A")
        b = svc.create_item(name="B")
        c = svc.create_item(name="C")
        svc.relate_items(a.item_id, b.item_id, "covers")
        svc.relate_items(a.item_id, c.item_id, "samples")

        svc2 = _fresh(tmp_json_path)
        links = svc2.list_item_relations(a.item_id)
        assert len(links) == 2
        types = {lnk.relation_type for lnk in links}
        assert types == {"covers", "samples"}

    def test_upsert_survives_reload(self, tmp_json_path: Path) -> None:
        svc = _fresh(tmp_json_path)
        src = svc.create_item(name="A")
        tgt = svc.create_item(name="B")
        svc.relate_items(src.item_id, tgt.item_id, "covers", sort_index=1)
        svc.relate_items(src.item_id, tgt.item_id, "covers", sort_index=9, metadata={"updated": True})

        svc2 = _fresh(tmp_json_path)
        links = svc2.list_item_relations(src.item_id)
        assert len(links) == 1
        assert links[0].sort_index == 9
        assert links[0].metadata == {"updated": True}

    def test_relation_written_to_json_file(self, tmp_json_path: Path) -> None:
        svc = _fresh(tmp_json_path)
        src = svc.create_item(name="A")
        tgt = svc.create_item(name="B")
        svc.relate_items(src.item_id, tgt.item_id, "covers")

        raw = json.loads(tmp_json_path.read_text())
        assert "item_relation_links" in raw
        assert len(raw["item_relation_links"]) == 1
        assert raw["item_relation_links"][0]["relation_type"] == "covers"

    def test_cascade_delete_survives_reload(self, tmp_json_path: Path) -> None:
        svc = _fresh(tmp_json_path)
        src = svc.create_item(name="A")
        tgt = svc.create_item(name="B")
        svc.relate_items(src.item_id, tgt.item_id, "covers")
        svc.delete_item(src.item_id)

        svc2 = _fresh(tmp_json_path)
        links = svc2.list_item_relations(tgt.item_id, direction="incoming")
        assert links == []


class TestJsonBackwardCompat:
    """Files without 'item_relation_links' key load as empty list."""

    def test_missing_key_loads_as_empty(self, tmp_json_path: Path) -> None:
        # Write a minimal valid JSON file without the item_relation_links key
        minimal: dict[str, object] = {
            "categories": {},
            "items": {},
            "tags": {},
            "item_tag_links": [],
            "category_parent_links": [],
            "item_parent_links": [],
        }
        tmp_json_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_json_path.write_text(json.dumps(minimal), encoding="utf-8")

        repo = JsonRepository(tmp_json_path)
        # Should not raise; item_relation_links treated as empty
        item_id = uuid4()
        assert repo.list_item_relation_links(item_id) == []

    def test_returned_type_is_list_of_item_relation_link(self, tmp_json_path: Path) -> None:
        svc = _fresh(tmp_json_path)
        src = svc.create_item(name="A")
        tgt = svc.create_item(name="B")
        svc.relate_items(src.item_id, tgt.item_id, "covers")

        svc2 = _fresh(tmp_json_path)
        links = svc2.list_item_relations(src.item_id)
        assert all(isinstance(lnk, ItemRelationLink) for lnk in links)
