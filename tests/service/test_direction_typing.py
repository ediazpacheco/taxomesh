"""``mypy --strict`` accepts a ``Direction`` member wherever a relation read takes a direction.

A ``StrEnum`` member equals its value at runtime, but a type checker does not accept a member where
a parameter is a ``Literal`` of the strings. Static typing is what a runtime test cannot check, so
this runs the type checker over a caller's code, as ``tests/utils/test_memoize_typing.py`` does.
"""

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

CALLER_SOURCE = '''\
"""A caller passing each direction as a member and as a string. Must type-check clean."""

from uuid import uuid4

from taxomesh import Direction, TaxomeshService

svc = TaxomeshService()
item_id = uuid4()

svc.items.list_relations(item_id, direction=Direction.OUTGOING)
svc.items.list_related(item_id, direction=Direction.INCOMING)
svc.items.get_many_related([item_id], direction=Direction.BOTH)
svc.items.list_relations(item_id, direction="both")
svc.items.list_related(item_id, direction="outgoing")
svc.items.get_many_related([item_id], direction="incoming")
'''


def test_a_direction_member_type_checks(tmp_path: Path) -> None:
    fixture = tmp_path / "direction_caller.py"
    fixture.write_text(CALLER_SOURCE, encoding="utf-8")

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

    assert result.returncode == 0, result.stdout
