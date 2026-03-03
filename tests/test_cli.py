"""Tests for CLI config loading and CLI commands (004-cli, 005-cli-verbose, 007-yaml-repository)."""

import time
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
import typer.testing

from taxomesh import TaxomeshService
from taxomesh.adapters.cli.config import BuildResult, build
from taxomesh.adapters.cli.main import app
from tests.service.conftest import InMemoryRepository

runner = typer.testing.CliRunner()


def _svc_with_repo(repo: InMemoryRepository) -> TaxomeshService:
    """Return a TaxomeshService backed by the given repo (used for test setup only)."""
    return TaxomeshService(repository=repo)


def _build_result(repo: InMemoryRepository, *, config_file_exists: bool = False) -> BuildResult:
    """Return a BuildResult backed by the given in-memory repo (for use in mocks)."""
    svc = TaxomeshService(repository=repo)
    return BuildResult(
        service=svc,
        repository=repo,
        config_file_path=Path("/fake/taxomesh.toml"),
        config_file_exists=config_file_exists,
    )


# ---------------------------------------------------------------------------
# T-09 / T002: build() / config loading
# ---------------------------------------------------------------------------


def test_build_defaults_when_no_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = build()
    assert isinstance(result.service, TaxomeshService)
    assert (tmp_path / "data" / "taxomesh.yaml").exists()


def test_build_reads_json_path_from_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    custom = tmp_path / "custom.json"
    (tmp_path / "taxomesh.toml").write_text(f'[repository]\ntype = "json"\npath = "{custom}"\n', encoding="utf-8")
    build()
    assert custom.exists()


def test_build_accepts_explicit_config_path(tmp_path: Path) -> None:
    custom_cfg = tmp_path / "other.toml"
    custom_db = tmp_path / "other.json"
    custom_cfg.write_text(f'[repository]\ntype = "json"\npath = "{custom_db}"\n', encoding="utf-8")
    build(config_path=custom_cfg)
    assert custom_db.exists()


def test_build_invalid_toml_exits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "taxomesh.toml").write_text("this is NOT toml !!!", encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        build()
    assert exc_info.value.code != 0


def test_build_unrecognised_repo_type_exits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "taxomesh.toml").write_text('[repository]\ntype = "sqlite"\n', encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        build()
    assert exc_info.value.code != 0


# ---------------------------------------------------------------------------
# T-11: CLI command tests — category
# ---------------------------------------------------------------------------


def test_category_list_empty() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "list"])
    assert result.exit_code == 0


def test_category_add() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "add", "--name", "Music"])
    assert result.exit_code == 0
    # Category.__str__ now returns "(uuid)" format; check a UUID-like string is present
    assert "(" in result.output


def test_category_add_with_description() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "add", "--name", "X", "--description", "Y"])
    assert result.exit_code == 0


def test_category_add_with_parent() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    parent = svc.create_category(name="Parent")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "add", "--name", "Child", "--parent-id", str(parent.category_id)])
    assert result.exit_code == 0


def test_category_add_parent_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "add", "--name", "X", "--parent-id", str(uuid4())])
    assert result.exit_code == 1


def test_category_delete() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="Gone")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "delete", str(cat.category_id)])
    assert result.exit_code == 0


def test_category_delete_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "delete", str(uuid4())])
    assert result.exit_code == 1


def test_category_add_with_slug() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "add", "--name", "Music", "--slug", "music"])
    assert result.exit_code == 0
    assert "music" in result.output


def test_category_update_name() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="Old")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "update", str(cat.category_id), "--name", "New"])
    assert result.exit_code == 0
    # Category.__str__ now returns "(uuid)" format; check UUID is present
    assert str(cat.category_id) in result.output


def test_category_update_slug() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="Old")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "update", str(cat.category_id), "--slug", "old-cat"])
    assert result.exit_code == 0
    assert "old-cat" in result.output


def test_category_update_no_options() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="X")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "update", str(cat.category_id)])
    assert result.exit_code != 0


def test_category_update_add_parent() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    child = svc.create_category(name="Child")
    parent = svc.create_category(name="Parent")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(
            app, ["category", "update", str(child.category_id), "--parent-id", str(parent.category_id)]
        )
    assert result.exit_code == 0


def test_category_cycle_detection() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="Self")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "update", str(cat.category_id), "--parent-id", str(cat.category_id)])
    assert result.exit_code == 1


def test_category_list_with_parent_id() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    parent = svc.create_category(name="P")
    child = svc.create_category(name="Child")
    svc.add_category_parent(child.category_id, parent.category_id)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "list", "--parent-id", str(parent.category_id)])
    assert result.exit_code == 0
    # Category.__str__ now returns "(uuid)" format; check child UUID is in output
    assert str(child.category_id) in result.output


def test_category_list_parent_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "list", "--parent-id", str(uuid4())])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# T-11: CLI command tests — item
# ---------------------------------------------------------------------------


def test_item_list_empty() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "list"])
    assert result.exit_code == 0


def test_item_add_with_slug() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "add", "--external-id", "42", "--slug", "item-42"])
    assert result.exit_code == 0
    assert "item-42" in result.output


def test_item_add_int_external_id() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "add", "--external-id", "42"])
    assert result.exit_code == 0


def test_item_add_str_external_id() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "add", "--external-id", "my-slug"])
    assert result.exit_code == 0


def test_item_add_uuid_external_id() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "add", "--external-id", str(uuid4())])
    assert result.exit_code == 0


def test_item_add_with_category() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="C")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "add", "--external-id", "1", "--category-id", str(cat.category_id)])
    assert result.exit_code == 0


def test_item_add_with_tag() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    tag = svc.create_tag(name="live")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "add", "--external-id", "1", "--tag-id", str(tag.tag_id)])
    assert result.exit_code == 0


def test_item_add_category_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "add", "--external-id", "1", "--category-id", str(uuid4())])
    assert result.exit_code == 1


def test_item_add_without_external_id() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "add", "--name", "no-id-item"])
    assert result.exit_code == 0
    assert "no-id-item" in result.output


def test_item_delete() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(name="x", external_id="x")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "delete", str(item.item_id)])
    assert result.exit_code == 0


def test_item_delete_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "delete", str(uuid4())])
    assert result.exit_code == 1


def test_item_update_slug() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(name="x", external_id="x")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "update", str(item.item_id), "--slug", "my-item"])
    assert result.exit_code == 0
    assert "my-item" in result.output


def test_item_update_disable() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(name="x", external_id="x")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "update", str(item.item_id), "--disable"])
    assert result.exit_code == 0


def test_item_update_no_options() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(name="x", external_id="x")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "update", str(item.item_id)])
    assert result.exit_code != 0


def test_item_update_with_category_id() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(name="x", external_id="x")
    cat = svc.create_category(name="C")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "update", str(item.item_id), "--category-id", str(cat.category_id)])
    assert result.exit_code == 0


def test_item_update_with_tag_id() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(name="x", external_id="x")
    tag = svc.create_tag(name="live")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "update", str(item.item_id), "--tag-id", str(tag.tag_id)])
    assert result.exit_code == 0


def test_item_update_category_not_found() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(name="x", external_id="x")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "update", str(item.item_id), "--category-id", str(uuid4())])
    assert result.exit_code == 1


def test_item_add_to_category() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(name="x", external_id="x")
    cat = svc.create_category(name="C")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(
            app, ["item", "add-to-category", str(item.item_id), "--category-id", str(cat.category_id)]
        )
    assert result.exit_code == 0


def test_item_add_to_category_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "add-to-category", str(uuid4()), "--category-id", str(uuid4())])
    assert result.exit_code == 1


def test_item_add_to_tag() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(name="x", external_id="x")
    tag = svc.create_tag(name="live")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "add-to-tag", str(item.item_id), "--tag-id", str(tag.tag_id)])
    assert result.exit_code == 0


def test_item_add_to_tag_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "add-to-tag", str(uuid4()), "--tag-id", str(uuid4())])
    assert result.exit_code == 1


def test_item_list_with_category_id() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="C")
    item = svc.create_item(name="x", external_id="x")
    svc.place_item_in_category(item.item_id, cat.category_id)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "list", "--category-id", str(cat.category_id)])
    assert result.exit_code == 0


def test_item_list_category_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "list", "--category-id", str(uuid4())])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# T-11: CLI command tests — tag
# ---------------------------------------------------------------------------


def test_tag_list_empty() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["tag", "list"])
    assert result.exit_code == 0


def test_tag_add() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["tag", "add", "--name", "live"])
    assert result.exit_code == 0
    assert "live" in result.output


def test_tag_add_name_too_long() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["tag", "add", "--name", "x" * 26])
    assert result.exit_code == 1


def test_tag_delete() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    tag = svc.create_tag(name="gone")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["tag", "delete", str(tag.tag_id)])
    assert result.exit_code == 0


def test_tag_delete_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["tag", "delete", str(uuid4())])
    assert result.exit_code == 1


def test_tag_update_name() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    tag = svc.create_tag(name="old")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["tag", "update", str(tag.tag_id), "--name", "new"])
    assert result.exit_code == 0
    assert "new" in result.output


# ---------------------------------------------------------------------------
# T007: --verbose flag tests — failing until T008/T009/T010 implement them
# ---------------------------------------------------------------------------


def _verbose_build_result(repo: InMemoryRepository, *, config_file_exists: bool = False) -> BuildResult:
    """Build result with a predictable config_file_path for verbose output assertions."""
    svc = TaxomeshService(repository=repo)
    return BuildResult(
        service=svc,
        repository=repo,
        config_file_path=Path("/test/taxomesh.toml"),
        config_file_exists=config_file_exists,
    )


def test_verbose_flag_prints_block_before_output() -> None:
    repo = InMemoryRepository()
    br = _verbose_build_result(repo)
    with patch("taxomesh.adapters.cli.main.build", return_value=br):
        result = runner.invoke(app, ["--verbose", "category", "list"])
    assert result.exit_code == 0
    lines = result.output.splitlines()
    repo_line = next((i for i, ln in enumerate(lines) if "Repository" in ln), None)
    config_line = next((i for i, ln in enumerate(lines) if "Config" in ln and "file" not in ln.lower()), None)
    file_line = next((i for i, ln in enumerate(lines) if "Config file" in ln), None)
    assert repo_line is not None, "verbose block: Repository line missing"
    assert config_line is not None, "verbose block: Config line missing"
    assert file_line is not None, "verbose block: Config file line missing"
    # verbose block must appear before any list content
    assert repo_line < config_line < file_line


def test_no_verbose_flag_suppresses_block() -> None:
    repo = InMemoryRepository()
    br = _verbose_build_result(repo)
    with patch("taxomesh.adapters.cli.main.build", return_value=br):
        result = runner.invoke(app, ["category", "list"])
    assert result.exit_code == 0
    assert "Repository  :" not in result.output


def test_verbose_shows_config_file_not_found() -> None:
    repo = InMemoryRepository()
    br = _verbose_build_result(repo, config_file_exists=False)
    with patch("taxomesh.adapters.cli.main.build", return_value=br):
        result = runner.invoke(app, ["--verbose", "category", "list"])
    assert result.exit_code == 0
    assert "[not found]" in result.output


def test_verbose_shows_config_file_path_found() -> None:
    repo = InMemoryRepository()
    br = _verbose_build_result(repo, config_file_exists=True)
    with patch("taxomesh.adapters.cli.main.build", return_value=br):
        result = runner.invoke(app, ["--verbose", "category", "list"])
    assert result.exit_code == 0
    assert "[not found]" not in result.output
    assert "/test/taxomesh.toml" in result.output


def test_verbose_block_appears_before_list_header() -> None:
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    svc.create_category(name="Alpha")
    br = BuildResult(
        service=svc,
        repository=repo,
        config_file_path=Path("/test/taxomesh.toml"),
        config_file_exists=False,
    )
    with patch("taxomesh.adapters.cli.main.build", return_value=br):
        result = runner.invoke(app, ["--verbose", "category", "list"])
    assert result.exit_code == 0
    repo_pos = result.output.find("Repository  :")
    header_pos = result.output.find("--- Categories ---")
    assert repo_pos != -1
    assert header_pos != -1
    assert repo_pos < header_pos


def test_verbose_block_appears_even_on_command_error() -> None:
    repo = InMemoryRepository()
    br = _verbose_build_result(repo)
    with patch("taxomesh.adapters.cli.main.build", return_value=br):
        result = runner.invoke(app, ["--verbose", "category", "list", "--parent-id", str(__import__("uuid").uuid4())])
    # command fails (parent not found), but verbose block still printed
    assert result.exit_code == 1
    assert "Repository  :" in result.output


# ---------------------------------------------------------------------------
# T011: list command headers & footers — failing until T012 implements them
# ---------------------------------------------------------------------------


def test_category_list_has_header() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    svc.create_category(name="Rock")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "list"])
    assert result.exit_code == 0
    assert "--- Categories ---" in result.output


def test_category_list_has_footer_with_count() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    svc.create_category(name="Rock")
    svc.create_category(name="Jazz")
    svc.create_category(name="Pop")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "list"])
    assert result.exit_code == 0
    assert "--- Total: 3 ---" in result.output


def test_category_list_empty_footer_is_zero() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "list"])
    assert result.exit_code == 0
    assert "--- Total: 0 ---" in result.output


def test_category_list_header_before_records() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="Rock")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "list"])
    assert result.exit_code == 0
    header_pos = result.output.find("--- Categories ---")
    # Category.__str__ now returns "(uuid)" format; search for the UUID
    uuid_pos = result.output.find(str(cat.category_id))
    assert header_pos != -1
    assert uuid_pos != -1
    assert header_pos < uuid_pos


def test_category_list_footer_after_records() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="Rock")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "list"])
    assert result.exit_code == 0
    uuid_pos = result.output.find(str(cat.category_id))
    footer_pos = result.output.find("--- Total: 1 ---")
    assert uuid_pos != -1
    assert footer_pos != -1
    assert uuid_pos < footer_pos


def test_category_list_filtered_footer_reflects_filter_count() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    parent = svc.create_category(name="Root")
    child1 = svc.create_category(name="Child1")
    child2 = svc.create_category(name="Child2")
    svc.add_category_parent(child1.category_id, parent.category_id)
    svc.add_category_parent(child2.category_id, parent.category_id)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "list", "--parent-id", str(parent.category_id)])
    assert result.exit_code == 0
    # 3 categories total, but only 2 are children of parent
    assert "--- Total: 2 ---" in result.output
    assert "--- Total: 3 ---" not in result.output


def test_category_list_no_footer_on_error() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "list", "--parent-id", str(__import__("uuid").uuid4())])
    assert result.exit_code == 1
    assert "--- Total:" not in result.output


def test_item_list_has_header() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    svc.create_item(name="x", external_id="x")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "list"])
    assert result.exit_code == 0
    assert "--- Items ---" in result.output


def test_item_list_has_footer_with_count() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    svc.create_item(name="x", external_id="x")
    svc.create_item(name="y", external_id="y")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "list"])
    assert result.exit_code == 0
    assert "--- Total: 2 ---" in result.output


def test_item_list_empty_footer_is_zero() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "list"])
    assert result.exit_code == 0
    assert "--- Total: 0 ---" in result.output


def test_item_list_filtered_footer_reflects_filter_count() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="C")
    item_in = svc.create_item(name="in", external_id="in")
    svc.create_item(name="out", external_id="out")
    svc.place_item_in_category(item_in.item_id, cat.category_id)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "list", "--category-id", str(cat.category_id)])
    assert result.exit_code == 0
    # 2 items total, only 1 in category
    assert "--- Total: 1 ---" in result.output
    assert "--- Total: 2 ---" not in result.output


def test_tag_list_has_header() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    svc.create_tag(name="live")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["tag", "list"])
    assert result.exit_code == 0
    assert "--- Tags ---" in result.output


def test_tag_list_has_footer_with_count() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    svc.create_tag(name="live")
    svc.create_tag(name="draft")
    svc.create_tag(name="archived")
    svc.create_tag(name="featured")
    svc.create_tag(name="hidden")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["tag", "list"])
    assert result.exit_code == 0
    assert "--- Total: 5 ---" in result.output


def test_tag_list_empty_footer_is_zero() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["tag", "list"])
    assert result.exit_code == 0
    assert "--- Total: 0 ---" in result.output


# ---------------------------------------------------------------------------
# T004: get_config_summary() — failing until T006 implements it
# ---------------------------------------------------------------------------


def test_json_repo_get_config_summary_contains_path(tmp_path: Path) -> None:
    from taxomesh.adapters.repositories.json_repository import JsonRepository  # noqa: PLC0415

    repo = JsonRepository(tmp_path / "data.json")
    summary = repo.get_config_summary()
    assert isinstance(summary, str)
    assert len(summary) > 0
    assert "data.json" in summary


def test_json_repo_get_config_summary_does_not_raise(tmp_path: Path) -> None:
    from taxomesh.adapters.repositories.json_repository import JsonRepository  # noqa: PLC0415

    repo = JsonRepository(tmp_path / "any.json")
    try:
        repo.get_config_summary()
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"get_config_summary() raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# T001: build() / BuildResult — failing until T002 implements them
# ---------------------------------------------------------------------------


def test_build_returns_build_result_instance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from taxomesh.adapters.cli.config import BuildResult, build  # noqa: PLC0415

    monkeypatch.chdir(tmp_path)
    result = build(None)
    assert isinstance(result, BuildResult)


def test_build_result_service_is_taxomesh_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from taxomesh.adapters.cli.config import build  # noqa: PLC0415

    monkeypatch.chdir(tmp_path)
    result = build(None)
    assert isinstance(result.service, TaxomeshService)


def test_build_result_has_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from taxomesh.adapters.cli.config import build  # noqa: PLC0415

    monkeypatch.chdir(tmp_path)
    result = build(None)
    assert result.repository is not None


def test_build_result_config_file_path_is_absolute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from taxomesh.adapters.cli.config import build  # noqa: PLC0415

    monkeypatch.chdir(tmp_path)
    result = build(None)
    assert result.config_file_path.is_absolute()


def test_build_result_config_file_exists_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from taxomesh.adapters.cli.config import build  # noqa: PLC0415

    monkeypatch.chdir(tmp_path)
    result = build(None)
    assert result.config_file_exists is False


def test_build_result_config_file_exists_true(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from taxomesh.adapters.cli.config import build  # noqa: PLC0415

    monkeypatch.chdir(tmp_path)
    (tmp_path / "taxomesh.toml").write_text('[repository]\ntype = "json"\n', encoding="utf-8")
    result = build(None)
    assert result.config_file_exists is True


# ---------------------------------------------------------------------------
# T005 [US2]: graph CLI command tests — failing until T006 implements graph_cmd
# ---------------------------------------------------------------------------


def test_version_command_prints_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    import taxomesh  # noqa: PLC0415

    assert taxomesh.__version__ in result.output


# ---------------------------------------------------------------------------
# T005 [US2]: graph CLI command tests — failing until T006 implements graph_cmd
# ---------------------------------------------------------------------------


def test_graph_empty_taxonomy_exits_zero() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0


def test_graph_empty_taxonomy_shows_message() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert result.output.strip() != ""


def test_graph_shows_category_name() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    svc.create_category("Animals")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert "Animals" in result.output


def test_graph_shows_category_uuid() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category("Animals")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert str(cat.category_id) in result.output


def test_graph_shows_item_external_id() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category("Animals")
    item = svc.create_item(name="lion", external_id="lion")
    svc.place_item_in_category(item.item_id, cat.category_id)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert "lion" in result.output


def test_graph_shows_item_item_id() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category("Animals")
    item = svc.create_item(name="lion", external_id="lion")
    svc.place_item_in_category(item.item_id, cat.category_id)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert str(item.item_id) in result.output


def test_graph_shows_item_enabled_true() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category("Animals")
    item = svc.create_item(name="lion", external_id="lion")
    svc.place_item_in_category(item.item_id, cat.category_id)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert "✓" in result.output
    assert "enabled=True" not in result.output


def test_graph_shows_item_enabled_false() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category("Animals")
    item = svc.create_item(name="lion", external_id="lion")
    svc.update_item(item.item_id, enabled=False)
    svc.place_item_in_category(item.item_id, cat.category_id)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert "✗" in result.output
    assert "enabled=False" not in result.output


def test_graph_shows_tree_connectors() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    parent = svc.create_category("Animals")
    child = svc.create_category("Mammals")
    svc.add_category_parent(child.category_id, parent.category_id, sort_index=1)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert any(c in result.output for c in ["│", "├", "└", "──"])


def test_graph_nested_category_appears_under_parent() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    parent = svc.create_category("Animals")
    child = svc.create_category("Mammals")
    svc.add_category_parent(child.category_id, parent.category_id, sort_index=1)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert "Mammals" in result.output


def test_graph_no_tag_data_in_output() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category("Animals")
    item = svc.create_item(name="lion", external_id="lion")
    svc.place_item_in_category(item.item_id, cat.category_id)
    tag = svc.create_tag(name="unique-tag-xyzzy")
    svc.assign_tag(tag.tag_id, item.item_id)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert "unique-tag-xyzzy" not in result.output


def test_graph_category_description_not_in_output() -> None:
    """FR-007b: category description MUST NOT appear in graph output; name only."""
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    svc.create_category("Animals", description="unique-description-xyzzy")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert "Animals" in result.output
    assert "unique-description-xyzzy" not in result.output


def test_graph_performance_sc005() -> None:
    """SC-005: graph command completes within 3 s for ≤ 50 categories / 200 items."""
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)

    # Build a taxonomy: 10 top-level categories, each with 4 children = 50 categories
    top_cats = [svc.create_category(f"Top{i}") for i in range(10)]
    all_cats = list(top_cats)
    for parent in top_cats:
        for j in range(4):
            child = svc.create_category(f"Child{parent.category_id.int % 1000}_{j}")
            svc.add_category_parent(child.category_id, parent.category_id, sort_index=j)
            all_cats.append(child)

    # Create 200 items, distribute across leaf categories
    for k in range(200):
        item = svc.create_item(name=f"item-{k}", external_id=f"item-{k}")
        target_cat = all_cats[k % len(all_cats)]
        svc.place_item_in_category(item.item_id, target_cat.category_id, sort_index=k)

    br = _build_result(repo)
    start = time.monotonic()
    with patch("taxomesh.adapters.cli.main.build", return_value=br):
        result = runner.invoke(app, ["graph"])
    elapsed = time.monotonic() - start

    assert result.exit_code == 0
    assert elapsed < 3.0, f"graph took {elapsed:.2f}s — exceeds SC-005 3-second budget"


# ---------------------------------------------------------------------------
# T005 (007-yaml-repository): CLI YAML default + backward compat tests
# ---------------------------------------------------------------------------


def test_cli_default_repo_is_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No taxomesh.toml → CLI falls back to data/taxomesh.yaml (service default)."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["--verbose", "category", "list"])
    assert result.exit_code == 0
    assert "data/taxomesh.yaml" in result.output


def test_cli_toml_type_yaml_uses_yaml_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """taxomesh.toml with type=yaml and custom path → that path is used (FR-005)."""
    monkeypatch.chdir(tmp_path)
    custom = tmp_path / "data.yaml"
    (tmp_path / "taxomesh.toml").write_text(f'[repository]\ntype = "yaml"\npath = "{custom}"\n', encoding="utf-8")
    result = runner.invoke(app, ["--verbose", "category", "list"])
    assert result.exit_code == 0
    assert "data.yaml" in result.output


def test_cli_toml_type_json_backward_compat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """taxomesh.toml with type=json → legacy.json is used, no YAML created (FR-006, SC-005)."""
    monkeypatch.chdir(tmp_path)
    legacy = tmp_path / "legacy.json"
    (tmp_path / "taxomesh.toml").write_text(f'[repository]\ntype = "json"\npath = "{legacy}"\n', encoding="utf-8")
    result = runner.invoke(app, ["--verbose", "category", "list"])
    assert result.exit_code == 0
    assert "legacy.json" in result.output
    assert legacy.exists()


def test_cli_toml_type_unsupported_exits_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """taxomesh.toml with type=csv → exit code 1 and descriptive error (FR-005)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "taxomesh.toml").write_text('[repository]\ntype = "csv"\n', encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        build(config_path=tmp_path / "taxomesh.toml")
    assert exc_info.value.code != 0


def test_cli_uses_yaml_when_configured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """taxomesh.toml with type=yaml → CLI creates data/taxomesh.yaml, not taxomesh.json."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "taxomesh.toml").write_text('[repository]\ntype = "yaml"\n', encoding="utf-8")

    result = runner.invoke(app, ["category", "list"])
    assert result.exit_code == 0

    assert (tmp_path / "data" / "taxomesh.yaml").exists()
    assert not (tmp_path / "taxomesh.json").exists()


def test_cli_leaves_json_untouched_when_yaml_is_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing taxomesh.json is not modified when CLI defaults to YAML (FR-013)."""
    monkeypatch.chdir(tmp_path)
    json_file = tmp_path / "taxomesh.json"
    json_file.write_text(
        '{"categories":{},"items":{},"tags":{},"item_tag_links":[],"category_parent_links":[],"item_parent_links":[]}',
        encoding="utf-8",
    )
    original_content = json_file.read_text(encoding="utf-8")

    result = runner.invoke(app, ["category", "list"])
    assert result.exit_code == 0

    # JSON file must be unchanged
    assert json_file.read_text(encoding="utf-8") == original_content
    # YAML file must have been created instead
    assert (tmp_path / "data" / "taxomesh.yaml").exists()
