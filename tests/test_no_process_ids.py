"""No process in the product: the library and its tests say what the code does, not how it came to be.

A docstring or a comment under ``taxomesh/`` or ``tests/`` carries no ticket, task, requirement or
specification identifier, no planning label or file, and no history. History belongs to
``CHANGELOG.md``. Every text file under both directories is read, templates and the recorded
fixtures included, and a line matching any pattern below fails the build. No pattern finds every
account of a change written in plain words: review finds those. This file is the one exemption,
since it has to spell the patterns out.
"""

import re
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
SCANNED: Final[tuple[str, ...]] = ("taxomesh", "tests")
TEXT_SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".html", ".txt", ".json", ".typed"})
SKIPPED_DIRECTORIES: Final[frozenset[str]] = frozenset({"__pycache__"})

#: Each pattern beside a line it must match, so that an expression which matches nothing cannot
#: pass for a clean tree.
PATTERNS: Final[dict[str, tuple[str, str]]] = {
    "lettered identifier": (r"\b[A-Z]{1,3}-[A-Z]\d{1,3}\b", "as XY-Z4 asked"),
    "zero-padded identifier": (r"\b[A-Z]{1,3}-0\d{1,3}\b", "(QR-007)"),
    "one-letter identifier": (r"\b[A-Z]-\d{2,4}\b", "Q-77: the cache tests"),
    "task number": (r"\bT\d{3}[a-z]?\b", "see T512"),
    "story or criterion label": (r"\b(?:US|AC)\d\b", "(US4, AC7)"),
    "numbered label inside a name": (r"(?<=_)[a-z]{2}\d{1,3}(?![a-z\d])", "test_total_qa2"),
    "planning word and its number": (
        r"(?i:\b(?:phase|stage|round|ruling|session|sprint|spec|specification|feature|iteration|milestone|ticket"
        r"|task|story)s?)\s+(?:[A-Z]?\d+[a-z]?|[A-Z])\b",
        "done in sprint 7",
    ),
    "planning file": (r"(?i)\b(?:spec|plan|tasks|research|roadmap)\.md\b|\bspecs?/\d", "see plan.md"),
    "numbered slug": (r"\b0\d{2}-[a-z][a-z-]+", "(047-some-feature)"),
    "zero-padded number in brackets": (r"\(0\d{2}\)", "the batch reads (093)"),
    "zero-padded number as a heading": (r"(?<![\w.,+-])0\d{2}(?: —|:)", "093 — one query each"),
    "before or after a zero-padded number": (
        r"(?i)\b(?:before|after|since|until|in) 0\d{2}\b",
        "raised a 500 before 071",
    ),
    "previously": (r"(?i)\bpreviously\b", "it was previously private"),
    "formerly": (r"(?i)\bformerly\b", "formerly a list"),
    "used to be": (r"(?i)\bused to be\b", "the sentinel used to be private"),
    "renamed": (r"(?i)\b(?:was|were) renamed\b|\brenamed (?:from|to)\b", "renamed from get_tag"),
    "backward compatibility": (r"(?i)\bbackwards?[- ]compat", "for backward-compatible imports"),
    "pre-release version": (r"\b\d+\.\d+\.\d+(?:a|b|rc)\d+\b", "no counterpart in 0.3.0a2"),
}
COMPILED: Final[dict[str, re.Pattern[str]]] = {name: re.compile(pattern) for name, (pattern, _) in PATTERNS.items()}


def _text_files(top: str) -> list[Path]:
    """Return every text file under *top*, chosen by suffix, this file excepted."""
    return sorted(
        path
        for path in (REPO_ROOT / top).rglob("*")
        if path.is_file()
        and path.suffix in TEXT_SUFFIXES
        and not SKIPPED_DIRECTORIES.intersection(path.parts)
        and path != Path(__file__).resolve()
    )


def _offences(path: Path) -> list[str]:
    """Return one ``path:line: patterns: text`` entry for each line of *path* that matches a pattern."""
    offences = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        names = [name for name, pattern in COMPILED.items() if pattern.search(line)]
        if names:
            offences.append(f"{path.relative_to(REPO_ROOT)}:{number}: {', '.join(names)}: {line.strip()}")
    return offences


@pytest.mark.parametrize("name", PATTERNS)
def test_each_pattern_matches_its_sample(name: str) -> None:
    _, sample = PATTERNS[name]
    assert COMPILED[name].search(sample), f"{name!r} does not match its own sample {sample!r}"


def test_the_walk_reaches_every_kind_of_text_file() -> None:
    suffixes = {path.suffix for top in SCANNED for path in _text_files(top)}
    assert {".py", ".html", ".txt", ".json"} <= suffixes


@pytest.mark.parametrize("top", SCANNED)
def test_no_process_text(top: str) -> None:
    offences = [entry for path in _text_files(top) for entry in _offences(path)]
    assert not offences, f"{len(offences)} lines under {top}/ carry process text:\n" + "\n".join(offences)
