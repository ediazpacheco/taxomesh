"""Continuous integration runs with least privilege and pinned code, and vulnerabilities have a
private way in.

Each workflow sets read-only default permissions at its top level, so a job that needs more asks
for it by name. Each action is pinned to a full commit, with its release in a trailing comment so a
bump by hand knows where it stands: a tag can be moved, a commit cannot. The pre-commit hook runs
the ruff the development group installs, so a commit is linted and formatted as CI checks it.
"""

import re
import tomllib
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))
READ_ONLY = frozenset({"read", "none"})
PINNED_USE = re.compile(r"^\s*(?:- )?uses: [\w.-]+/[\w.-]+@[0-9a-f]{40} # v\d+(?:\.\d+)*$")
EMAIL_ADDRESS = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
RUFF_HOOKS = "https://github.com/astral-sh/ruff-pre-commit"
RUFF_FLOOR = re.compile(r"^ruff>=(?P<version>[\d.]+)$")


def test_the_workflows_are_found() -> None:
    assert WORKFLOWS, "no workflow under .github/workflows/"


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda path: path.name)
def test_the_default_permissions_are_read_only(workflow: Path) -> None:
    permissions = yaml.safe_load(workflow.read_text(encoding="utf-8")).get("permissions")

    assert isinstance(permissions, dict), f"{workflow.name} sets no top-level permissions"
    assert set(permissions.values()) <= READ_ONLY, f"{workflow.name} grants {permissions} by default"


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda path: path.name)
def test_every_action_is_pinned_to_a_commit(workflow: Path) -> None:
    uses = [line for line in workflow.read_text(encoding="utf-8").splitlines() if "uses:" in line]
    unpinned = [line.strip() for line in uses if not PINNED_USE.match(line)]

    assert uses, f"{workflow.name} uses no action"
    assert not unpinned, f"{workflow.name} uses actions not pinned to a commit: {unpinned}"


def test_the_security_policy_sends_a_reporter_to_an_email_address() -> None:
    policy = REPO_ROOT / "SECURITY.md"

    assert policy.is_file(), "SECURITY.md is missing"
    section = policy.read_text(encoding="utf-8").partition("## Reporting a vulnerability")[2]
    reporting = " ".join(section.split())
    assert EMAIL_ADDRESS.search(reporting), "the policy names no address to report to"
    assert "not in a public issue" in reporting


def test_pre_commit_runs_the_ruff_the_dev_group_installs() -> None:
    hooks = yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    (ruff,) = (repo for repo in hooks["repos"] if repo["repo"] == RUFF_HOOKS)
    dev = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["dependency-groups"]["dev"]
    (floor,) = (match["version"] for match in map(RUFF_FLOOR.match, dev) if match)

    assert ruff["rev"] == f"v{floor}"
