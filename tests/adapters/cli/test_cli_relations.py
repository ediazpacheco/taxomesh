"""CLI tests for the item relation commands: relate, unrelate, list-relations and list-related."""

from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
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
    src = svc.items.create(name="A")
    tgt = svc.items.create(name="B")
    return repo, src.item_id, tgt.item_id


class TestItemRelate:
    def test_relate_creates_relation(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "relate", str(src_id), str(tgt_id), "covers"])
        assert result.exit_code == 0
        assert result.output.splitlines() == [f"Stored relation: {src_id} --[covers]--> {tgt_id}"]

    def test_relate_refuses_metadata_without_a_value(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(
                app, ["item", "relate", str(src_id), str(tgt_id), "covers", "--metadata", "novalue"]
            )
        assert result.exit_code == 1
        assert result.output.splitlines() == ["--metadata must be KEY=VALUE, not 'novalue'"]

    def test_relate_with_sort_index(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "relate", str(src_id), str(tgt_id), "covers", "--sort-index", "5"])
        assert result.exit_code == 0

    def test_relate_with_metadata(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(
                app,
                [
                    "item",
                    "relate",
                    str(src_id),
                    str(tgt_id),
                    "covers",
                    "--metadata",
                    "key=value",
                ],
            )
        assert result.exit_code == 0

    def test_relate_self_relation_rejected(self) -> None:
        repo, src_id, _ = _make_repo_with_two_items()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "relate", str(src_id), str(src_id), "covers"])
        assert result.exit_code == 1

    def test_relate_empty_type_rejected(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "relate", str(src_id), str(tgt_id), ""])
        assert result.exit_code == 1

    def test_relate_unknown_source_rejected(self) -> None:
        repo, _, tgt_id = _make_repo_with_two_items()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "relate", str(uuid4()), str(tgt_id), "covers"])
        assert result.exit_code == 1


class TestItemListRelations:
    def test_list_relations_outgoing_shows_relations(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        svc = TaxomeshService(repository=repo)
        svc.items.relate(src_id, tgt_id, "covers")
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "list-relations", str(src_id)])
        assert result.exit_code == 0
        assert "covers" in result.output

    def test_list_relations_empty(self) -> None:
        repo, src_id, _ = _make_repo_with_two_items()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "list-relations", str(src_id)])
        assert result.exit_code == 0

    def test_list_relations_direction_incoming(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        svc = TaxomeshService(repository=repo)
        svc.items.relate(src_id, tgt_id, "covers")
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "list-relations", str(tgt_id), "--direction", "incoming"])
        assert result.exit_code == 0
        assert "covers" in result.output

    def test_list_relations_filter_by_type(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        svc = TaxomeshService(repository=repo)
        svc.items.relate(src_id, tgt_id, "covers")
        svc.items.relate(src_id, tgt_id, "samples")
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "list-relations", str(src_id), "--relation-type", "covers"])
        assert result.exit_code == 0
        assert "covers" in result.output


class TestItemListRelated:
    def test_list_related_resolves_items(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        svc = TaxomeshService(repository=repo)
        svc.items.relate(src_id, tgt_id, "covers")
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "list-related", str(src_id)])
        assert result.exit_code == 0

    def test_list_related_direction_incoming(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        svc = TaxomeshService(repository=repo)
        svc.items.relate(src_id, tgt_id, "covers")
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "list-related", str(tgt_id), "--direction", "incoming"])
        assert result.exit_code == 0

    def test_list_related_filter_by_type(self) -> None:
        """``--relation-type`` narrows the resolved items, not just the links.

        The count is what discriminates: both relations point at the same target, so an
        ignored option would resolve it twice and report ``Total: 2``.
        """
        repo, src_id, tgt_id = _make_repo_with_two_items()
        svc = TaxomeshService(repository=repo)
        svc.items.relate(src_id, tgt_id, "covers")
        svc.items.relate(src_id, tgt_id, "samples")
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "list-related", str(src_id), "--relation-type", "covers"])
        assert result.exit_code == 0
        assert "--- Total: 1 ---" in result.output


class TestItemListRelatedState:
    """``--state`` selects the related items by their state, as on ``item list``.

    The source relates to one enabled and one disabled item, so each state lists a different set.
    """

    @staticmethod
    def _related_by_state(state: list[str]) -> str:
        repo = InMemoryRepository()
        svc = TaxomeshService(repository=repo)
        source = svc.items.create(name="Source")
        live = svc.items.create(name="Live")
        dark = svc.items.create(name="Dark")
        svc.items.update(dark, enabled=False)
        svc.items.relate(source, live, "covers")
        svc.items.relate(source, dark, "covers")
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "list-related", str(source.item_id), *state])
        assert result.exit_code == 0, result.output
        return result.output

    def test_the_enabled_items_by_default(self) -> None:
        output = self._related_by_state([])
        assert "Live" in output and "Dark" not in output

    def test_the_disabled_items(self) -> None:
        output = self._related_by_state(["--state", "disabled"])
        assert "Dark" in output and "Live" not in output

    def test_every_item(self) -> None:
        output = self._related_by_state(["--state", "all"])
        assert "Live" in output and "Dark" in output
        assert "--- Total: 2 ---" in output


class TestRepeatedRelationType:
    """``--relation-type`` given twice selects both types, as ``relation_types`` takes several.

    The source relates to a different item under each of three types, so the count tells the two
    selected types from the last one alone and from all three.
    """

    @staticmethod
    def _two_of_three_types(command: str) -> str:
        repo = InMemoryRepository()
        svc = TaxomeshService(repository=repo)
        source = svc.items.create(name="Source")
        for name, relation_type in (("Cover", "covers"), ("Sample", "samples"), ("Remix", "remixes")):
            svc.items.relate(source, svc.items.create(name=name), relation_type)
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(
                app,
                ["item", command, str(source.item_id), "--relation-type", "covers", "--relation-type", "samples"],
            )
        assert result.exit_code == 0, result.output
        return result.output

    def test_list_relations_takes_both_types(self) -> None:
        output = self._two_of_three_types("list-relations")
        assert "--- Total: 2 ---" in output
        assert "remixes" not in output

    def test_list_related_takes_both_types(self) -> None:
        output = self._two_of_three_types("list-related")
        assert "--- Total: 2 ---" in output
        assert "Cover" in output and "Sample" in output and "Remix" not in output


class TestItemUnrelate:
    def test_unrelate_removes_relation(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        svc = TaxomeshService(repository=repo)
        svc.items.relate(src_id, tgt_id, "covers")
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "unrelate", str(src_id), str(tgt_id), "covers"])
        assert result.exit_code == 0
        assert result.output.splitlines() == [f"Removed relation: {src_id} --[covers]--> {tgt_id}"]

    def test_unrelate_of_an_absent_relation_changes_nothing(self) -> None:
        repo, src_id, tgt_id = _make_repo_with_two_items()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "unrelate", str(src_id), str(tgt_id), "covers"])
        assert result.exit_code == 0
        assert not repo.list_item_relation_links(src_id, direction="both")

    def test_unrelate_of_an_unknown_item_exits(self) -> None:
        repo, src_id, _ = _make_repo_with_two_items()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "unrelate", str(src_id), str(uuid4()), "covers"])
        assert result.exit_code == 1


DIRECTION_COMMANDS: list[list[str]] = [["item", "list-relations"], ["item", "list-related"]]


class TestRejectsAnUnknownDirection:
    """Both commands taking ``--direction`` must refuse a value outside the three directions.

    Parametrized over both so a command that simply forgot the option is caught: that failure
    also exits 2, and asserting only on the exit code would not tell the two apart. Hence the
    assertion on the message naming the valid choices.

    The option is typed as :class:`~taxomesh.domain.types.Direction`, so an unknown value is
    refused at the boundary rather than answered by ``list-relations`` or ``list-related``.
    """

    @pytest.mark.parametrize("command", DIRECTION_COMMANDS, ids=[" ".join(c) for c in DIRECTION_COMMANDS])
    def test_unknown_direction_is_refused(self, command: list[str]) -> None:
        repo, src_id, _ = _make_repo_with_two_items()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, [*command, str(src_id), "--direction", "nonsense"])
        assert result.exit_code == 2
        assert "outgoing" in result.output, "the error must name the valid choices, not just fail"
