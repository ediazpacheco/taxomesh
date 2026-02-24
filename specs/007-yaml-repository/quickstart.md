# Quickstart: YAML Repository

**Branch**: `007-yaml-repository` | **Date**: 2026-02-24

---

## Scenario 1 — CLI with no config (new default)

```bash
# No taxomesh.toml needed — YAML is now the default
taxomesh category add --name "Animals"
taxomesh category add --name "Plants"
taxomesh item add --external-id "lion" --category-id <uuid>
taxomesh graph

# Storage is at ./taxomesh.yaml — open it with any text editor
cat taxomesh.yaml
```

Expected `taxomesh.yaml` content (snippet):
```yaml
categories:
  3fa85f64-5717-4562-b3fc-2c963f66afa6:
    category_id: 3fa85f64-5717-4562-b3fc-2c963f66afa6
    name: Animals
    description: null
...
```

---

## Scenario 2 — CLI with explicit YAML config

```toml
# taxomesh.toml
[repository]
type = "yaml"
path = "data/taxonomy.yaml"
```

```bash
taxomesh --verbose category list
# Output: Storage: data/taxonomy.yaml
```

---

## Scenario 3 — Backward compat: keep using JSON

```toml
# taxomesh.toml
[repository]
type = "json"
path = "taxomesh.json"
```

All existing JSON-backed data continues to work without change.

---

## Scenario 4 — Python library usage (YAMLRepository directly)

```python
from pathlib import Path
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.yaml_repository import YAMLRepository

# Explicit YAML backend
repo = YAMLRepository(Path("my_taxonomy.yaml"))
service = TaxomeshService(repository=repo)

animals = service.create_category(name="Animals")
lion = service.create_item(external_id="lion")
service.add_item_to_category(item_id=lion.item_id, category_id=animals.category_id, sort_index=0)

graph = service.get_graph()
print(graph.roots[0].category.name)  # "Animals"
```

> **Note**: `TaxomeshService()` called without a `repository` argument still defaults to
> `JsonRepository` (library API default, per taxomesh constitution Principle II).
> Pass `YAMLRepository` explicitly to use YAML from Python code.

---

## Scenario 5 — Load example data file

```python
from pathlib import Path
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.yaml_repository import YAMLRepository

# Load the bundled example taxonomy (clone the repo first)
repo = YAMLRepository(Path("examples/taxomesh_example.yaml"))
service = TaxomeshService(repository=repo)

graph = service.get_graph()
print(f"{len(graph.roots)} top-level categories")
```

---

## Test Scenarios (for contract verification)

### T1 — Round-trip persistence

```python
import tempfile
from pathlib import Path
from taxomesh.adapters.repositories.yaml_repository import YAMLRepository
from taxomesh.domain.models import Category
from uuid import uuid4

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "test.yaml"
    repo = YAMLRepository(path)
    cat = Category(category_id=uuid4(), name="Test", description=None)
    repo.save_category(cat)

    repo2 = YAMLRepository(path)
    assert repo2.list_categories() == [cat]
```

### T2 — Empty file treated as empty taxonomy

```python
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "empty.yaml"
    path.write_text("")
    repo = YAMLRepository(path)  # must not raise
    assert repo.list_categories() == []
```

### T3 — Invalid YAML raises TaxomeshRepositoryError

```python
from taxomesh.exceptions import TaxomeshRepositoryError
import pytest

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "bad.yaml"
    path.write_text(": invalid: yaml: {{{{")
    with pytest.raises(TaxomeshRepositoryError):
        YAMLRepository(path)
```

### T4 — CLI default uses taxomesh.yaml

```python
from typer.testing import CliRunner
from taxomesh.adapters.cli.main import app
from unittest.mock import patch

runner = CliRunner()
result = runner.invoke(app, ["--verbose", "category", "list"])
assert "taxomesh.yaml" in result.output
assert result.exit_code == 0
```
