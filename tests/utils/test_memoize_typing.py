"""SC-009: deliberate misuse of the cache must be reported by ``mypy --strict``.

``prime`` and ``cached`` are typed against the decorated callable's own signature and
return type, so priming a ``Category`` into ``get_item``'s cache, or keying on the wrong
argument, is a *type error* rather than a silent extra read. That guarantee is the reason
the cache is a class at all — and static typing is precisely what a runtime test cannot
check, so it is asserted by running the type checker.

The fixture is written to a temporary file rather than committed, so it needs no
``pyproject.toml`` exclusion and cannot drift out of sync with one: a committed file full
of deliberate errors would fail the repository's own ``mypy --strict .`` gate.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

# One misuse per line, each tagged with the marker the assertion looks for. Keep the
# ``# E:`` comment on the same line as the expression it describes.
MISUSE_SOURCE = '''\
"""Deliberate misuses of taxomesh.utils.memoize. Every marked line must error."""

from taxomesh.utils.memoize import Miss, memoize


@memoize(ttl=5)
def paths_from_main() -> dict[int, str]:
    return {1: "a"}


@memoize(ttl=5)
def mosaic(*, count: int = 8) -> list[int]:
    return list(range(count))


class Service:
    @memoize(ttl=5)
    def get_category(self, category_id: int) -> str:
        return f"cat-{category_id}"


svc = Service()

svc.get_category.prime(123, 7)  # E: value type
svc.get_category("x")  # E: argument type
n: int = svc.get_category(7)  # E: return type
paths_from_main(1)  # E: too many args for a zero-argument function
mosaic(3)  # E: count is keyword-only
svc.get_category.cached("x")  # E: argument type on cached
svc.get_category.cached()  # E: missing argument on cached
bad: str = svc.get_category.cached(7)  # E: R | Miss is not R without narrowing
paths_from_main.cached(1)  # E: zero-argument function takes no lookup arguments
svc.get_category.prime("ok", "x")  # E: key type on prime

hit = svc.get_category.cached(7)
if not isinstance(hit, Miss):
    m: int = hit  # E: narrowed to str, so assigning to int is an error
'''


def _expected_error_lines(source: str) -> list[int]:
    """Return the 1-based line numbers carrying an ``# E:`` marker."""
    return [n for n, line in enumerate(source.splitlines(), start=1) if "# E:" in line]


@pytest.mark.skipif(shutil.which("mypy") is None, reason="mypy not installed")
def test_deliberate_misuse_is_reported(tmp_path: Path) -> None:
    """Every marked line errors, and nothing else does."""
    fixture = tmp_path / "memoize_misuse.py"
    fixture.write_text(MISUSE_SOURCE, encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--strict",
            "--python-version",
            "3.13",
            "--no-error-summary",
            "--no-incremental",
            str(fixture),
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    reported = {int(line.split(":")[1]) for line in result.stdout.splitlines() if ": error:" in line}
    expected = set(_expected_error_lines(MISUSE_SOURCE))

    missed = sorted(expected - reported)
    assert not missed, (
        f"mypy did not report these deliberate misuses: {missed}. "
        f"A line that stops erroring is a regression in the cache's typing, not a fix.\n{result.stdout}"
    )
    unexpected = sorted(reported - expected)
    assert not unexpected, f"mypy reported errors on unmarked lines {unexpected}:\n{result.stdout}"


@pytest.mark.skipif(shutil.which("mypy") is None, reason="mypy not installed")
def test_correct_use_type_checks_clean(tmp_path: Path) -> None:
    """The counterpart: the shapes the library and its consumer actually use are clean.

    Without this, the misuse test above would still pass if ``prime``/``cached`` rejected
    *everything*.
    """
    fixture = tmp_path / "memoize_correct.py"
    fixture.write_text(
        '''\
"""Correct uses of taxomesh.utils.memoize — must type-check clean."""

from taxomesh.utils.memoize import Miss, memoize


@memoize(ttl=5)
def paths_from_main() -> dict[int, str]:
    return {1: "a"}


@memoize(ttl=5)
def mosaic(*, count: int = 8) -> list[int]:
    return list(range(count))


class Service:
    @memoize(ttl=5)
    def get_category(self, category_id: int) -> str:
        return f"cat-{category_id}"

    def read_through(self, category_id: int) -> str:
        hit = self.get_category.cached(category_id)
        if isinstance(hit, Miss):
            value = f"cat-{category_id}"
            self.get_category.prime(value, category_id)
            return value
        return hit


paths_from_main.prime({2: "b"})
mosaic.prime([9], count=4)
Service.get_category.prime("primed", Service(), 1)
paths_from_main.clear_cache()
''',
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--python-version", "3.13", "--no-incremental", str(fixture)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout
