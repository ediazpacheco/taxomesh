# Quickstart: taxomesh.toml Configuration Template

**Branch**: `008-toml-config-template` | **Date**: 2026-02-24

## Using the config template (CLI)

```bash
# 1. Copy the template to your project root
cp taxomesh.toml.example taxomesh.toml

# 2. Edit to taste — e.g. change the storage path
#    (all settings are documented inline; no external docs needed)
nano taxomesh.toml

# 3. Run any CLI command — it picks up taxomesh.toml automatically
taxomesh category list

# Override the config file location per-invocation
taxomesh --config /path/to/other.toml category list
```

---

## Using the config via Python API

### Auto-discovery (no arguments needed)

```python
from taxomesh import TaxomeshService

# Reads taxomesh.toml from CWD if present; falls back to JsonRepository otherwise
svc = TaxomeshService()
print(type(svc.repository).__name__)   # YAMLRepository (if taxomesh.toml present)
                                        # YAMLRepository at data/taxomesh.yaml  (if no config file)
```

### Explicit config path

```python
from taxomesh import TaxomeshService

svc = TaxomeshService(config_path="path/to/taxomesh.toml")
# or with an absolute Path
from pathlib import Path
svc = TaxomeshService(config_path=Path("/etc/myapp/taxomesh.toml"))
```

### Bypass config — explicit repository

```python
from pathlib import Path
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.yaml_repository import YAMLRepository

svc = TaxomeshService(repository=YAMLRepository(Path("data/taxonomy.yaml")))
# config_path is ignored entirely when repository is provided
```

### Inspect the active backend

```python
svc = TaxomeshService(config_path="taxomesh.toml")
print(svc.repository)                    # e.g. YAMLRepository(path=PosixPath('taxomesh.yaml'))
print(type(svc.repository).__name__)     # YAMLRepository
```

---

## Handling config errors

```python
from taxomesh import TaxomeshService
from taxomesh.exceptions import TaxomeshConfigError, TaxomeshRepositoryError

try:
    svc = TaxomeshService(config_path="taxomesh.toml")
except TaxomeshConfigError as exc:
    # Invalid TOML syntax, unsupported type, or OS read error
    # exc.__cause__ carries the original exception
    print(f"Config problem: {exc}")
except TaxomeshRepositoryError as exc:
    # Repository adapter failed to initialise (e.g. bad path permissions on data file)
    print(f"Storage problem: {exc}")
```

---

## Minimal taxomesh.toml examples

```toml
# YAML backend (default when no taxomesh.toml present)
[repository]
type = "yaml"
path = "data/taxomesh.yaml"
```

```toml
# JSON backend
[repository]
type = "json"
path = "data/taxonomy.json"
```

For the full reference — every accepted value, default, and both backend examples — see
[`taxomesh.toml.example`](../../taxomesh.toml.example) at the repository root.
