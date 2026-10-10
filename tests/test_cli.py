"""Tests for CLI config loading and CLI commands."""

import inspect
import time
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import click
import pytest
import typer.main
import typer.testing

from taxomesh import TaxomeshService
from taxomesh.adapters.cli.config import BuildResult, build
from taxomesh.adapters.cli.main import app
from taxomesh.application.collections.categories import CategoryCollection
from taxomesh.application.collections.items import ItemCollection
from taxomesh.application.collections.tags import TagCollection
from taxomesh.domain.constants import MAX_TAG_NAME_LENGTH
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
# build() and config loading
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


def test_category_create() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "create", "--name", "Music"])
    assert result.exit_code == 0
    # Category.__str__ ends in "(uuid)"; check a UUID-like string is present
    assert "(" in result.output


def test_category_create_with_description() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "create", "--name", "X", "--description", "Y"])
    assert result.exit_code == 0


def test_category_add_parent() -> None:
    """The parent link is stored, and the child leaves the top level."""
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    parent = svc.categories.create(name="Parent")
    child = svc.categories.create(name="Child")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(
            app, ["category", "add-parent", str(child.category_id), "--parent-id", str(parent.category_id)]
        )
    assert result.exit_code == 0
    assert result.output.splitlines() == [
        f"Added parent {parent.category_id} to category {child.category_id} at sort index 0"
    ]
    assert [c.name for c in _svc_with_repo(repo).categories.list(parent=parent)] == ["Child"]


def test_category_add_parent_not_found() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    child = svc.categories.create(name="Child")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "add-parent", str(child.category_id), "--parent-id", str(uuid4())])
    assert result.exit_code == 1


def test_category_delete() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.categories.create(name="Gone")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "delete", str(cat.category_id)])
    assert result.exit_code == 0


def test_category_delete_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "delete", str(uuid4())])
    assert result.exit_code == 1


def test_category_create_with_slug() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "create", "--name", "Music", "--slug", "music"])
    assert result.exit_code == 0
    assert "music" in result.output


def test_category_update_name() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.categories.create(name="Old")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "update", str(cat.category_id), "--name", "New"])
    assert result.exit_code == 0
    # Category.__str__ ends in "(uuid)"; check the UUID is present
    assert str(cat.category_id) in result.output


def test_category_update_slug() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.categories.create(name="Old")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "update", str(cat.category_id), "--slug", "old-cat"])
    assert result.exit_code == 0
    assert "old-cat" in result.output


def test_category_update_no_options() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.categories.create(name="X")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "update", str(cat.category_id)])
    assert result.exit_code != 0
    assert result.output.splitlines() == [
        "At least one of --name, --description, --slug or --enable/--disable is required"
    ]


@pytest.mark.parametrize(("flag", "enabled"), [("--disable", False), ("--enable", True)])
def test_category_update_sets_enabled(flag: str, enabled: bool) -> None:
    """``--enable`` and ``--disable`` set the field, as they do on ``item update``."""
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.categories.create(name="X")
    svc.categories.update(cat, enabled=not enabled)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "update", str(cat.category_id), flag])
    assert result.exit_code == 0
    assert _svc_with_repo(repo).categories[cat.category_id].enabled is enabled


def test_category_remove_parent() -> None:
    """The parent link must actually be gone.

    ``remove_parent`` is a no-op when the link does not exist, so exit 0 on its own is also what
    a command that added the parent would return.
    """
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    child = svc.categories.create(name="Child")
    parent = svc.categories.create(name="Parent")
    svc.categories.add_parent(child.category_id, parent.category_id)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(
            app, ["category", "remove-parent", str(child.category_id), "--parent-id", str(parent.category_id)]
        )
    assert result.exit_code == 0
    links = repo.list_category_parent_links(category_ids=[child.category_id])
    assert [lnk for lnk in links if lnk.parent_category_id == parent.category_id] == []


def test_category_remove_parent_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "remove-parent", str(uuid4()), "--parent-id", str(uuid4())])
    assert result.exit_code == 1


def test_category_cycle_detection() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.categories.create(name="Self")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(
            app, ["category", "add-parent", str(cat.category_id), "--parent-id", str(cat.category_id)]
        )
    assert result.exit_code == 1


def test_category_list_with_parent_id() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    parent = svc.categories.create(name="P")
    child = svc.categories.create(name="Child")
    svc.categories.add_parent(child.category_id, parent.category_id)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "list", "--parent-id", str(parent.category_id)])
    assert result.exit_code == 0
    # Category.__str__ ends in "(uuid)"; check the child's UUID is in the output
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


def test_item_create_with_slug() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "create", "--name", "Item", "--external-id", "42", "--slug", "item-42"])
    assert result.exit_code == 0
    assert "item-42" in result.output


def test_item_create_int_external_id() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "create", "--name", "Item", "--external-id", "42"])
    assert result.exit_code == 0


def test_item_create_str_external_id() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "create", "--name", "Item", "--external-id", "my-slug"])
    assert result.exit_code == 0


def test_item_create_uuid_external_id() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "create", "--name", "Item", "--external-id", str(uuid4())])
    assert result.exit_code == 0


def test_item_create_without_external_id() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "create", "--name", "no-id-item"])
    assert result.exit_code == 0
    assert "no-id-item" in result.output


def test_item_create_requires_a_name() -> None:
    """``--name`` is required, as it is on ``category create`` and ``tag create``.

    ``Item.name`` is required: supplied, not necessarily non-empty. Left out, the option is
    refused rather than stored as ``""``; ``--name ""`` stores an empty name explicitly.
    """
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "create", "--external-id", "kind-of-blue"])
    assert result.exit_code == 2
    assert "--name" in click.unstyle(result.output)
    assert repo.list_items(enabled=None) == []


def test_item_delete() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.items.create(name="x", external_id="x")
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
    item = svc.items.create(name="x", external_id="x")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "update", str(item.item_id), "--slug", "my-item"])
    assert result.exit_code == 0
    assert "my-item" in result.output


def test_item_update_disable() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.items.create(name="x", external_id="x")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "update", str(item.item_id), "--disable"])
    assert result.exit_code == 0


def test_item_update_no_options() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.items.create(name="x", external_id="x")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "update", str(item.item_id)])
    assert result.exit_code != 0
    assert result.output.splitlines() == ["At least one of --name, --slug or --enable/--disable is required"]


def test_item_place_in() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.items.create(name="x", external_id="x")
    cat = svc.categories.create(name="C")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "place-in", str(item.item_id), "--category-id", str(cat.category_id)])
    assert result.exit_code == 0
    assert result.output.splitlines() == [f"Placed item {item.item_id} in category {cat.category_id} at sort index 0"]


def test_item_place_in_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "place-in", str(uuid4()), "--category-id", str(uuid4())])
    assert result.exit_code == 1


def test_item_tag() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.items.create(name="x", external_id="x")
    tag = svc.tags.create(name="live")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "tag", str(item.item_id), "--tag-id", str(tag.tag_id)])
    assert result.exit_code == 0
    assert result.output.splitlines() == [f"Added tag {tag.tag_id} to item {item.item_id}"]


def test_item_tag_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "tag", str(uuid4()), "--tag-id", str(uuid4())])
    assert result.exit_code == 1


def test_item_untag() -> None:
    """The link must actually be gone.

    Asserting the exit code alone would pass on a command that tagged instead of untagging,
    which is one word's difference from the body above, so the item's tags are read back.
    """
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.items.create(name="x", external_id="x")
    tag = svc.tags.create(name="live")
    svc.items.tag(item.item_id, tag.tag_id)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "untag", str(item.item_id), "--tag-id", str(tag.tag_id)])
    assert result.exit_code == 0
    assert _svc_with_repo(repo).tags.list(item=item) == ()


def test_item_untag_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "untag", str(uuid4()), "--tag-id", str(uuid4())])
    assert result.exit_code == 1


def test_item_remove_from() -> None:
    """The placement must actually be gone.

    ``remove_from`` is a no-op when the item is not in the category, so exit 0 on its own is
    also what a command that placed the item would return.
    """
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.items.create(name="x", external_id="x")
    cat = svc.categories.create(name="C")
    svc.items.place_in(item.item_id, cat.category_id)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "remove-from", str(item.item_id), "--category-id", str(cat.category_id)])
    assert result.exit_code == 0
    assert [lnk for lnk in repo.list_item_parent_links() if lnk.item_id == item.item_id] == []


def test_item_remove_from_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "remove-from", str(uuid4()), "--category-id", str(uuid4())])
    assert result.exit_code == 1


def test_each_group_has_help() -> None:
    """``taxomesh --help`` describes each group of commands, as it describes each command."""
    described = {
        group.name: group.typer_instance is not None and bool(group.typer_instance.info.help)
        for group in app.registered_groups
    }
    assert described == {"category": True, "item": True, "tag": True}


def test_the_tag_name_help_gives_the_limit() -> None:
    """The limit in the help is the model's, so the two cannot differ."""
    result = runner.invoke(app, ["tag", "create", "--help"])
    assert result.exit_code == 0
    assert f"at most {MAX_TAG_NAME_LENGTH} characters" in result.output


@pytest.mark.parametrize(
    ("command", "summary"),
    [
        (["category", "remove-parent"], "Remove one parent from a category"),
        (["item", "untag"], "Remove a tag from an item"),
        (["item", "remove-from"], "Remove an item from one category"),
    ],
    ids=["category-remove-parent", "item-untag", "item-remove-from"],
)
def test_help_ends_at_the_summary(command: list[str], summary: str) -> None:
    """``--help`` shows a command's summary and not the ``Args:`` block its docstring carries.

    Typer prints the whole docstring as help unless a form feed marks where the help ends, so
    the notes written for readers of the code, ``ctx`` among them, reached the terminal. Each
    option carries its own help string.
    """
    result = runner.invoke(app, [*command, "--help"])

    assert result.exit_code == 0
    assert summary in result.output
    assert "Args:" not in result.output
    assert "Typer context" not in result.output


def test_item_list_with_category_id() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.categories.create(name="C")
    item = svc.items.create(name="x", external_id="x")
    svc.items.place_in(item.item_id, cat.category_id)
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


def test_tag_create() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["tag", "create", "--name", "live"])
    assert result.exit_code == 0
    assert "live" in result.output


def test_tag_create_name_too_long() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["tag", "create", "--name", "x" * 26])
    assert result.exit_code == 1


def test_tag_delete() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    tag = svc.tags.create(name="gone")
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
    tag = svc.tags.create(name="old")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["tag", "update", str(tag.tag_id), "--name", "new"])
    assert result.exit_code == 0
    assert "new" in result.output


def test_tag_update_no_options() -> None:
    """``--name`` is optional, as on the other updates, and leaving every option off is refused."""
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    tag = svc.tags.create(name="old")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["tag", "update", str(tag.tag_id)])
    assert result.exit_code == 1
    assert result.output.splitlines() == ["--name is required"]
    assert repo.find_tag(tag.tag_id) == tag


# ---------------------------------------------------------------------------
# --verbose
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
    svc.categories.create(name="Alpha")
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
# List command headers and footers
# ---------------------------------------------------------------------------


def test_category_list_has_header() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    svc.categories.create(name="Rock")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "list"])
    assert result.exit_code == 0
    assert "--- Categories ---" in result.output


def test_category_list_has_footer_with_count() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    svc.categories.create(name="Rock")
    svc.categories.create(name="Jazz")
    svc.categories.create(name="Pop")
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
    cat = svc.categories.create(name="Rock")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "list"])
    assert result.exit_code == 0
    header_pos = result.output.find("--- Categories ---")
    # Category.__str__ ends in "(uuid)"; search for the UUID
    uuid_pos = result.output.find(str(cat.category_id))
    assert header_pos != -1
    assert uuid_pos != -1
    assert header_pos < uuid_pos


def test_category_list_footer_after_records() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.categories.create(name="Rock")
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
    parent = svc.categories.create(name="Root")
    child1 = svc.categories.create(name="Child1")
    child2 = svc.categories.create(name="Child2")
    svc.categories.add_parent(child1.category_id, parent.category_id)
    svc.categories.add_parent(child2.category_id, parent.category_id)
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
    svc.items.create(name="x", external_id="x")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "list"])
    assert result.exit_code == 0
    assert "--- Items ---" in result.output


def test_item_list_has_footer_with_count() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    svc.items.create(name="x", external_id="x")
    svc.items.create(name="y", external_id="y")
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
    cat = svc.categories.create(name="C")
    item_in = svc.items.create(name="in", external_id="in")
    svc.items.create(name="out", external_id="out")
    svc.items.place_in(item_in.item_id, cat.category_id)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "list", "--category-id", str(cat.category_id)])
    assert result.exit_code == 0
    # 2 items total, only 1 in category
    assert "--- Total: 1 ---" in result.output
    assert "--- Total: 2 ---" not in result.output


def test_tag_list_has_header() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    svc.tags.create(name="live")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["tag", "list"])
    assert result.exit_code == 0
    assert "--- Tags ---" in result.output


def test_tag_list_has_footer_with_count() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    svc.tags.create(name="live")
    svc.tags.create(name="draft")
    svc.tags.create(name="archived")
    svc.tags.create(name="featured")
    svc.tags.create(name="hidden")
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
# config_summary
# ---------------------------------------------------------------------------


def test_json_repo_config_summary_contains_path(tmp_path: Path) -> None:
    from taxomesh.adapters.repositories.json_repository import JsonRepository  # noqa: PLC0415

    repo = JsonRepository(tmp_path / "data.json")
    summary = repo.config_summary
    assert isinstance(summary, str)
    assert len(summary) > 0
    assert "data.json" in summary


def test_json_repo_config_summary_does_not_raise(tmp_path: Path) -> None:
    from taxomesh.adapters.repositories.json_repository import JsonRepository  # noqa: PLC0415

    repo = JsonRepository(tmp_path / "any.json")
    try:
        _ = repo.config_summary
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"config_summary raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# build() and BuildResult
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
# version
# ---------------------------------------------------------------------------


def test_version_command_prints_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    import taxomesh  # noqa: PLC0415

    assert taxomesh.__version__ in result.output


# ---------------------------------------------------------------------------
# graph
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
    assert result.output.splitlines() == ["No categories found. Add one with: taxomesh category create --name <name>"]


def test_graph_shows_category_name() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    svc.categories.create("Animals")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert "Animals" in result.output


def test_graph_shows_category_uuid() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.categories.create("Animals")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert str(cat.category_id) in result.output


def test_graph_shows_item_external_id() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.categories.create("Animals")
    item = svc.items.create(name="lion", external_id="lion")
    svc.items.place_in(item.item_id, cat.category_id)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert "lion" in result.output


def test_graph_shows_item_item_id() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.categories.create("Animals")
    item = svc.items.create(name="lion", external_id="lion")
    svc.items.place_in(item.item_id, cat.category_id)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert str(item.item_id) in result.output


def test_graph_shows_item_enabled_true() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.categories.create("Animals")
    item = svc.items.create(name="lion", external_id="lion")
    svc.items.place_in(item.item_id, cat.category_id)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert "✓" in result.output
    assert "enabled=True" not in result.output


def test_graph_shows_item_enabled_false() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.categories.create("Animals")
    item = svc.items.create(name="lion", external_id="lion")
    svc.items.update(item.item_id, enabled=False)
    svc.items.place_in(item.item_id, cat.category_id)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph", "--state", "all"])
    assert result.exit_code == 0
    assert "✗" in result.output
    assert "enabled=False" not in result.output


def test_graph_shows_tree_connectors() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    parent = svc.categories.create("Animals")
    child = svc.categories.create("Mammals")
    svc.categories.add_parent(child.category_id, parent.category_id, sort_index=1)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert any(c in result.output for c in ["│", "├", "└", "──"])


def test_graph_nested_category_appears_under_parent() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    parent = svc.categories.create("Animals")
    child = svc.categories.create("Mammals")
    svc.categories.add_parent(child.category_id, parent.category_id, sort_index=1)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert "Mammals" in result.output


def test_graph_no_tag_data_in_output() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.categories.create("Animals")
    item = svc.items.create(name="lion", external_id="lion")
    svc.items.place_in(item.item_id, cat.category_id)
    tag = svc.tags.create(name="unique-tag-xyzzy")
    svc.items.tag(item.item_id, tag.tag_id)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert "unique-tag-xyzzy" not in result.output


def test_graph_category_description_not_in_output() -> None:
    """Category description MUST NOT appear in graph output; name only."""
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    svc.categories.create("Animals", description="unique-description-xyzzy")
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert "Animals" in result.output
    assert "unique-description-xyzzy" not in result.output


def test_graph_performance_sc005() -> None:
    """Graph command completes within 3 s for ≤ 50 categories / 200 items."""
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)

    # Build a taxonomy: 10 top-level categories, each with 4 children = 50 categories
    top_cats = [svc.categories.create(f"Top{i}") for i in range(10)]
    all_cats = list(top_cats)
    for parent in top_cats:
        for j in range(4):
            child = svc.categories.create(f"Child{parent.category_id.int % 1000}_{j}")
            svc.categories.add_parent(child.category_id, parent.category_id, sort_index=j)
            all_cats.append(child)

    # Create 200 items, distribute across leaf categories
    for k in range(200):
        item = svc.items.create(name=f"item-{k}", external_id=f"item-{k}")
        target_cat = all_cats[k % len(all_cats)]
        svc.items.place_in(item.item_id, target_cat.category_id, sort_index=k)

    br = _build_result(repo)
    start = time.monotonic()
    with patch("taxomesh.adapters.cli.main.build", return_value=br):
        result = runner.invoke(app, ["graph"])
    elapsed = time.monotonic() - start

    assert result.exit_code == 0
    assert elapsed < 3.0, f"graph took {elapsed:.2f}s — exceeds its 3-second budget"


# ---------------------------------------------------------------------------
# The CLI's default store, and a configured JSON store
# ---------------------------------------------------------------------------


def test_cli_default_repo_is_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No taxomesh.toml → CLI falls back to data/taxomesh.yaml (service default)."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["--verbose", "category", "list"])
    assert result.exit_code == 0
    assert "data/taxomesh.yaml" in result.output


def test_cli_toml_type_yaml_uses_yaml_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """taxomesh.toml with type=yaml and custom path → that path is used."""
    monkeypatch.chdir(tmp_path)
    custom = tmp_path / "data.yaml"
    (tmp_path / "taxomesh.toml").write_text(f'[repository]\ntype = "yaml"\npath = "{custom}"\n', encoding="utf-8")
    result = runner.invoke(app, ["--verbose", "category", "list"])
    assert result.exit_code == 0
    assert "data.yaml" in result.output


def test_cli_toml_type_json_uses_the_json_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """taxomesh.toml with type=json → that JSON file is used, and no YAML file is created."""
    monkeypatch.chdir(tmp_path)
    store = tmp_path / "store.json"
    (tmp_path / "taxomesh.toml").write_text(f'[repository]\ntype = "json"\npath = "{store}"\n', encoding="utf-8")
    result = runner.invoke(app, ["--verbose", "category", "list"])
    assert result.exit_code == 0
    assert "store.json" in result.output
    assert store.exists()


def test_cli_toml_type_unsupported_exits_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """taxomesh.toml with type=csv → exit code 1 and descriptive error."""
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
    """Existing taxomesh.json is not modified when CLI defaults to YAML."""
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


# ---------------------------------------------------------------------------
# The command tree: each command is its Python member's name, `_` written `-`
# ---------------------------------------------------------------------------

EXPECTED_TREE: dict[str, set[str]] = {
    "category": {"list", "roots", "create", "add-parent", "remove-parent", "update", "delete"},
    "item": {
        "list",
        "create",
        "update",
        "delete",
        "place-in",
        "remove-from",
        "tag",
        "untag",
        "relate",
        "unrelate",
        "list-relations",
        "list-related",
    },
    "tag": {"list", "create", "update", "delete"},
}
GROUP_COLLECTIONS: dict[str, type] = {"category": CategoryCollection, "item": ItemCollection, "tag": TagCollection}


def _groups() -> dict[str, click.Group]:
    """The entity groups of the command line, by name."""
    root = typer.main.get_command(app)
    assert isinstance(root, click.Group)
    return {name: command for name, command in root.commands.items() if isinstance(command, click.Group)}


def _top_level_commands() -> set[str]:
    """The commands directly under ``taxomesh`` that are not groups."""
    root = typer.main.get_command(app)
    assert isinstance(root, click.Group)
    return {name for name, command in root.commands.items() if not isinstance(command, click.Group)}


def test_the_command_tree() -> None:
    """Each entity group holds exactly its commands, and no group nests another."""
    groups = _groups()
    assert {name: set(group.commands) for name, group in groups.items()} == EXPECTED_TREE
    assert _top_level_commands() == {"graph", "version"}
    for group in groups.values():
        assert not [name for name, command in group.commands.items() if isinstance(command, click.Group)]


@pytest.mark.parametrize(
    ("group", "command"),
    [(group, command) for group, commands in sorted(EXPECTED_TREE.items()) for command in sorted(commands)],
)
def test_each_command_names_a_member_of_its_collection(group: str, command: str) -> None:
    """``item place-in`` calls ``svc.items.place_in``: the name, with ``-`` read as ``_``."""
    collection = GROUP_COLLECTIONS[group]
    assert callable(getattr(collection, command.replace("-", "_"), None))


@pytest.mark.parametrize(
    ("group", "command"),
    [(group, command) for group in sorted(GROUP_COLLECTIONS) for command in ("create", "update")],
)
def test_create_and_update_offer_their_options_in_the_members_order(group: str, command: str) -> None:
    """``item create`` offers ``--name``, ``--slug`` and ``--external-id`` in the order ``items.create`` takes them."""
    parameters = list(inspect.signature(getattr(GROUP_COLLECTIONS[group], command)).parameters)
    options = [
        option.name
        for option in _groups()[group].commands[command].params
        if isinstance(option, click.Option) and option.name in parameters
    ]

    assert options
    assert options == sorted(options, key=parameters.index)


@pytest.mark.parametrize(
    ("group", "command"),
    [(group, command) for group, commands in sorted(EXPECTED_TREE.items()) for command in sorted(commands)],
)
def test_each_command_help_ends_at_its_summary(group: str, command: str) -> None:
    """``--help`` shows the summary and the options, never the docstring's ``Args:`` block."""
    result = runner.invoke(app, [group, command, "--help"])
    assert result.exit_code == 0
    assert "Args:" not in result.output


@pytest.mark.parametrize(
    "command",
    [
        ["category", "create", "--name", "X", "--parent-id", "00000000-0000-0000-0000-000000000001"],
        [
            "category",
            "update",
            "00000000-0000-0000-0000-000000000001",
            "--parent-id",
            "00000000-0000-0000-0000-000000000002",
        ],
        ["item", "create", "--name", "X", "--category-id", "00000000-0000-0000-0000-000000000001"],
        ["item", "create", "--name", "X", "--tag-id", "00000000-0000-0000-0000-000000000001"],
        [
            "item",
            "update",
            "00000000-0000-0000-0000-000000000001",
            "--category-id",
            "00000000-0000-0000-0000-000000000002",
        ],
        ["item", "update", "00000000-0000-0000-0000-000000000001", "--tag-id", "00000000-0000-0000-0000-000000000002"],
    ],
    ids=[
        "category-create-parent",
        "category-update-parent",
        "item-create-category",
        "item-create-tag",
        "item-update-category",
        "item-update-tag",
    ],
)
def test_a_command_calls_one_member(command: list[str]) -> None:
    """``create`` and ``update`` take their member's arguments only: a link is its own command."""
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, command)
    assert result.exit_code == 2
    assert "No such option" in result.output


def test_category_list_lists_every_category() -> None:
    """With no filter, ``category list`` answers ``list()``: a category with a parent too."""
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    parent = svc.categories.create(name="Parent")
    child = svc.categories.create(name="Child")
    svc.categories.add_parent(child, parent)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "list"])
    assert result.exit_code == 0
    assert str(parent.category_id) in result.output
    assert str(child.category_id) in result.output


def test_category_roots_lists_the_top_level() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    parent = svc.categories.create(name="Parent")
    child = svc.categories.create(name="Child")
    svc.categories.add_parent(child, parent)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "roots"])
    assert result.exit_code == 0
    assert str(parent.category_id) in result.output
    assert str(child.category_id) not in result.output


def test_category_list_by_item() -> None:
    """``--item-id`` lists the categories the item is placed in."""
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    holding = svc.categories.create(name="Holding")
    other = svc.categories.create(name="Other")
    item = svc.items.create(name="Thing")
    svc.items.place_in(item, holding)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "list", "--item-id", str(item.item_id)])
    assert result.exit_code == 0
    assert str(holding.category_id) in result.output
    assert str(other.category_id) not in result.output


def test_category_create_with_external_id() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["category", "create", "--name", "Music", "--external-id", "cat-music"])
    assert result.exit_code == 0
    found = _svc_with_repo(repo).categories.get_by_external_id("cat-music")
    assert found is not None
    assert found.name == "Music"


@pytest.mark.parametrize(("flag", "enabled"), [("--disable", False), ("--enable", True)])
def test_item_update_sets_enabled(flag: str, enabled: bool) -> None:
    """One ``--enable/--disable`` pair, as on ``category update``; left off, the field stays."""
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.items.create(name="x")
    svc.items.update(item, enabled=not enabled)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "update", str(item.item_id), flag])
    assert result.exit_code == 0
    assert _svc_with_repo(repo).items[item.item_id].enabled is enabled


def test_item_update_leaves_enabled_when_the_flag_is_left_off() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.items.create(name="x")
    svc.items.update(item, enabled=False)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["item", "update", str(item.item_id), "--name", "y"])
    assert result.exit_code == 0
    stored = _svc_with_repo(repo).items[item.item_id]
    assert (stored.name, stored.enabled) == ("y", False)


def test_item_list_by_tag() -> None:
    """``--tag-id`` lists the items carrying the tag, and composes with ``--category-id``."""
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    shelf = svc.categories.create(name="Shelf")
    inside = svc.items.create(name="Inside")
    outside = svc.items.create(name="Outside")
    live = svc.tags.create(name="live")
    svc.items.place_in(inside, shelf)
    svc.items.tag(inside, live)
    svc.items.tag(outside, live)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        tagged = runner.invoke(app, ["item", "list", "--tag-id", str(live.tag_id)])
        both = runner.invoke(
            app, ["item", "list", "--tag-id", str(live.tag_id), "--category-id", str(shelf.category_id)]
        )
    assert tagged.exit_code == 0
    assert str(inside.item_id) in tagged.output
    assert str(outside.item_id) in tagged.output
    assert both.exit_code == 0
    assert str(inside.item_id) in both.output
    assert str(outside.item_id) not in both.output


def test_item_list_recursive() -> None:
    """``--recursive`` takes the category's descendants in."""
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    parent = svc.categories.create(name="Parent")
    child = svc.categories.create(name="Child")
    svc.categories.add_parent(child, parent)
    deep = svc.items.create(name="Deep")
    svc.items.place_in(deep, child)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        direct = runner.invoke(app, ["item", "list", "--category-id", str(parent.category_id)])
        recursive = runner.invoke(app, ["item", "list", "--category-id", str(parent.category_id), "--recursive"])
    assert direct.exit_code == 0
    assert str(deep.item_id) not in direct.output
    assert recursive.exit_code == 0
    assert str(deep.item_id) in recursive.output


def test_tag_list_by_item() -> None:
    """``--item-id`` lists the tags the item carries."""
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.items.create(name="Thing")
    live = svc.tags.create(name="live")
    studio = svc.tags.create(name="studio")
    svc.items.tag(item, live)
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["tag", "list", "--item-id", str(item.item_id)])
    assert result.exit_code == 0
    assert str(live.tag_id) in result.output
    assert str(studio.tag_id) not in result.output


def test_tag_list_unknown_item_fails() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["tag", "list", "--item-id", str(uuid4())])
    assert result.exit_code == 1


def test_an_empty_graph_names_the_create_command() -> None:
    """The hint on an empty store names a command that exists."""
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, ["graph"])
    assert result.exit_code == 0
    assert "taxomesh category create --name <name>" in result.output


@pytest.mark.parametrize("group", ["category", "item"])
def test_create_reports_a_refused_write(group: str) -> None:
    """A slug already taken is refused by the member, and the command exits 1 with its message."""
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        runner.invoke(app, [group, "create", "--name", "First", "--slug", "taken"])
        result = runner.invoke(app, [group, "create", "--name", "Second", "--slug", "taken"])
    assert result.exit_code == 1
    assert "taken" in result.output


@pytest.mark.parametrize("group", ["category", "item"])
def test_update_reports_an_unknown_row(group: str) -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
        result = runner.invoke(app, [group, "update", str(uuid4()), "--name", "x"])
    assert result.exit_code == 1
