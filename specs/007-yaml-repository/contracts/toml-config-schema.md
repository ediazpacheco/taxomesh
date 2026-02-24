# Contract: taxomesh.toml Repository Configuration

**Applies to**: `taxomesh/adapters/cli/config.py` `build()` factory
**Date**: 2026-02-24

---

## Schema

```toml
[repository]
type = "yaml"          # "yaml" | "json"  — default: "yaml"
path = "taxomesh.yaml" # any file path    — default: "taxomesh.yaml"
```

---

## Behaviour Table

| `type` value | `path` value | Repository constructed | Default path if omitted |
|---|---|---|---|
| absent (no config file) | — | `YAMLRepository` | `taxomesh.yaml` |
| `"yaml"` | provided | `YAMLRepository(Path(path))` | `taxomesh.yaml` |
| `"yaml"` | absent | `YAMLRepository(Path("taxomesh.yaml"))` | — |
| `"json"` | provided | `JsonRepository(Path(path))` | `taxomesh.json` |
| `"json"` | absent | `JsonRepository(Path("taxomesh.json"))` | — |
| any other string | any | stderr error + `sys.exit(1)` | — |

---

## Error Conditions

| Condition | Output | Exit code |
|-----------|--------|-----------|
| Config file exists but not valid TOML | `Error: could not parse config file <path>: <detail>` to stderr | 1 |
| `type` is unrecognised value | `Error: unsupported repository type '<value>'. Supported: 'yaml', 'json'.` to stderr | 1 |
| Repository path is a directory | `Error: could not open repository: <detail>` to stderr | 1 |
| Repository YAML/JSON file is corrupt | `Error: could not open repository: <detail>` to stderr | 1 |

---

## CLI Verbose Output

When the `--verbose` flag is active, `build()` returns a `BuildResult` whose `repository` attribute is the constructed adapter. The CLI prints `result.repository.get_config_summary()` as the storage path line — for `YAMLRepository` this is the resolved YAML file path string.

---

## Default Constants (in config.py)

```python
_CONFIG_FILENAME    = "taxomesh.toml"
_DEFAULT_REPO_TYPE  = "yaml"           # changed from "json"
_DEFAULT_REPO_PATH  = "taxomesh.yaml"  # changed from "taxomesh.json"
```
