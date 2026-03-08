"""CLI tests for the 'relation' command group (US6)."""

from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import typer.testing

from taxomesh import TaxomeshService
from taxomesh.adapters.cli.config import BuildResult
from taxomesh.adapters.cli.main import app
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


def _make_repo_with_two_items() -> tuple[InMemoryRepository, UUID, UUID]:
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    src = svc.create_item(name="A")
    tgt = svc.create_item(name="B")
    return repo, src.item_id, tgt.item_id


class TestRelationAdd:
    def test_relation_add_creates_relation(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "relation", "add", str(src_id), str(tgt_id), "covers"])
        assert result.exit_code == 0
        assert "covers" in result.output

    def test_relation_add_with_sort_index(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(
                app, ["item", "relation", "add", str(src_id), str(tgt_id), "covers", "--sort-index", "5"]
            )
        assert result.exit_code == 0

    def test_relation_add_with_metadata(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(
                app,
                [
                    "item",
                    "relation",
                    "add",
                    str(src_id),
                    str(tgt_id),
                    "covers",
                    "--metadata",
                    "key=value",
                ],
            )
        assert result.exit_code == 0

    def test_relation_add_self_relation_rejected(self) -> None:
        repo, src_id, _ = _make_repo_with_two_items()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "relation", "add", str(src_id), str(src_id), "covers"])
        assert result.exit_code == 1

    def test_relation_add_empty_type_rejected(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "relation", "add", str(src_id), str(tgt_id), ""])
        assert result.exit_code == 1

    def test_relation_add_unknown_source_rejected(self) -> None:
        repo, _, tgt_id = _make_repo_with_two_items()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "relation", "add", str(uuid4()), str(tgt_id), "covers"])
        assert result.exit_code == 1


class TestRelationList:
    def test_relation_list_outgoing_shows_relations(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        svc = TaxomeshService(repository=repo)
        svc.relate_items(src_id, tgt_id, "covers")
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "relation", "list", str(src_id)])
        assert result.exit_code == 0
        assert "covers" in result.output

    def test_relation_list_empty(self) -> None:
        repo, src_id, _ = _make_repo_with_two_items()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "relation", "list", str(src_id)])
        assert result.exit_code == 0

    def test_relation_list_direction_incoming(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        svc = TaxomeshService(repository=repo)
        svc.relate_items(src_id, tgt_id, "covers")
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "relation", "list", str(tgt_id), "--direction", "incoming"])
        assert result.exit_code == 0
        assert "covers" in result.output

    def test_relation_list_filter_by_type(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        svc = TaxomeshService(repository=repo)
        svc.relate_items(src_id, tgt_id, "covers")
        svc.relate_items(src_id, tgt_id, "samples")
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "relation", "list", str(src_id), "--type", "covers"])
        assert result.exit_code == 0
        assert "covers" in result.output


class TestRelationRelated:
    def test_relation_related_resolves_items(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        svc = TaxomeshService(repository=repo)
        svc.relate_items(src_id, tgt_id, "covers")
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "relation", "related", str(src_id)])
        assert result.exit_code == 0

    def test_relation_related_direction_incoming(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        svc = TaxomeshService(repository=repo)
        svc.relate_items(src_id, tgt_id, "covers")
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "relation", "related", str(tgt_id), "--direction", "incoming"])
        assert result.exit_code == 0


class TestRelationDelete:
    def test_relation_delete_removes_relation(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        svc = TaxomeshService(repository=repo)
        svc.relate_items(src_id, tgt_id, "covers")
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "relation", "delete", str(src_id), str(tgt_id), "covers"])
        assert result.exit_code == 0

    def test_relation_delete_not_found_exits(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "relation", "delete", str(src_id), str(tgt_id), "covers"])
        assert result.exit_code == 1
