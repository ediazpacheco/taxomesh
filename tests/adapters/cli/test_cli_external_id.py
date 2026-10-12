"""Tests for CLI external_id handling, and the form an external id is stored in."""

from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
import typer.testing

from taxomesh import TaxomeshService
from taxomesh.adapters.cli.config import BuildResult
from taxomesh.adapters.cli.main import app
from tests.service.conftest import InMemoryRepository

runner = typer.testing.CliRunner()


def _stored_external_id(raw: str | None) -> str | None:
    """Run ``item create --external-id <raw>``, or without the option for None, and return what is stored."""
    repo = InMemoryRepository()
    built = BuildResult(
        service=TaxomeshService(repository=repo),
        repository=repo,
        config_file_path=Path("/fake/taxomesh.toml"),
        config_file_exists=False,
    )
    with patch("taxomesh.adapters.cli.main.build", return_value=built):
        option = [] if raw is None else ["--external-id", raw]
        result = runner.invoke(app, ["item", "create", "--name", "Item", *option])
    assert result.exit_code == 0, result.output
    (item,) = repo.list_items(enabled=None)
    return item.external_id


class TestTheCliStoresTheExternalIdAsWritten:
    """``item create --external-id`` hands the text to the one conversion rule unchanged.

    The CLI does not parse it first, as a UUID or an integer: ``0042`` stays ``"0042"``,
    ``" 42 "`` does not collide with ``42``, and an upper-case UUID keeps its case, as the library
    stores each for every write.
    """

    def test_an_empty_option_is_stored_as_written(self) -> None:
        """``""`` is a valid external id, so ``--external-id ""`` stores it; leaving it off stores none."""
        assert _stored_external_id("") == ""

    def test_an_omitted_option_stores_none(self) -> None:
        assert _stored_external_id(None) is None

    def test_digits_are_stored_as_text(self) -> None:
        assert _stored_external_id("42") == "42"

    @pytest.mark.parametrize(
        "raw",
        ["0042", " 42 ", str(uuid4()).upper()],
        ids=["leading-zeros", "surrounding-spaces", "upper-case-uuid"],
    )
    def test_the_text_is_stored_as_written(self, raw: str) -> None:
        assert _stored_external_id(raw) == raw


class TestCliExternalIdDisplay:
    """Verify that None external_id does not render as 'None' in CLI output."""

    def test_item_str_with_none_external_id_omits_external_id(self) -> None:
        from taxomesh.domain.models import Item  # noqa: PLC0415

        item = Item(item_id=uuid4(), name="Test", external_id=None)
        rendered = str(item)
        assert "None" not in rendered
        assert "external_id" not in rendered

    def test_item_str_with_none_external_id_not_empty_dash(self) -> None:
        """None external_id renders as empty indicator, not literal 'None'."""
        from taxomesh.domain.models import Item  # noqa: PLC0415

        item = Item(item_id=uuid4(), name="Product", external_id=None)
        rendered = str(item)
        # The rendered string must not contain the Python literal "None"
        assert "None" not in rendered

    def test_a_listing_prints_each_row_as_its_label(self) -> None:
        """``category list`` prints ``str(row)``: the plain-text label, as it is."""
        repo = InMemoryRepository()
        service = TaxomeshService(repository=repo)
        music = service.categories.create("Music", slug="music", external_id="cat:music")
        built = BuildResult(
            service=service, repository=repo, config_file_path=Path("/fake/taxomesh.toml"), config_file_exists=False
        )
        with patch("taxomesh.adapters.cli.main.build", return_value=built):
            result = runner.invoke(app, ["category", "list"])

        assert result.exit_code == 0, result.output
        assert f"Music (slug: music, id: {music.category_id}, external_id: cat:music)" in result.output.splitlines()
