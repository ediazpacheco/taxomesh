# Data Model: CLI Config Dump

**Branch**: `014-cli-config-dump` | **Date**: 2026-02-28
**Amended**: 2026-02-28 — revised per FR-011 (no service init on --show-config)

No new domain entities are introduced by this feature. The feature is a read-only
CLI presentation concern that parses the TOML config file directly and produces a
formatted string output. `TaxomeshService` and `BuildResult` are NOT used.

---

## Existing Entities Used (read-only)

### None from domain or application layers

Per FR-011, `--show-config` does not construct `TaxomeshService` or any repository.
It reads the raw `taxomesh.toml` file (if present) using `tomllib` directly.

The only existing adapter constants consumed are:

| Constant | Module | Value | Used for |
|----------|--------|-------|---------|
| `DEFAULT_YAML_PATH` | `yaml_repository` | `Path("data/taxomesh.yaml")` | Default path when `type = "yaml"` and `path` absent |
| `DEFAULT_JSON_PATH` | `json_repository` | `Path("data/taxomesh.json")` | Default path when `type = "json"` and `path` absent |

---

## New Constructs Introduced

### CONFIG_KEYS (new constant — `taxomesh/adapters/cli/config.py`)

```python
CONFIG_KEYS: Final[list[str]] = [
    "repository.type",
    "repository.path",
]
```

- **Purpose**: Single authoritative list of all supported TOML configuration key names
  (dotted-path format). Every key in the `dump_config()` output MUST be present here.
- **Format**: Dotted-path strings matching the TOML hierarchy (`section.key`).
- **Invariant**: No config key name appears as a bare string literal in dump logic.

---

### _resolve_effective_config (new helper — `taxomesh/adapters/cli/config.py`)

```
_resolve_effective_config(config_path: Path | None) -> tuple[str, str]
```

- **Purpose**: Lightweight config resolution. Reads the TOML file at `config_path`
  (or auto-discovers `taxomesh.toml` from CWD if `None`). Extracts `[repository] type`
  and `[repository] path`, applying adapter-sourced defaults for any absent key.
- **Returns**: `(repo_type, repo_path)` — both plain strings; `repo_type` is one of
  `"yaml"`, `"json"`, `"django"`.
- **Side effects**: None. No `TaxomeshService`, no repository construction, no file writes.
- **Error behaviour**: Raises `TaxomeshConfigError` on malformed TOML or unreadable
  file (propagated to the caller, which handles it and exits non-zero).

**Resolution logic**:

| TOML state | `repo_type` result | `repo_path` result |
|------------|--------------------|--------------------|
| No config file (or empty) | `"yaml"` | `str(DEFAULT_YAML_PATH)` |
| `type = "yaml"`, no `path` | `"yaml"` | `str(DEFAULT_YAML_PATH)` |
| `type = "json"`, no `path` | `"json"` | `str(DEFAULT_JSON_PATH)` |
| `type = "yaml"`, `path = "custom.yaml"` | `"yaml"` | `"custom.yaml"` |
| `type = "json"`, `path = "custom.json"` | `"json"` | `"custom.json"` |
| `type` absent, `path` present | `"yaml"` | value from TOML |

---

### dump_config (new function — `taxomesh/adapters/cli/config.py`)

```
dump_config(repo_type: str, repo_path: str) -> str
```

- **Purpose**: Renders the effective configuration as an annotated TOML string.
  Pure function — no I/O, no side effects.
- **Returns**: A valid TOML string with comment blocks above each key covering all
  entries in `CONFIG_KEYS`.

---

### Effective Configuration (value, not a class)

Not modelled as a class. The "effective configuration" is the two-value tuple returned
by `_resolve_effective_config` and passed to `dump_config`.

| Logical Field | Source | Default (yaml) | Default (json) |
|---------------|--------|----------------|----------------|
| `repository.type` | TOML `[repository].type` (default `"yaml"`) | `"yaml"` | `"json"` |
| `repository.path` | TOML `[repository].path` (default from adapter constant) | `"data/taxomesh.yaml"` | `"data/taxomesh.json"` |
