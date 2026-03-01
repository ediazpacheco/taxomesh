# Research: CLI Config Dump

**Branch**: `014-cli-config-dump` | **Date**: 2026-02-28

No unknowns remain from the Technical Context — all clarifications were resolved
in the spec session. This document records the four design decisions made during
Phase 0 research so the rationale is preserved for future reference.

---

## Decision 1: Annotated TOML Generation Strategy

**Decision**: Hand-craft the TOML output as an f-string template inside `dump_config()`.

**Rationale**: TOML serialisation libraries (`tomli-w`, `tomllib`) do not support
comment injection. The config has exactly two settings in one section (`[repository]`).
An f-string template is the simplest correct approach and adds zero dependencies (KISS,
YAGNI). If the number of settings grows significantly in a future spec, this decision
should be revisited.

**Alternatives considered**:
- `tomli-w` — no comment support; rejected.
- `tomlkit` — supports comment-preserving round-trips but is a new runtime dependency
  for a two-setting output; rejected (YAGNI).
- `configparser` — INI-style, not TOML; rejected.

---

## Decision 2: Location of CONFIG_KEYS and dump_config()

**Decision**: Extend `taxomesh/adapters/cli/config.py` with the `CONFIG_KEYS` constant
and the `dump_config()` function.

**Rationale**: Both are CLI adapter concerns — they format adapter configuration for
display alongside `BuildResult` and `build()`, which already live in that module.
Adding a new file for ~30 lines of code would be over-engineering.

**Alternatives considered**:
- New `taxomesh/adapters/cli/config_dump.py` — unnecessary file split; rejected.
- `taxomesh/application/service.py` — wrong layer (application should not own CLI output
  format); violates constitution Principle I; rejected.
- `taxomesh/adapters/cli/main.py` — mixes dump logic with routing; rejected.

---

## Decision 3: Typer Early Exit Mechanism

**Decision**: Raise `typer.Exit()` inside the `main()` callback after printing the
dump when `--show-config` is `True`.

**Rationale**: This is Typer's own documented pattern for terminal flags (e.g. its
built-in `--version` flag uses the same mechanism). After `raise typer.Exit()`, no
subcommand is executed and Typer performs its normal cleanup.

**Alternatives considered**:
- `sys.exit(0)` — works but bypasses Typer's cleanup hooks; less idiomatic; rejected.
- `ctx.exit()` — equivalent to `raise typer.Exit()`; both are valid, `raise` form
  is cleaner since it requires no ctx threading.

---

## Decision 4: Reading Effective Config Values for the Dump

**⚠️ SUPERSEDED by spec clarification 2026-02-28 (FR-011).**

Original decision proposed using `BuildResult` + `TaxomeshService`. Rejected because
constructing `TaxomeshService` triggers `_ensure_root()`, which creates `data/taxomesh.yaml`
as a side effect — violating the principle that `--show-config` must not perform any
repository I/O.

---

## Decision 4 (revised): Lightweight TOML Parse in Callback

**Decision**: A new helper function `_resolve_effective_config(config_path: Path | None) -> tuple[str, str]`
in `taxomesh/adapters/cli/config.py` reads the TOML config file (if it exists) using
`tomllib`, extracts `type` and `path` from the `[repository]` section, applies adapter
defaults for absent keys, and returns `(type_str, path_str)`. The `main()` callback
calls this helper when `--show-config` is present, passes the result to `dump_config()`,
prints, and raises `typer.Exit()`. No `TaxomeshService`, no `build()`, no `_ensure_root()`.

**Path default selection**: When `path` is absent from the TOML:
- If `type == "yaml"` (or type absent) → import `DEFAULT_YAML_PATH` from `yaml_repository`
- If `type == "json"` → import `DEFAULT_JSON_PATH` from `json_repository`

This is the one place where importing adapter constants directly is required and correct
(the callback is already in the adapter layer; constitution Principle I is satisfied).

**Signature**:
```
dump_config(repo_type: str, repo_path: str) -> str
```

**Rationale**: Satisfies FR-011 (no service init, no storage I/O). Keeps the logic
minimal and testable — `_resolve_effective_config` can be unit-tested independently
of the CLI. The callback remains thin.

**Alternatives considered**:
- `BuildResult` approach (original Decision 4) — triggers `_ensure_root()`; creates data
  files on first run; violates spec FR-011; rejected.
- `TaxomeshService.get_effective_config() -> dict` — new public API with no benefit
  beyond the lightweight parse; rejected.
- Inlining the parse in `main()` callback directly — mixes routing with logic; rejected.

---

## Decision 5: CONFIG_KEYS Constant Format

**Decision**: `CONFIG_KEYS: Final[list[str]] = ["repository.type", "repository.path"]`
— dotted-path strings mirroring the TOML key hierarchy.

**Rationale**: Fully qualified dotted paths (e.g. `"repository.type"`) are unambiguous
even if future specs add a second top-level section. Leaf-only names (`"type"`, `"path"`)
could collide across sections.

**Alternatives considered**:
- Leaf-only names (`["type", "path"]`) — ambiguous if a future section adds a key
  with the same leaf name; rejected.
- Nested dict structure (`{"repository": ["type", "path"]}`) — harder to iterate;
  rejected.
- Enum — adds class overhead for a simple list of strings; rejected (KISS).

---

## Summary: No Unknowns Remain

All decisions recorded. Decision 4 revised post-clarification (2026-02-28) to use
lightweight TOML parse instead of BuildResult, satisfying FR-011 (no service init).
No NEEDS CLARIFICATION markers exist in spec or plan. Ready for implementation.
