# Research: CLI Verbose Mode & List Enhancements

**Feature**: 005-cli-verbose  
**Date**: 2026-02-23

---

## Decision 1: `--verbose` optional-value semantics in Typer/Click

**Decision**: Use `verbose: int = typer.Option(0, "--verbose", is_flag=False, flag_value=1)` passed through to Click's `Option` constructor via Typer's `**kwargs` forwarding.

**Rationale**: Click's `flag_value` parameter, when combined with `is_flag=False`, gives the option a "fallback value" when the flag is used without an argument. Typer forwards unrecognised `typer.Option` kwargs to the underlying Click `Option` at registration time. This is confirmed by Typer's source code (`typer/params.py` passes `**kwargs` to `click.option()`). The result: `--verbose` alone → 1, `--verbose 0` → 0, `--verbose 2` → 2, omitted → 0.

**Fallback if `flag_value` is rejected at runtime**: Use `Optional[int] = typer.Option(None, "--verbose")` where `None` means "omitted (level 0)" and the implementation treats it as 0. In this case `--verbose` alone fails (Click error); the user must type `--verbose 1`. Acceptance tests will verify which path works; if `flag_value` fails, FR-001's "no value → 1" becomes `--verbose 1` and the spec assumption note is updated.

**Alternatives considered**:
- `count=True`: each `--verbose` adds 1 — incorrect semantics (cumulative count ≠ explicit level).
- Boolean `--verbose / --no-verbose` flag: collapses two numeric levels into bool — loses the future extensibility of levels > 1.
- Separate `--verbose-level N` option: verbose UX, defeats the purpose of a short flag.

---

## Decision 2: Context object structure (`ctx.obj`)

**Decision**: Change `ctx.obj` from `Path | None` to a plain `dict[str, Any]` with keys `config_path: Path | None` and `verbose: int`. Service construction remains lazy (inside each sub-command).

**Rationale**: A typed dataclass would require an import from `main.py` into `config.py` or vice versa. A `dict[str, Any]` is the Typer idiomatic pattern for shared state and avoids circular imports. mypy's `--strict` flag is satisfied by a narrow access helper `_verbose(ctx) -> int` that casts and returns the value. Service construction stays lazy to preserve the existing behaviour (no side effects on `--help`).

**Alternatives considered**:
- Typed `CliState` dataclass: cleaner typing, but adds a shared module for a two-field struct; overhead not justified.
- Eager service construction in root callback: triggers repository side effects (creates `taxomesh.json`) on `taxomesh category list --help`, which is a behaviour regression.

---

## Decision 3: New repository method name

**Decision**: `get_config_summary() -> str`

**Rationale**: Follows the existing `get_*` accessor naming convention in the protocol. `summary` communicates that the value is a concise, human-readable description, not a full structured configuration object. The name is unambiguous and distinct from `build_service`'s config-file concept.

**Alternatives considered**:
- `describe()`: too generic; does not signal configuration.
- `config_info()`: noun-verb ordering inconsistent with `get_*` pattern.
- `repository_info()`: redundant (method is already on the repository object).

---

## Decision 4: Verbose block output format

**Decision**: Three fixed-width labelled lines, printed to stdout before any sub-command output:

```
Repository  : JsonRepository
Config      : taxomesh.json
Config file : /abs/path/taxomesh.toml [not found]
```

When the config file exists, `[not found]` is omitted:

```
Repository  : JsonRepository
Config      : taxomesh.json
Config file : /abs/path/taxomesh.toml
```

The config file path is always the **absolute** resolved path so the user can locate it regardless of the working directory.

**Rationale**: Aligned labels make the three values scannable at a glance. Using `Path.resolve()` for the config file avoids confusion when the user invokes taxomesh from a different directory. `[not found]` follows the convention of diagnostic tools (e.g., `env: 'foo': No such file or directory`).

**Alternatives considered**:
- JSON output for verbose: verbose mode is a diagnostic convenience feature, not a machine-readable interface. Plain text is appropriate.
- Single-line format `JsonRepository @ taxomesh.json (config: taxomesh.toml)`: harder to read and parse visually.

---

## Decision 5: List header/footer format

**Decision**:

```
--- Categories ---
Category(name='Rock', ...)
Category(name='Jazz', ...)
--- Total: 2 ---
```

Empty list:

```
--- Categories ---
--- Total: 0 ---
```

Entity labels: `Categories`, `Items`, `Tags`.

**Rationale**: Dashes as separators are visually distinct from record lines, which are Pydantic `__repr__` strings. `Total:` is explicit enough that scripts parsing the output can grep for the count. The format is symmetric (opening and closing separators).

**Alternatives considered**:
- `=== Categories ===` / `=== 2 records ===`: equal signs are heavier visually; no advantage.
- No header, footer only: header helps identify which entity list is displayed when verbose block is also present.
- Separate `count:` field in JSON: out of scope; CLI is plain text.

---

## Decision 6: `build_service()` refactor → `BuildResult`

**Decision**: Rename/refactor `build_service()` in `config.py` to return a `BuildResult` dataclass:

```python
@dataclass
class BuildResult:
    service: TaxomeshService
    repository: JsonRepository          # concrete type; only JsonRepository exists
    config_file_path: Path              # resolved absolute path
    config_file_exists: bool
```

A module-level helper `build(config_path: Path | None) -> BuildResult` replaces the old `build_service()`. Each sub-command calls `build(ctx.obj["config_path"])` to get the result; if verbose >= 1 it calls `_print_verbose(result)` before issuing the command.

**Rationale**: The verbose block requires both the repository instance (for `get_config_summary()` and `type(repo).__name__`) and the config file metadata. Returning these from one function avoids building the service twice and keeps all startup logic in `config.py`.

**Composition-root exception (Principle I)**: `config.py` already imports `JsonRepository` directly (adapter → adapter coupling). This is inside the CLI adapter layer; no application → adapter import is introduced. The existing `build_service()` already had this coupling. No new constitution violation.

---

## Decision 7: Secrets contract enforcement

**Decision**: The `get_config_summary()` docstring and protocol definition state the no-secrets requirement as a **docstring contract**, not a runtime assertion. No automated secret detection is added.

**Rationale**: Runtime secret detection (regex scanning the returned string) would be fragile, maintenance-heavy, and outside the scope of a configuration summary method. The contract is enforced through code review and protocol documentation. `JsonRepository` only returns a file path — no secret can appear.

**Alternatives considered**:
- Runtime regex for passwords/tokens: false positives on legitimate path names, fragile.
- Separate `SanitisedStr` newtype: over-engineering for a string field on an internal protocol.
