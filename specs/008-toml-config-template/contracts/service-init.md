# Contract: TaxomeshService public interface changes

**Feature**: `008-toml-config-template` | **Date**: 2026-02-24

## `TaxomeshService.__init__`

### Signature (updated)

```python
def __init__(
    self,
    repository: TaxomeshRepositoryBase | None = None,
    *,
    config_path: Path | str | None = None,
) -> None:
```

### Behaviour matrix

| `repository` | `config_path` | Config file exists? | Result |
|---|---|---|---|
| provided | any | any | Use `repository`; ignore `config_path` entirely |
| `None` | provided | yes | Parse file at `Path(config_path)`; construct repo from `[repository]` section |
| `None` | provided | no | Fall back to `YAMLRepository(Path("data/taxomesh.yaml"))` |
| `None` | `None` | yes (CWD) | Auto-discover `Path.cwd() / "taxomesh.toml"`; construct repo from it |
| `None` | `None` | no (CWD) | Fall back to `YAMLRepository(Path("data/taxomesh.yaml"))` |

### Raises

| Exception | Condition |
|---|---|
| `TaxomeshConfigError` | Config file exists but is invalid TOML (chains `tomllib.TOMLDecodeError`) |
| `TaxomeshConfigError` | Config file exists but OS read fails (chains `OSError` / `PermissionError`) |
| `TaxomeshConfigError` | `[repository].type` is not `"yaml"` or `"json"` |
| `TaxomeshRepositoryError` | Repository adapter raises on initialisation (propagates unchanged) |

### Path resolution

- `config_path` as `str` or `Path` — resolved as-is; relative paths are relative to CWD at
  construction time.
- `path` value inside the TOML `[repository]` section — same rule: relative to CWD at
  construction time, not to the config file's location.

---

## `TaxomeshService.repository` property

### Signature

```python
@property
def repository(self) -> TaxomeshRepositoryBase: ...
```

### Contract

- Always returns the same instance set during `__init__` (no re-construction on access).
- Never `None` — `__init__` always assigns `self._repo` before the property is accessible.
- Returns the *injected* repository when `repository` was passed to `__init__`.
- Returns the *config-constructed* repository when `config_path` or CWD auto-discovery was used.
- Returns the *default* `YAMLRepository` when no config file was found.

---

## Backward compatibility

All existing call sites are unaffected:

```python
# pre-existing — unchanged behaviour
TaxomeshService()                         # falls back to YAMLRepository (data/taxomesh.yaml) — no taxomesh.toml in test CWD
TaxomeshService(repository=my_repo)       # repository injected; config ignored
```

The `config_path` parameter is keyword-only — it cannot be passed positionally, so there is no
risk of accidentally breaking a call that passed a single positional argument.
