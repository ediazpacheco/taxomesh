"""Two services built at the same moment over one new YAML or JSON store store one implicit root.

A host that starts several threads at once may build a service on each, over one repository. The
build reads the store and, when it finds no implicit root, reads it again inside one ``atomic()``
block, which holds the repository's lock, and stores the root only if it is still absent. So the
second build finds the root that the first one stored, and both services show the same top level.
``_root_race.py`` holds the schedule that makes both builds read the empty store first.
"""

from pathlib import Path
from typing import Literal

import pytest

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YamlRepository
from tests.service._root_race import FIRST, SECOND, start_together


@pytest.mark.parametrize("kind", ["json", "yaml"])
def test_two_services_built_at_the_same_moment_store_one_root(kind: Literal["json", "yaml"], tmp_path: Path) -> None:
    path = tmp_path / f"store.{kind}"
    if kind == "json":
        shared_json = JsonRepository(path)
        outcome = start_together(JsonRepository, lambda: shared_json, lambda: JsonRepository(path))
    else:
        shared_yaml = YamlRepository(path)
        outcome = start_together(YamlRepository, lambda: shared_yaml, lambda: YamlRepository(path))

    both = sorted([FIRST, SECOND])
    assert outcome == {"roots": 1, "first": both, "second": both, "listed": both, "errors": []}
