"""Each user documentation page fits its line budget.

A budget keeps a page a reference rather than a narrative: a signature is written once, and a rule
is stated where it applies. ``docs/cli.md`` is generated and ``docs/design.md`` is for
contributors, so neither has one.
"""

import pytest

from tests.docs._reference import REPO_ROOT

BUDGETS = {
    "README.md": 170,
    "docs/python-api.md": 700,
    "docs/http-api-integration.md": 170,
    "docs/django-integration.md": 120,
    "docs/repositories.md": 80,
    "docs/configuration.md": 40,
    "llms.txt": 150,
}


@pytest.mark.parametrize(("page", "budget"), BUDGETS.items(), ids=BUDGETS)
def test_page_fits_its_budget(page: str, budget: int) -> None:
    lines = len((REPO_ROOT / page).read_text(encoding="utf-8").splitlines())
    assert lines <= budget, f"{page} has {lines} lines, over its budget of {budget}"
