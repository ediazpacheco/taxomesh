"""``list()`` means every category, ``roots()`` means the top level, on every surface.

``categories.list()`` with no filters answers every category, and ``roots()`` the categories with
no parent. The recorded top-level rows are ``{Alpha, Beta}`` enabled, ``{Dim}`` disabled, and all
three unfiltered.

Two classes, one per side of the rule:

* the collection, where ``list()`` sees a category below the top level, and
* the periphery, where the HTTP handlers and the CLI's commands, each named after the member it
  calls, answer that member's meaning: ``categories_list`` and ``category list`` every category,
  ``categories_roots`` and ``category roots`` the top level.

The periphery half is here rather than beside its own suites because it is the half nothing else
could catch: every other parentless fixture in the suite is a flat taxonomy, so "all categories"
and "the top level" return the same rows there and a surface calling the wrong member stays
invisible. ``Deep`` exists to break that symmetry.

Sets rather than sequences for the unfiltered comparisons: this file asserts which categories each
member answers, and the order is asserted elsewhere, the port's in
``tests/adapters/repositories/test_repository_contract.py`` and the ``roots()`` path's in
``test_service_categories.py``.
"""

from collections.abc import Sequence
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import typer.testing

from taxomesh.adapters.cli.config import BuildResult
from taxomesh.adapters.cli.main import app
from taxomesh.application.service import TaxomeshService
from taxomesh.contrib.api import handlers
from taxomesh.domain.constants import ROOT_CATEGORY_NAME
from taxomesh.domain.models import Category
from tests.service.conftest import InMemoryRepository

runner = typer.testing.CliRunner()


def _build_taxonomy(service: TaxomeshService) -> None:
    """Create Alpha and Beta at the top level, Deep under Alpha only, and disabled Dim.

    ``Deep`` is the row the split turns up: every category is listed, and only the ones with no
    parent are at the top level.
    """
    alpha = service.categories.create("Alpha")
    service.categories.create("Beta")
    deep = service.categories.create("Deep")
    service.categories.add_parent(deep.category_id, alpha.category_id)
    dim = service.categories.create("Dim")
    service.categories.update(dim.category_id, enabled=False)
    service._cache.clear()


def _names(rows: Sequence[Category]) -> set[str]:
    """Collect the names of a returned category sequence."""
    return {row.name for row in rows}


def _cli_build_result() -> BuildResult:
    """Return a BuildResult over a fresh in-memory taxonomy, for the CLI's patched ``build()``."""
    repo = InMemoryRepository()
    service = TaxomeshService(repository=repo)
    _build_taxonomy(service)
    return BuildResult(
        service=service,
        repository=repo,
        config_file_path=Path("/fake/taxomesh.toml"),
        config_file_exists=False,
    )


class TestTheSplit:
    """``svc.categories``: ``list()`` means every category, ``roots()`` the top level."""

    def test_list_returns_a_category_below_the_top_level(self, service: TaxomeshService) -> None:
        """``Deep`` sits under Alpha only, and ``list()`` returns it."""
        _build_taxonomy(service)

        assert "Deep" in _names(service.categories.list(enabled=None))

    def test_roots_still_ignores_the_non_root_descendant(self, service: TaxomeshService) -> None:
        _build_taxonomy(service)

        assert "Deep" not in _names(service.categories.roots(enabled=None))

    def test_roots_reproduces_the_recorded_listing_for_every_enabled_state(self, service: TaxomeshService) -> None:
        """The top level in each enabled state: ``{Alpha, Beta}``, ``{Dim}``, and all three."""
        _build_taxonomy(service)

        assert _names(service.categories.roots()) == {"Alpha", "Beta"}
        assert _names(service.categories.roots(enabled=False)) == {"Dim"}
        assert _names(service.categories.roots(enabled=None)) == {"Alpha", "Beta", "Dim"}

    def test_list_honours_the_enabled_filter_over_every_category(self, service: TaxomeshService) -> None:
        _build_taxonomy(service)

        assert _names(service.categories.list()) == {"Alpha", "Beta", "Deep"}
        assert _names(service.categories.list(enabled=False)) == {"Dim"}
        assert _names(service.categories.list(enabled=None)) == {"Alpha", "Beta", "Deep", "Dim"}

    def test_roots_returns_a_subset_of_list(self, service: TaxomeshService) -> None:
        """Whatever the top level holds, the whole taxonomy holds too."""
        _build_taxonomy(service)

        assert _names(service.categories.roots(enabled=None)) <= _names(service.categories.list(enabled=None))

    def test_list_excludes_the_implicit_root(self, service: TaxomeshService) -> None:
        """ "All categories" is all the caller's categories — the root is not one of them."""
        _build_taxonomy(service)

        rows = service.categories.list(enabled=None)

        assert service._root_id not in {row.category_id for row in rows}
        assert ROOT_CATEGORY_NAME not in _names(rows)

    def test_list_with_a_parent_is_unchanged(self, service: TaxomeshService) -> None:
        """The filtered path keeps its meaning: Alpha's children, which is Deep alone."""
        _build_taxonomy(service)
        alpha_id = next(row.category_id for row in service.categories.roots() if row.name == "Alpha")

        assert _names(service.categories.list(parent=alpha_id)) == {"Deep"}


class TestThePeripherySpeaksTheSameMeaning:
    """The HTTP handlers and the CLI answer what the member they are named after answers.

    ``categories_list`` and ``category list`` answer ``list()``, every category, and
    ``categories_roots`` and ``category roots`` answer ``roots()``, the top level.
    """

    def test_handler_list_answers_every_category(self, service: TaxomeshService) -> None:
        _build_taxonomy(service)

        assert _names(handlers.categories_list(service)) == {"Alpha", "Beta", "Deep"}

    def test_handler_list_enabled_none_answers_every_category(self, service: TaxomeshService) -> None:
        _build_taxonomy(service)

        assert _names(handlers.categories_list(service, enabled=None)) == {"Alpha", "Beta", "Deep", "Dim"}

    def test_handler_list_with_a_parent_still_filters(self, service: TaxomeshService) -> None:
        _build_taxonomy(service)
        alpha_id = next(row.category_id for row in service.categories.roots() if row.name == "Alpha")

        assert _names(handlers.categories_list(service, parent_id=alpha_id)) == {"Deep"}

    def test_handler_roots_answers_the_top_level(self, service: TaxomeshService) -> None:
        _build_taxonomy(service)

        assert _names(handlers.categories_roots(service)) == {"Alpha", "Beta"}
        assert _names(handlers.categories_roots(service, enabled=None)) == {"Alpha", "Beta", "Dim"}

    def test_cli_category_list_shows_every_category(self) -> None:
        build_result = _cli_build_result()

        with patch("taxomesh.adapters.cli.main.build", return_value=build_result):
            result = runner.invoke(app, ["category", "list"])

        assert result.exit_code == 0
        assert "Alpha" in result.output
        assert "Beta" in result.output
        assert "Deep" in result.output

    def test_cli_category_roots_shows_the_top_level(self) -> None:
        build_result = _cli_build_result()

        with patch("taxomesh.adapters.cli.main.build", return_value=build_result):
            result = runner.invoke(app, ["category", "roots"])

        assert result.exit_code == 0
        assert "Alpha" in result.output
        assert "Beta" in result.output
        assert "Deep" not in result.output

    def test_cli_category_list_with_a_parent_still_filters(self) -> None:
        build_result = _cli_build_result()
        alpha_id = next(row.category_id for row in build_result.service.categories.roots() if row.name == "Alpha")

        with patch("taxomesh.adapters.cli.main.build", return_value=build_result):
            result = runner.invoke(app, ["category", "list", "--parent-id", str(alpha_id)])

        assert result.exit_code == 0
        assert "Deep" in result.output
        assert "Alpha" not in result.output

    def test_cli_category_list_reports_a_missing_parent(self) -> None:
        """An unknown parent is a wrong address, and the command fails."""
        build_result = _cli_build_result()

        with patch("taxomesh.adapters.cli.main.build", return_value=build_result):
            result = runner.invoke(app, ["category", "list", "--parent-id", str(uuid4())])

        assert result.exit_code == 1
