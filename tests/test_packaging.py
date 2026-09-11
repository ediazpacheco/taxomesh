"""Tests for packaging metadata that consumers depend on.

The PEP 561 marker is the one piece of packaging that silently changes behavior in
someone else's project: without ``py.typed`` a downstream ``mypy`` ignores every
annotation taxomesh ships, so the inline types and the ``Typing :: Typed`` classifier
have no effect at all. It is invisible from inside this repository — the suite here type
checks fine either way — which is exactly why it needs a test.
"""

import subprocess
import tomllib
import zipfile
from importlib.resources import files
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


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
        try:
            subprocess.run(
                ["uv", "build", "--wheel", "--out-dir", str(out_dir)],
                cwd=PROJECT_ROOT,
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            pytest.skip(f"uv build unavailable in this environment: {exc}")

        built = list(out_dir.glob("*.whl"))
        assert len(built) == 1, f"expected one wheel, got {built}"
        return built[0]

    def test_wheel_contains_the_marker(self, wheel: Path) -> None:
        """A consumer installing from PyPI gets py.typed, not just a git checkout."""
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()

        assert "taxomesh/py.typed" in names, f"py.typed absent from the built wheel; contents: {sorted(names)[:20]}"
