"""Tests for packaging metadata that consumers depend on.

The PEP 561 marker is the one piece of packaging that silently changes behavior in
someone else's project: without ``py.typed`` a downstream ``mypy`` ignores every
annotation taxomesh ships, so the inline types and the ``Typing :: Typed`` classifier
have no effect at all. It is invisible from inside this repository — the suite here type
checks fine either way — which is exactly why it needs a test.
"""

import re
import subprocess
import sys
import tomllib
import zipfile
from collections.abc import Mapping
from importlib import import_module
from importlib.resources import files
from itertools import chain
from pathlib import Path
from typing import Final

import pytest

import taxomesh
import taxomesh.exceptions
from taxomesh import repositories
from taxomesh.adapters.cli import CLI_EXTRA_MESSAGE, run
from taxomesh.adapters.repositories import django_repository, json_repository, yaml_repository
from taxomesh.contrib.api import errors

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Every name the package root exports, keyed by the module that defines it. One
# table drives all three export tests: what ``__all__`` must list, what must be bound on the
# package, and which object each name must be.
_PUBLIC_EXPORTS: Final[Mapping[str, frozenset[str]]] = {
    "taxomesh.application.service": frozenset({"TaxomeshService"}),
    "taxomesh.exceptions": frozenset(
        {
            "TaxomeshCategoryNotFoundError",
            "TaxomeshConfigError",
            "TaxomeshCyclicDependencyError",
            "TaxomeshDuplicateSlugError",
            "TaxomeshError",
            "TaxomeshExternalIdConflictError",
            "TaxomeshItemNotFoundError",
            "TaxomeshNotFoundError",
            "TaxomeshRelationError",
            "TaxomeshRepositoryError",
            "TaxomeshRootCategoryError",
            "TaxomeshTagNotFoundError",
            "TaxomeshValidationError",
            "TaxomeshVersionConflictError",
        }
    ),
    # ``ModelBase`` is deliberately absent: it is the shared Pydantic base, not a domain
    # model. No public member accepts or returns one, and it appears in no public signature.
    "taxomesh.domain.models": frozenset(
        {
            "Category",
            "CategoryParentLink",
            "Item",
            "ItemParentLink",
            "ItemRelationLink",
            "ItemTagLink",
            "Tag",
        }
    ),
    "taxomesh.domain.graph": frozenset({"CategoryNode", "TaxomeshGraph"}),
    "taxomesh.domain.related": frozenset({"RelatedItems"}),
    "taxomesh.domain.info": frozenset({"RepositoryInfo", "TaxomeshInfo"}),
    "taxomesh.ports.repository": frozenset({"TaxomeshRepositoryBase"}),
    # ``UnsetType`` travels with ``UNSET``: the sentinel is unannotatable without its type.
    # ``normalise_external_id`` is not here — it is the conversion rule, not a public type.
    "taxomesh.domain.types": frozenset({"UNSET", "Direction", "ExternalId", "UnsetType"}),
    # The conversions beside them, ``category_id_of`` and its siblings, are the rule behind the
    # types, as ``normalise_external_id`` is.
    "taxomesh.domain.refs": frozenset({"CategoryRef", "ItemRef", "TagRef"}),
}

_EXPECTED_EXPORTS: Final[frozenset[str]] = frozenset(chain.from_iterable(_PUBLIC_EXPORTS.values()))

_CLI_DEPENDENCIES: Final[frozenset[str]] = frozenset({"typer", "rich"})


def _pyproject() -> dict[str, object]:
    """Return ``pyproject.toml`` as a table."""
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)


def _project() -> dict[str, object]:
    """Return the ``[project]`` table of ``pyproject.toml``."""
    project = _pyproject()["project"]
    assert isinstance(project, dict)
    return project


def _requirement_names(requirements: object) -> set[str]:
    """Return the distribution names a list of requirement strings names."""
    assert isinstance(requirements, list)
    return {re.split(r"[<>=!~;\[ ]", str(requirement), maxsplit=1)[0].lower() for requirement in requirements}


class TestPyTypedMarker:
    """PEP 561 — the marker that makes taxomesh's inline types visible to consumers."""

    def test_marker_is_present_in_the_package(self) -> None:
        """taxomesh/py.typed exists and is importable as package data."""
        marker = files("taxomesh") / "py.typed"
        assert marker.is_file(), (
            "taxomesh/py.typed is missing. Without it, PEP 561 tells downstream type "
            "checkers to ignore every annotation in this package."
        )

    def test_typed_classifier_is_declared(self) -> None:
        """The Typing :: Typed classifier and the marker file must agree.

        Either alone is a false claim: the classifier without the file promises types
        that never arrive, and the file without the classifier hides that they do.
        """
        with (PROJECT_ROOT / "pyproject.toml").open("rb") as fh:
            pyproject = tomllib.load(fh)

        assert "Typing :: Typed" in pyproject["project"]["classifiers"]


class TestBuiltWheel:
    """The marker has to survive the build, not just exist in the source tree."""

    @pytest.fixture(scope="class")
    def wheel(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        """Build a wheel into a temporary directory and return its path."""
        out_dir = tmp_path_factory.mktemp("wheel")
        result = subprocess.run(
            ["uv", "build", "--wheel", "--out-dir", str(out_dir)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"uv build failed:\n{result.stderr}"

        built = list(out_dir.glob("*.whl"))
        assert len(built) == 1, f"expected one wheel, got {built}"
        return built[0]

    def test_wheel_contains_the_marker(self, wheel: Path) -> None:
        """A consumer installing from PyPI gets py.typed, not just a git checkout."""
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()

        assert "taxomesh/py.typed" in names, f"py.typed absent from the built wheel; contents: {sorted(names)[:20]}"


class TestPublicExports:
    """The package root carries the whole public surface.

    A consumer reading a public signature such as ``external_id: ExternalId | UnsetType =
    UNSET`` has to be able to spell those three types. While they lived only in
    ``taxomesh.domain.types`` the annotation was readable in the reference and unwritable in
    the consumer's own code — exportable but unannotatable.
    """

    def test_all_lists_exactly_the_public_surface(self) -> None:
        """``__all__`` names every root export, once each, and nothing besides."""
        declared = list(taxomesh.__all__)
        repeated = sorted({name for name in declared if declared.count(name) > 1})
        assert not repeated, f"__all__ repeats: {repeated}"

        missing = sorted(_EXPECTED_EXPORTS - set(declared))
        unexpected = sorted(set(declared) - _EXPECTED_EXPORTS)
        assert not missing and not unexpected, f"__all__ is missing {missing} and carries unexpected {unexpected}"

    def test_every_public_name_is_bound_on_the_package(self) -> None:
        """``from taxomesh import <name>`` succeeds for every name.

        ``__all__`` is a declaration, not a guarantee: a name listed there but never imported
        into the module still fails at the import. This checks the binding, not the listing.
        """
        unreachable = sorted(name for name in _EXPECTED_EXPORTS if not hasattr(taxomesh, name))
        assert not unreachable, f"exported but not bound on `taxomesh`: {unreachable}"

    def test_every_export_is_the_object_its_module_defines(self) -> None:
        """Each re-export is the original object, not a second definition shadowing it.

        Reaching the objects by name is the subject of this test rather than a way around
        the type system: the table above is what drives it, so there is no literal to import.
        """
        shadowed = [
            f"{name} ({module_path})"
            for module_path, names in _PUBLIC_EXPORTS.items()
            for name in sorted(names)
            if getattr(taxomesh, name, None) is not getattr(import_module(module_path), name)
        ]
        assert not shadowed, f"re-exported as a different object than its own module defines: {shadowed}"


class TestTheHttpOnlyError:
    """The error only the HTTP serializer raises lives beside it, not in the core."""

    def test_it_lives_in_the_http_errors_module(self) -> None:
        assert issubclass(errors.TaxomeshGraphTooLargeError, taxomesh.TaxomeshError)

    def test_it_is_not_in_the_core(self) -> None:
        assert not hasattr(taxomesh, "TaxomeshGraphTooLargeError")
        assert not hasattr(taxomesh.exceptions, "TaxomeshGraphTooLargeError")


class TestTheCliExtra:
    """typer and rich are the ``cli`` extra: the library installs and imports without them."""

    def test_importing_the_package_imports_no_cli_and_no_django(self) -> None:
        probe = "import sys, taxomesh; print(sorted(m for m in ('typer', 'rich', 'django') if m in sys.modules))"

        result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)

        assert result.stdout.strip() == "[]"

    def test_typer_and_rich_are_the_cli_extra_and_not_core(self) -> None:
        project = _project()
        extras = project["optional-dependencies"]
        assert isinstance(extras, dict)

        assert not _CLI_DEPENDENCIES & _requirement_names(project["dependencies"])
        assert _requirement_names(extras["cli"]) == _CLI_DEPENDENCIES

    def test_the_console_script_without_the_extra_exits_naming_it(self) -> None:
        """The declared ``taxomesh`` script, run where typer and rich cannot be imported."""
        scripts = _project()["scripts"]
        assert isinstance(scripts, dict)
        module, _, attribute = str(scripts["taxomesh"]).partition(":")
        probe = (
            "import sys\n"
            "sys.modules['typer'] = None\n"
            "sys.modules['rich'] = None\n"
            f"from {module} import {attribute}\n"
            f"{attribute}()\n"
        )

        result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=False)

        assert result.returncode != 0
        assert "taxomesh[cli]" in result.stderr
        assert "Traceback" not in result.stderr

    def test_run_exits_with_the_message_when_typer_cannot_be_imported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delitem(sys.modules, "taxomesh.adapters.cli.main", raising=False)
        monkeypatch.setitem(sys.modules, "typer", None)

        with pytest.raises(SystemExit) as exited:
            run()

        assert exited.value.code == CLI_EXTRA_MESSAGE

    def test_run_raises_any_other_missing_module_as_it_is(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "taxomesh.adapters.cli.main", None)

        with pytest.raises(ModuleNotFoundError):
            run()


class TestTheRepositoriesModule:
    """``taxomesh.repositories`` names the three storage backends a service can be given."""

    def test_it_re_exports_the_three_adapters(self) -> None:
        assert repositories.JsonRepository is json_repository.JsonRepository
        assert repositories.YamlRepository is yaml_repository.YamlRepository
        assert repositories.DjangoRepository is django_repository.DjangoRepository
        assert sorted(repositories.__all__) == ["DjangoRepository", "JsonRepository", "YamlRepository"]

    def test_the_yaml_adapter_is_named_as_a_word_with_no_alias(self) -> None:
        assert yaml_repository.YamlRepository.__name__ == "YamlRepository"
        assert not hasattr(yaml_repository, "YAMLRepository")
        assert not hasattr(repositories, "YAMLRepository")

    def test_importing_it_imports_no_django(self) -> None:
        probe = "import sys, taxomesh.repositories; print('django' in sys.modules)"

        result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)

        assert result.stdout.strip() == "False"


class TestEachThingIsSaidOnce:
    """The packaging states each fact in one place."""

    def test_the_dev_tools_are_one_dependency_group(self) -> None:
        """The tools a contributor runs are a PEP 735 group: not a published extra, and not repeated."""
        pyproject = _pyproject()
        project = _project()
        extras = project["optional-dependencies"]
        groups = pyproject["dependency-groups"]
        assert isinstance(extras, dict)
        assert isinstance(groups, dict)
        published = _requirement_names(project["dependencies"]).union(
            *(_requirement_names(requirements) for requirements in extras.values())
        )

        assert "dev" not in extras
        assert not _requirement_names(groups["dev"]) & published

    def test_the_description_is_the_package_docstring_summary(self) -> None:
        assert taxomesh.__doc__ is not None
        summary = " ".join(taxomesh.__doc__.split("\n\n")[0].split())

        assert _project()["description"] == summary

    def test_the_example_taxonomy_ships_in_one_copy(self) -> None:
        copies = sorted(
            path.relative_to(PROJECT_ROOT).as_posix() for path in PROJECT_ROOT.glob("*/taxomesh_example.yaml")
        )

        assert copies == ["examples/taxomesh_example.yaml"]
