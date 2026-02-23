"""Tests for CLI config loading and CLI commands (004-cli)."""

from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
import typer.testing

from taxomesh import TaxomeshService
from taxomesh.adapters.cli.config import build_service
from taxomesh.adapters.cli.main import app
from tests.service.conftest import InMemoryRepository

runner = typer.testing.CliRunner()


def _svc_with_repo(repo: InMemoryRepository) -> TaxomeshService:
    """Return a TaxomeshService backed by the given repo."""
    return TaxomeshService(repository=repo)


# ---------------------------------------------------------------------------
# T-09: build_service / config loading
# ---------------------------------------------------------------------------


def test_build_service_defaults_when_no_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    svc = build_service()
    assert isinstance(svc, TaxomeshService)
    assert (tmp_path / "taxomesh.json").exists()


def test_build_service_reads_json_path_from_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    custom = tmp_path / "custom.json"
    (tmp_path / "taxomesh.toml").write_text(f'[repository]\ntype = "json"\npath = "{custom}"\n', encoding="utf-8")
    build_service()
    assert custom.exists()


def test_build_service_accepts_explicit_config_path(tmp_path: Path) -> None:
    custom_cfg = tmp_path / "other.toml"
    custom_db = tmp_path / "other.json"
    custom_cfg.write_text(f'[repository]\ntype = "json"\npath = "{custom_db}"\n', encoding="utf-8")
    build_service(config_path=custom_cfg)
    assert custom_db.exists()


def test_build_service_invalid_toml_exits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "taxomesh.toml").write_text("this is NOT toml !!!", encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        build_service()
    assert exc_info.value.code != 0


def test_build_service_unrecognised_repo_type_exits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "taxomesh.toml").write_text('[repository]\ntype = "sqlite"\n', encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        build_service()
    assert exc_info.value.code != 0


# ---------------------------------------------------------------------------
# T-11: CLI command tests — category
# ---------------------------------------------------------------------------


def test_category_list_empty() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["category", "list"])
    assert result.exit_code == 0


def test_category_add() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["category", "add", "--name", "Music"])
    assert result.exit_code == 0
    assert "Music" in result.output


def test_category_add_with_description() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["category", "add", "--name", "X", "--description", "Y"])
    assert result.exit_code == 0


def test_category_add_with_parent() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    parent = svc.create_category(name="Parent")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["category", "add", "--name", "Child", "--parent-id", str(parent.category_id)])
    assert result.exit_code == 0


def test_category_add_parent_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["category", "add", "--name", "X", "--parent-id", str(uuid4())])
    assert result.exit_code == 1


def test_category_delete() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="Gone")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["category", "delete", str(cat.category_id)])
    assert result.exit_code == 0


def test_category_delete_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["category", "delete", str(uuid4())])
    assert result.exit_code == 1


def test_category_update_name() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="Old")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["category", "update", str(cat.category_id), "--name", "New"])
    assert result.exit_code == 0
    assert "New" in result.output


def test_category_update_no_options() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="X")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["category", "update", str(cat.category_id)])
    assert result.exit_code != 0


def test_category_update_add_parent() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    child = svc.create_category(name="Child")
    parent = svc.create_category(name="Parent")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(
            app, ["category", "update", str(child.category_id), "--parent-id", str(parent.category_id)]
        )
    assert result.exit_code == 0


def test_category_cycle_detection() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="Self")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["category", "update", str(cat.category_id), "--parent-id", str(cat.category_id)])
    assert result.exit_code == 1


def test_category_list_with_parent_id() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    parent = svc.create_category(name="P")
    child = svc.create_category(name="Child")
    svc.add_category_parent(child.category_id, parent.category_id)
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["category", "list", "--parent-id", str(parent.category_id)])
    assert result.exit_code == 0
    assert "Child" in result.output


def test_category_list_parent_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["category", "list", "--parent-id", str(uuid4())])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# T-11: CLI command tests — item
# ---------------------------------------------------------------------------


def test_item_list_empty() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "list"])
    assert result.exit_code == 0


def test_item_add_int_external_id() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "add", "--external-id", "42"])
    assert result.exit_code == 0


def test_item_add_str_external_id() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "add", "--external-id", "my-slug"])
    assert result.exit_code == 0


def test_item_add_uuid_external_id() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "add", "--external-id", str(uuid4())])
    assert result.exit_code == 0


def test_item_add_with_category() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="C")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "add", "--external-id", "1", "--category-id", str(cat.category_id)])
    assert result.exit_code == 0


def test_item_add_with_tag() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    tag = svc.create_tag(name="live")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "add", "--external-id", "1", "--tag-id", str(tag.tag_id)])
    assert result.exit_code == 0


def test_item_add_category_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "add", "--external-id", "1", "--category-id", str(uuid4())])
    assert result.exit_code == 1


def test_item_delete() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(external_id="x")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "delete", str(item.item_id)])
    assert result.exit_code == 0


def test_item_delete_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "delete", str(uuid4())])
    assert result.exit_code == 1


def test_item_update_disable() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(external_id="x")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "update", str(item.item_id), "--disable"])
    assert result.exit_code == 0


def test_item_update_no_options() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(external_id="x")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "update", str(item.item_id)])
    assert result.exit_code != 0


def test_item_update_with_category_id() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(external_id="x")
    cat = svc.create_category(name="C")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "update", str(item.item_id), "--category-id", str(cat.category_id)])
    assert result.exit_code == 0


def test_item_update_with_tag_id() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(external_id="x")
    tag = svc.create_tag(name="live")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "update", str(item.item_id), "--tag-id", str(tag.tag_id)])
    assert result.exit_code == 0


def test_item_update_category_not_found() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(external_id="x")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "update", str(item.item_id), "--category-id", str(uuid4())])
    assert result.exit_code == 1


def test_item_add_to_category() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(external_id="x")
    cat = svc.create_category(name="C")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(
            app, ["item", "add-to-category", str(item.item_id), "--category-id", str(cat.category_id)]
        )
    assert result.exit_code == 0


def test_item_add_to_category_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "add-to-category", str(uuid4()), "--category-id", str(uuid4())])
    assert result.exit_code == 1


def test_item_add_to_tag() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(external_id="x")
    tag = svc.create_tag(name="live")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "add-to-tag", str(item.item_id), "--tag-id", str(tag.tag_id)])
    assert result.exit_code == 0


def test_item_add_to_tag_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "add-to-tag", str(uuid4()), "--tag-id", str(uuid4())])
    assert result.exit_code == 1


def test_item_list_with_category_id() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="C")
    item = svc.create_item(external_id="x")
    svc.place_item_in_category(item.item_id, cat.category_id)
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "list", "--category-id", str(cat.category_id)])
    assert result.exit_code == 0


def test_item_list_category_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "list", "--category-id", str(uuid4())])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# T-11: CLI command tests — tag
# ---------------------------------------------------------------------------


def test_tag_list_empty() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["tag", "list"])
    assert result.exit_code == 0


def test_tag_add() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["tag", "add", "--name", "live"])
    assert result.exit_code == 0
    assert "live" in result.output


def test_tag_add_name_too_long() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["tag", "add", "--name", "x" * 26])
    assert result.exit_code == 1


def test_tag_delete() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    tag = svc.create_tag(name="gone")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["tag", "delete", str(tag.tag_id)])
    assert result.exit_code == 0


def test_tag_delete_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["tag", "delete", str(uuid4())])
    assert result.exit_code == 1


def test_tag_update_name() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    tag = svc.create_tag(name="old")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["tag", "update", str(tag.tag_id), "--name", "new"])
    assert result.exit_code == 0
    assert "new" in result.output
