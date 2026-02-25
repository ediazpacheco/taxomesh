# Data Model: taxomesh.toml Configuration Template

**Branch**: `008-toml-config-template` | **Date**: 2026-02-24

## Overview

This feature introduces no new domain entities (no `pydantic.BaseModel` subclasses). It adds one
new exception class and one new property to the existing `TaxomeshService` facade.

---

## Exception: TaxomeshConfigError

**Module**: `taxomesh/exceptions.py`
**Exported from**: `taxomesh/__init__.py`

```python
class TaxomeshConfigError(TaxomeshError):
    """Raised when a taxomesh.toml configuration file is invalid or specifies an unsupported option."""
```

**Hierarchy position**:

```
TaxomeshError
└── TaxomeshConfigError   ← new (direct child, not under ValidationError or RepositoryError)
```

**When raised**:
1. `tomllib.TOMLDecodeError` during `read_text()` → `TaxomeshConfigError` with chaining.
2. `OSError` / `PermissionError` during `read_text()` → `TaxomeshConfigError` with chaining.
3. Unsupported `type` value in `[repository]` section → `TaxomeshConfigError` (no underlying cause to chain).

**Not raised** for:
- Missing config file (silent fallback to the default backend — `TaxomeshService` is repository-agnostic at the config level).
- Unknown keys or sections in the config (silently ignored).

---

## Config document structure (parsed at runtime)

The in-memory representation after `tomllib.loads()` — not a stored entity:

```
config: dict[str, Any]
└── "repository": dict[str, Any]
    ├── "type": str     # "yaml" | "json"; default "yaml"
    └── "path": str     # file path; default "data/taxomesh.yaml" or "data/taxomesh.json"
```

**Path resolution**: `Path(path_str)` — relative paths resolve from CWD at
`TaxomeshService()` construction time (confirmed in clarifications).

---

## TaxomeshService extensions

### New keyword-only parameter

```python
config_path: Path | str | None = None
```

- When `None`: auto-discover `taxomesh.toml` from `Path.cwd() / "taxomesh.toml"`.
- When provided: resolve `Path(config_path)` (relative paths → CWD-relative).
- Ignored entirely when `repository` argument is not `None`.

### New property

```python
@property
def repository(self) -> TaxomeshRepositoryBase:
    """Return the active storage backend."""
```

Returns `self._repo` — the same instance that was set during `__init__`.

### New private static method

```python
@staticmethod
def _build_repo_from_config(
    config: dict[str, Any],
    config_path: Path,
) -> TaxomeshRepositoryBase:
```

- Reads `config["repository"]["type"]` and `config["repository"]["path"]`.
- Returns `YAMLRepository` or `JsonRepository` with the resolved path.
- Raises `TaxomeshConfigError` for unsupported `type`.
- Both adapter imports live inside this method (honoring composition-root exception).

---

## No domain model changes

`Item`, `Category`, `Tag`, `CategoryParentLink`, `ItemParentLink`, `ItemTagLink` are unchanged.
`TaxomeshGraph` and `CategoryNode` are unchanged.
