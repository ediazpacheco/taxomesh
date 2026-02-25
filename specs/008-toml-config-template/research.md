# Research: taxomesh.toml Configuration Template

**Branch**: `008-toml-config-template` | **Date**: 2026-02-24

## Summary

No genuine unknowns existed at the start of this feature — all configuration keys and their
defaults were confirmed from `taxomesh/adapters/cli/config.py`. One decision was elevated from
implementation to a formal spec clarification during `/speckit.clarify`.

---

## Decision 1 — Relative `path` resolution base

**Question**: When `path` in `taxomesh.toml` is a relative string (e.g. `"data/taxonomy.yaml"`),
which directory is it resolved from?

**Decision**: CWD at `TaxomeshService()` construction time.

**Rationale**: Simplest, most predictable contract. Matches how the CLI previously resolved paths
(it runs from the user's project root, which is also the CWD when scripts call `TaxomeshService()`
directly). Avoids surprising behaviour where the resolved path depends on the location of the
config file rather than the process's working directory.

**Alternatives considered**:
- Directory containing the `taxomesh.toml` file — makes `path` relative to the config location.
  Rejected: creates surprising results when `config_path` is an absolute path pointing outside the
  project root (the resolved storage file would also land outside the project).
- Require absolute paths — rejected: too restrictive, breaks the common case of pointing to a
  local data directory.

**Spec impact**: FR-003 updated to document this contract explicitly.

---

## Decision 2 — OSError handling during config read

**Question**: When `taxomesh.toml` exists but `read_text()` raises an OS-level error (e.g.
`PermissionError`), what propagates to the caller?

**Decision**: Wrap in `TaxomeshConfigError` with exception chaining
(`raise TaxomeshConfigError(…) from exc`).

**Rationale**: Callers who want to handle any config-level failure catch a single exception type
(`TaxomeshConfigError`). Exception chaining preserves the full original traceback for debugging.
Without wrapping, a `PermissionError` leaks through and forces callers to catch both types.

**Alternatives considered**:
- Let `OSError` propagate raw — rejected: inconsistent; callers must catch two unrelated types.
- Wrap in `TaxomeshRepositoryError` — rejected: a read permission failure is a *config* failure
  (the repository hasn't been created yet), not a *storage* failure.

**Spec impact**: FR-011 updated to require `OSError` wrapping + chaining.

**Implementation impact**: `service.py` currently only catches `tomllib.TOMLDecodeError`. The
`read_text()` call must also be wrapped in a `try/except OSError` block.

---

## Decision 3 — Type-specific `path` defaults

**Question**: Should the default for `path` be a single universal value (`"taxomesh.yaml"`) or
depend on `type` (`"taxomesh.yaml"` for yaml, `"taxomesh.json"` for json)?

**Decision**: Type-specific defaults — `"taxomesh.yaml"` for `type = "yaml"`,
`"taxomesh.json"` for `type = "json"`.

**Rationale**: Using `"taxomesh.yaml"` as the default for a JSON repository would create a
`.yaml` extension file containing JSON data — confusing and technically wrong. The implementation
already uses type-specific defaults; the spec should match.

**Alternatives considered**:
- Universal default of `"taxomesh.yaml"` with required `path` when `type = "json"` — rejected:
  forces extra boilerplate for a common use case; inconsistent with YAML behaviour.

**Spec impact**: FR-003 updated with type-specific defaults.

---

## Confirmed key inventory

All supported `[repository]` keys confirmed from reading
`taxomesh/adapters/cli/config.py` (pre-refactor) and
`taxomesh/application/service.py` (post-refactor):

| Key | Section | Accepted values | Default |
|-----|---------|-----------------|---------|
| `type` | `[repository]` | `"yaml"`, `"json"` | `"yaml"` |
| `path` | `[repository]` | Any path string | `"data/taxomesh.yaml"` (yaml) / `"data/taxomesh.json"` (json) |

No other sections or keys exist or are planned in scope for this feature.
