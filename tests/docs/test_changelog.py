"""``CHANGELOG.md`` says what each release changed in a page a reader finishes.

A release section is the release's story, not its build log: what it is, what breaks and what
it adds, in at most ``RELEASE_BUDGET`` lines. The releases the file does not describe are on the
GitHub releases page, and the file links it.
"""

from tests.docs._reference import REPO_ROOT

CHANGELOG = REPO_ROOT / "CHANGELOG.md"
RELEASE_BUDGET = 150
RELEASES_PAGE = "https://github.com/ediazpacheco/taxomesh/releases"


def _release_sections() -> dict[str, int]:
    """Return each release heading with the number of lines its section spans."""
    sections: dict[str, int] = {}
    heading = ""
    for line in CHANGELOG.read_text(encoding="utf-8").splitlines():
        if line.startswith("## ["):
            heading = line
            sections[heading] = 0
        if heading:
            sections[heading] += 1
    return sections


def test_every_release_fits_its_budget() -> None:
    sections = _release_sections()
    over = {heading: lines for heading, lines in sections.items() if lines > RELEASE_BUDGET}

    assert sections, "CHANGELOG.md has no release section"
    assert not over, f"over the budget of {RELEASE_BUDGET} lines: {over}"


def test_the_earlier_releases_are_linked() -> None:
    assert f"]({RELEASES_PAGE})" in CHANGELOG.read_text(encoding="utf-8")
