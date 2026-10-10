"""No process in the product: the library and its tests say what the code does, not how it came to be.

A docstring or a comment under ``taxomesh/`` or ``tests/`` carries no task, requirement, spec or
finding identifier, no history and no citation of the governance text. History belongs to
``CHANGELOG.md``. Every text file under both directories is read, templates and the recorded
fixtures included, and a line matching any pattern below fails the build. This file is the one
exemption, since it has to spell the patterns out.
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
    "task": (r"\bT\d{3}[a-z]?\b", "see T180"),
    "requirement": (r"\bFR-\d", "(FR-012)"),
    "non-functional requirement": (r"\bNFR-\d", "(NFR-008)"),
    "success criterion": (r"\bSC-\d", "the bytes SC-009 pins"),
    "finding": (r"\bJ-[BSC]\d", "closes J-B6"),
    "short finding": (r"\b[GEF]\d{1,2}\b", "fixes G1"),
    "user story": (r"\bUS\d", "(US1 + US3)"),
    "acceptance criterion": (r"\bAC\d\b", "meets AC2"),
    "phase": (r"\bPhase \d+\b", "Phase 11"),
    "spec number": (r"(?i)\bspecs? ?\d{3}\b|specs/\d{3}", "introduced in spec 034"),
    "spec slug": (r"\b0\d{2}-[a-z][a-z-]+", "(062-container-api)"),
    "research note": (r"research\.md", "(research.md R2)"),
    "research decision": (r"\bR\d{2}\b", "as R14 decided"),
    "analyze run": (r"(?i)analyze run", "the twentieth analyze run"),
    "previously": (r"(?i)\bpreviously\b", "it was previously private"),
    "formerly": (r"(?i)\bformerly\b", "formerly a list"),
    "used to be": (r"(?i)\bused to be\b", "the sentinel used to be private"),
    "renamed": (r"(?i)\b(?:was|were) renamed\b|\brenamed (?:from|to)\b", "renamed from get_tag"),
    "backward compatibility": (r"(?i)\bbackwards?[- ]compat", "for backward-compatible imports"),
    "release": (r"\b0\.\d+\.\d+a\d+\b", "no counterpart in 0.1.0a50"),
    "added in a spec": (r"(?i)\b(?:added|introduced|removed) in (?:spec )?0\d{2}\b", "(removed in 025)"),
    "constitution": (r"(?i)\bconstitution\b", "(Constitution II)"),
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
