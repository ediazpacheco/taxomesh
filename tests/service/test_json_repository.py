"""Tests for JsonRepository persistence behavior (US5)."""

import json
from pathlib import Path

import pytest

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.application.service import TaxomeshService
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


def test_service_default_repository_uses_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TaxomeshService() without arguments defaults to JsonRepository at taxomesh.json in CWD."""
    monkeypatch.chdir(tmp_path)
    svc = TaxomeshService()
    cat = svc.create_category(name="Default")
    assert (tmp_path / "taxomesh.json").exists()
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
    assert len(loaded_links) == 1
    assert loaded_links[0].category_id == link.category_id
    assert loaded_links[0].parent_category_id == link.parent_category_id
    # Verify the service can also detect the existing cycle after reload
    with pytest.raises(TaxomeshCyclicDependencyError):
        svc2.add_category_parent(cat_b.category_id, cat_a.category_id)
