"""Tests for CLI --include-disabled flag on category list, item list, and graph (spec 046).

Written before implementation (TDD-first).
"""

from pathlib import Path
from unittest.mock import patch

import typer.testing

from taxomesh.adapters.cli.config import BuildResult
from taxomesh.adapters.cli.main import app
from taxomesh.application.service import TaxomeshService
from tests.service.conftest import InMemoryRepository

runner = typer.testing.CliRunner()


def _build_result(repo: InMemoryRepository) -> BuildResult:
    svc = TaxomeshService(repository=repo)
    return BuildResult(
        service=svc,
        repository=repo,
        config_file_path=Path("/fake/taxomesh.toml"),
        config_file_exists=False,
    )


def _make_repo_with_disabled_category() -> InMemoryRepository:
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    svc.create_category(name="ActiveCategory")
    cat_off = svc.create_category(name="DisabledCategory")
    cat_off_obj = repo.get_category(cat_off.category_id)
    assert cat_off_obj is not None
    cat_off_obj.enabled = False
    repo.save_category(cat_off_obj)
    return repo


def _make_repo_with_disabled_item() -> InMemoryRepository:
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    svc.create_item(name="ActiveItem")
    item_off = svc.create_item(name="DisabledItem")
    svc.update_item(item_off.item_id, enabled=False)
    return repo


class TestCategoryListIncludeDisabled:
    def test_default_hides_disabled(self) -> None:
        repo = _make_repo_with_disabled_category()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["category", "list"])
        assert result.exit_code == 0
        assert "ActiveCategory" in result.output
        assert "DisabledCategory" not in result.output

    def test_include_disabled_shows_all(self) -> None:
        repo = _make_repo_with_disabled_category()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["category", "list", "--include-disabled"])
        assert result.exit_code == 0
        assert "ActiveCategory" in result.output
        assert "DisabledCategory" in result.output


class TestItemListIncludeDisabled:
    def test_default_hides_disabled(self) -> None:
        repo = _make_repo_with_disabled_item()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "list"])
        assert result.exit_code == 0
        assert "ActiveItem" in result.output
        assert "DisabledItem" not in result.output

    def test_include_disabled_shows_all(self) -> None:
        repo = _make_repo_with_disabled_item()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "list", "--include-disabled"])
        assert result.exit_code == 0
        assert "ActiveItem" in result.output
        assert "DisabledItem" in result.output
