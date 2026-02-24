# Data Model: CLI Verbose Mode & List Enhancements

**Feature**: 005-cli-verbose  
**Date**: 2026-02-23

---

## No New Domain Entities

This feature introduces no new Pydantic domain models. All changes are at the
ports layer (protocol extension) and the CLI adapter layer.

---

## Protocol Extension: `TaxomeshRepositoryBase.get_config_summary()`

### Location
`taxomesh/ports/repository.py`

### Signature
```python
def get_config_summary(self) -> str:
    """Return a human-readable, secrets-free summary of this repository's configuration.

    The returned string MUST NOT contain secrets, credentials, or passwords.
    Implementations are contractually required to sanitize or omit sensitive values.

    Returns:
        A non-empty string describing the repository's configuration.
        Must never raise; must never return an empty string.
    """
    ...
```

### Constraints
- Return type: `str` (non-empty, no newlines required)
- MUST NOT raise under any circumstances
- MUST NOT include secrets, passwords, tokens, or credentials
- MUST return a non-empty string

### `JsonRepository` Implementation
```python
def get_config_summary(self) -> str:
    """Return the configured JSON storage file path."""
    return str(self._path)
```

Returns the path as stored at construction time (not necessarily absolute). The CLI
layer is responsible for resolving and displaying the absolute path if needed.

---

## New Adapter Type: `BuildResult`

### Location
`taxomesh/adapters/cli/config.py`

### Definition
```python
from dataclasses import dataclass
from pathlib import Path
from taxomesh import TaxomeshService
from taxomesh.ports.repository import TaxomeshRepositoryBase

@dataclass
class BuildResult:
    service: TaxomeshService
    repository: TaxomeshRepositoryBase
    config_file_path: Path      # resolved absolute path to taxomesh.toml (or --config path)
    config_file_exists: bool    # True if the config file was found and loaded
```

### Purpose
Returned by the new `build()` function in `config.py`. Carries both the ready-to-use
`TaxomeshService` and the repository reference (needed for verbose output), plus
config file metadata (needed for FR-015).

### Notes
- `repository` is typed as `TaxomeshRepositoryBase` (Protocol) to allow any
  compliant implementation — including `InMemoryRepository` used in tests.
- `config_file_path` is always the **resolved** (absolute) path, even when the
  file does not exist. Computed as `Path(path).resolve()` before returning.

---

## Context Object: `ctx.obj` shape

### Current shape
```python
ctx.obj = config_path   # Path | None
```

### New shape
```python
ctx.obj = {
    "config_path": config_path,   # Path | None  — explicit --config value
    "verbose": verbose,           # int           — 0 or 1 (clamped)
}
```

### Access helpers in `main.py`
```python
def _verbose(ctx: typer.Context) -> int:
    state: dict[str, Any] = ctx.obj
    return min(int(state.get("verbose", 0)), 1)

def _config_path(ctx: typer.Context) -> Path | None:
    state: dict[str, Any] = ctx.obj
    value = state.get("config_path")
    return Path(value) if value is not None else None
```

Both helpers are private (`_`-prefixed). mypy `--strict` compliance is maintained
without `type: ignore` by using explicit `Path(value) if value is not None else None`.
