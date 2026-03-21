# Implementation Plan: External ID Clear Support

**Branch**: `043-clear-external-id` | **Date**: 2026-03-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/043-clear-external-id/spec.md`

## Summary

`TaxomeshService.update_item` and `update_category` currently use `None` to mean both "unchanged" and "clear this field", making it impossible to explicitly clear `external_id`. This change introduces a private typed sentinel `_UnsetType` / `_UNSET` so `None` means "clear" and an omitted argument means "unchanged". All repository backends already support persisting `None` correctly; only the service layer requires modification.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Pydantic v2 (domain models), stdlib `typing.Final`
**Storage**: JsonRepository (JSON file), YAMLRepository (YAML file), DjangoRepository (Django ORM) — **no changes required**
**Testing**: pytest with `tests/service/conftest.py` fixtures
**Target Platform**: Python library (any platform)
**Project Type**: Library
**Performance Goals**: No change — cache invalidation already happens on every write
**Constraints**: mypy `--strict` must pass; ruff clean; ≥ 80% test coverage
**Scale/Scope**: 1 modified file (`service.py`), 1 new test file

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Hexagonal Architecture | ✅ PASS | Change is entirely in `application/` layer. No adapter imports at module level. |
| II. TaxomeshService is single facade | ✅ PASS | Only `TaxomeshService.update_item` and `update_category` are modified. |
| III. Repository as Protocol | ✅ PASS | No protocol changes; sentinel is application-layer only. |
| IV. Pydantic + mypy strict | ✅ PASS | `_UnsetType` class produces a proper typed union `str \| None \| _UnsetType`; isinstance guard narrows correctly. |
| V. Custom Exception Hierarchy | ✅ PASS | No new exceptions. Existing `TaxomeshExternalIdConflictError` already handles the conflict case. |
| VI. DAG Integrity | ✅ PASS | No topology changes. |
| VII. Spec-Driven Development | ✅ PASS | This plan is driven by spec.md. |
| VIII. Quality Gates | ✅ PASS | New tests + all existing tests must pass; no exceptions to gate. |
| IX. Framework-Agnostic HTTP | ✅ PASS | No HTTP layer changes. |
| X. Named Constants | ✅ PASS | `_UNSET: Final[_UnsetType] = _UnsetType()` — named, Final-annotated, single definition. |
| XI. OO by Default | ✅ PASS | Sentinel is a class, not a bare `object()`. |

**No violations. No complexity tracking required.**

## Project Structure

### Documentation (this feature)

```text
specs/043-clear-external-id/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── contracts/
│   └── service-api.md  ← Phase 1 output
└── tasks.md             ← Phase 2 output (/speckit.tasks)
```

### Source Code (affected files only)

```text
taxomesh/
└── application/
    └── service.py       ← add _UnsetType + _UNSET; modify update_item + update_category

tests/
└── service/
    └── test_service_external_id_clear.py   ← new; 8 test scenarios
```

**Structure Decision**: Single-project layout (Option 1). Only `service.py` and a new test file are touched. No new modules required.

## Phase 0: Research

All unknowns resolved — see [research.md](research.md).

**Key findings**:

1. **Sentinel**: Use `_UnsetType` singleton class + `_UNSET: Final[_UnsetType]`. This is mypy `--strict` safe and satisfies Principles X and XI. A bare `object()` is not acceptable.

2. **Repository layer**: No changes. All three backends (`JsonRepository`, `YAMLRepository`, `DjangoRepository`) already persist `external_id = None` correctly. `check_external_id_unique` already skips validation for `None`.

3. **Cache**: No changes. `clear_all_caches()` is already called unconditionally at the end of both update methods — the stale-cache risk does not exist once the service-layer bug is fixed.

4. **Test location**: `tests/service/test_service_external_id_clear.py`. Existing `tests/service/conftest.py` provides the fixtures needed.

## Phase 1: Design & Contracts

### Data Model

See [data-model.md](data-model.md).

- Domain models (`Item`, `Category`): **unchanged** — `external_id: str | None` already defined.
- New application-layer construct: `_UnsetType` private singleton class.
- No schema migrations.

### Service Contracts

See [contracts/service-api.md](contracts/service-api.md).

**Three-state `external_id` semantics**:

| Caller passes | Old behaviour (bug) | New behaviour |
|---------------|---------------------|---------------|
| *(omitted)* | field unchanged ✅ | field unchanged ✅ |
| `None` | field unchanged ❌ | field cleared to None ✅ |
| `"string"` | field set ✅ | field set ✅ |

### Implementation Detail

**Step 1 — Add sentinel (top of `service.py`, after imports)**:

```python
class _UnsetType:
    """Singleton sentinel: distinguishes 'not provided' from None in update methods."""

_UNSET: Final[_UnsetType] = _UnsetType()
```

**Step 2 — Update `update_item` signature**:

```python
def update_item(
    self,
    item_id: UUID,
    enabled: bool | None = None,
    slug: str | None = None,
    name: str | None = None,
    external_id: str | None | _UnsetType = _UNSET,
    metadata: dict[str, Any] | None = None,
) -> Item:
```

**Step 3 — Update `update_item` logic** (replace the current `if external_id is not None:` guard):

```python
if not isinstance(external_id, _UnsetType):
    item.external_id = external_id
```

**Step 4 — Update `update_item` docstring** — add to `external_id` arg:

```
external_id: New external identifier. Omit to leave unchanged.
    Pass None to clear the field. Pass a string to set a new value.
```

**Step 5–8** — Repeat steps 2–4 for `update_category`.

### Agent Context Update

Run after this plan is committed: `.specify/scripts/bash/update-agent-context.sh claude`

## Implementation Sequence

Tasks are ordered: tests first (TDD), then implementation, then quality gates.

1. **T1 — Write failing tests** (`tests/service/test_service_external_id_clear.py`)
   - 4 item scenarios: clear, lookup-after-clear, reassignment, no-op
   - 4 category scenarios: same
   - Use the parametrized `service` fixture from `tests/service/conftest.py`
   - All 8 tests MUST fail (red) before T2

2. **T2 — Add `_UnsetType` sentinel to `service.py`**
   - Add class + `_UNSET: Final[_UnsetType]`
   - Update signatures and logic for both methods
   - Update docstrings

3. **T3 — Verify all 8 new tests pass (green)**

4. **T4 — Run full quality gate**
   ```bash
   ruff check .
   ruff format --check .
   mypy --strict .
   pytest --cov=taxomesh --cov-fail-under=80
   ```

5. **T5 — Run `/speckit.analyze`** — zero deviations required before PR.
