"""Tests for JsonRepository persistence behavior (US5)."""

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import CategoryParentLink
from taxomesh.exceptions import TaxomeshCyclicDependencyError, TaxomeshRepositoryError


def test_json_repository_creates_file_on_init(tmp_json_path: Path) -> None:
    assert not tmp_json_path.exists()
    JsonRepository(tmp_json_path)
    assert tmp_json_path.exists()


def test_json_repository_persistence_across_restart(tmp_json_path: Path) -> None:
    svc1 = TaxomeshService(repository=JsonRepository(tmp_json_path))
    cat = svc1.create_category(name="Persistent")
    item = svc1.create_item(external_id="ext-1")
    tag = svc1.create_tag(name="mytag")
    svc1.assign_tag(tag.tag_id, item.item_id)

    # Simulate a process restart by discarding the first service and repo
    svc2 = TaxomeshService(repository=JsonRepository(tmp_json_path))
    assert svc2.get_category(cat.category_id).name == "Persistent"
    assert svc2.get_item(item.item_id).external_id == "ext-1"


def test_json_repository_flush_after_write(tmp_json_path: Path) -> None:
    repo = JsonRepository(tmp_json_path)
    svc = TaxomeshService(repository=repo)
    cat = svc.create_category(name="Flushed")
    content = json.loads(tmp_json_path.read_text())
    assert str(cat.category_id) in content["categories"]


def test_json_repository_flush_after_delete(tmp_json_path: Path) -> None:
    repo = JsonRepository(tmp_json_path)
    svc = TaxomeshService(repository=repo)
    cat = svc.create_category(name="Gone")
    svc.delete_category(cat.category_id)
    content = json.loads(tmp_json_path.read_text())
    assert str(cat.category_id) not in content["categories"]


def test_json_repository_corrupt_file_raises(tmp_json_path: Path) -> None:
    tmp_json_path.write_text("this is not valid json!!!", encoding="utf-8")
    with pytest.raises(TaxomeshRepositoryError):
        JsonRepository(tmp_json_path)


def test_json_repository_non_object_json_raises(tmp_json_path: Path) -> None:
    tmp_json_path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(TaxomeshRepositoryError):
        JsonRepository(tmp_json_path)


def test_json_repository_directory_path_raises(tmp_path: Path) -> None:
    with pytest.raises(TaxomeshRepositoryError):
        JsonRepository(tmp_path)


def test_service_default_repository_uses_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TaxomeshService() without arguments defaults to YAMLRepository at data/taxomesh.yaml in CWD."""
    monkeypatch.chdir(tmp_path)
    svc = TaxomeshService()
    cat = svc.create_category(name="Default")
    assert (tmp_path / "data" / "taxomesh.yaml").exists()
    assert svc.get_category(cat.category_id).name == "Default"


def test_json_repository_no_temp_files_left_behind(tmp_json_path: Path) -> None:
    repo = JsonRepository(tmp_json_path)
    svc = TaxomeshService(repository=repo)
    svc.create_category(name="Clean")
    svc.create_item(external_id="x")
    tmp_files = list(tmp_json_path.parent.glob("*.tmp"))
    assert tmp_files == []


def test_json_repository_persists_category_parent_links(tmp_json_path: Path) -> None:
    """CategoryParentLink records survive a JsonRepository process restart."""
    svc1 = TaxomeshService(repository=JsonRepository(tmp_json_path))
    cat_a = svc1.create_category(name="A")
    cat_b = svc1.create_category(name="B")
    link = svc1.add_category_parent(cat_a.category_id, cat_b.category_id)

    # Simulate restart
    repo2 = JsonRepository(tmp_json_path)
    svc2 = TaxomeshService(repository=repo2)
    loaded_links = repo2.list_category_parent_links()
    # 3 links: A→root (auto), B→root (auto), A→B (explicit)
    assert len(loaded_links) == 3
    explicit = next(
        lnk
        for lnk in loaded_links
        if lnk.category_id == link.category_id and lnk.parent_category_id == link.parent_category_id
    )
    assert explicit.category_id == link.category_id
    assert explicit.parent_category_id == link.parent_category_id
    # Verify the service can also detect the existing cycle after reload
    with pytest.raises(TaxomeshCyclicDependencyError):
        svc2.add_category_parent(cat_b.category_id, cat_a.category_id)


# ---------------------------------------------------------------------------
# T-04: JsonRepository new methods (delete_tag, save/list item_parent_links)
# ---------------------------------------------------------------------------


def test_delete_tag_removes_it(tmp_json_path: Path) -> None:
    repo = JsonRepository(tmp_json_path)
    svc = TaxomeshService(repository=repo)
    tag = svc.create_tag(name="gone")
    result = repo.delete_tag(tag.tag_id)
    assert result is True
    assert repo.get_tag(tag.tag_id) is None


def test_delete_tag_missing_returns_false(tmp_json_path: Path) -> None:
    repo = JsonRepository(tmp_json_path)
    assert repo.delete_tag(uuid4()) is False


def test_delete_tag_persists_to_file(tmp_json_path: Path) -> None:
    repo = JsonRepository(tmp_json_path)
    svc = TaxomeshService(repository=repo)
    tag = svc.create_tag(name="temp")
    repo.delete_tag(tag.tag_id)
    content = json.loads(tmp_json_path.read_text())
    assert str(tag.tag_id) not in content["tags"]


def test_save_item_parent_link_persists(tmp_json_path: Path) -> None:
    repo = JsonRepository(tmp_json_path)
    svc = TaxomeshService(repository=repo)
    item = svc.create_item(external_id="x")
    cat = svc.create_category(name="C")
    svc.place_item_in_category(item.item_id, cat.category_id)
    content = json.loads(tmp_json_path.read_text())
    assert len(content["item_parent_links"]) == 1


def test_save_item_parent_link_upserts_sort_index(tmp_json_path: Path) -> None:
    repo = JsonRepository(tmp_json_path)
    svc = TaxomeshService(repository=repo)
    item = svc.create_item(external_id="x")
    cat = svc.create_category(name="C")
    svc.place_item_in_category(item.item_id, cat.category_id, sort_index=1)
    svc.place_item_in_category(item.item_id, cat.category_id, sort_index=99)
    links = repo.list_item_parent_links()
    assert len(links) == 1
    assert links[0].sort_index == 99


def test_list_item_parent_links_empty(tmp_json_path: Path) -> None:
    repo = JsonRepository(tmp_json_path)
    assert repo.list_item_parent_links() == []


def test_item_parent_links_survive_restart(tmp_json_path: Path) -> None:
    svc1 = TaxomeshService(repository=JsonRepository(tmp_json_path))
    item = svc1.create_item(external_id="x")
    cat = svc1.create_category(name="C")
    svc1.place_item_in_category(item.item_id, cat.category_id, sort_index=3)
    repo2 = JsonRepository(tmp_json_path)
    links = repo2.list_item_parent_links()
    assert len(links) == 1
    assert links[0].sort_index == 3


def test_legacy_json_without_item_parent_links_loads_empty(tmp_json_path: Path) -> None:
    legacy: dict[str, object] = {
        "categories": {},
        "items": {},
        "tags": {},
        "item_tag_links": [],
        "category_parent_links": [],
    }
    tmp_json_path.write_text(json.dumps(legacy), encoding="utf-8")
    repo = JsonRepository(tmp_json_path)
    assert repo.list_item_parent_links() == []


# ---------------------------------------------------------------------------
# T003: JsonRepository — category-parent upsert (010-unique-parent-links)
# ---------------------------------------------------------------------------


def test_json_save_category_parent_link_upserts_sort_index(tmp_json_path: Path) -> None:
    """Saving the same (category_id, parent_category_id) pair twice updates sort_index."""
    repo = JsonRepository(tmp_json_path)
    cat_id = uuid4()
    parent_id = uuid4()
    repo.save_category_parent_link(CategoryParentLink(category_id=cat_id, parent_category_id=parent_id, sort_index=0))
    repo.save_category_parent_link(CategoryParentLink(category_id=cat_id, parent_category_id=parent_id, sort_index=42))
    links = repo.list_category_parent_links()
    matching = [lnk for lnk in links if lnk.category_id == cat_id and lnk.parent_category_id == parent_id]
    assert len(matching) == 1
    assert matching[0].sort_index == 42


def test_json_save_category_parent_link_upserts_persists(tmp_json_path: Path) -> None:
    """Upserted category-parent link survives a process restart."""
    repo1 = JsonRepository(tmp_json_path)
    cat_id = uuid4()
    parent_id = uuid4()
    repo1.save_category_parent_link(CategoryParentLink(category_id=cat_id, parent_category_id=parent_id, sort_index=0))
    repo1.save_category_parent_link(
        CategoryParentLink(category_id=cat_id, parent_category_id=parent_id, sort_index=10)
    )
    repo2 = JsonRepository(tmp_json_path)
    links = repo2.list_category_parent_links()
    matching = [lnk for lnk in links if lnk.category_id == cat_id and lnk.parent_category_id == parent_id]
    assert len(matching) == 1
    assert matching[0].sort_index == 10


def test_legacy_category_description_null_loads_empty_string(tmp_json_path: Path) -> None:
    cat_id = str(uuid4())
    legacy: dict[str, object] = {
        "categories": {cat_id: {"category_id": cat_id, "name": "X", "description": None, "metadata": {}}},
        "items": {},
        "tags": {},
        "item_tag_links": [],
        "category_parent_links": [],
        "item_parent_links": [],
    }
    tmp_json_path.write_text(json.dumps(legacy), encoding="utf-8")
    repo = JsonRepository(tmp_json_path)
    cat = repo.get_category(UUID(cat_id))
    assert cat is not None
    assert cat.description == ""
