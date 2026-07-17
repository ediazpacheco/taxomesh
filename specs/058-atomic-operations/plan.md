# Implementation Plan: Atomic Multi-Write Service Operations

**Branch**: `058-atomic-operations` | **Date**: 2026-07-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/058-atomic-operations/spec.md`

## Summary

Five `TaxomeshService` operations perform more than one repository write with no
unit-of-work around them (`create_category`, `reorder_subcategories`,
`reorder_items_in_category`, `reparent_category`, `reparent_item`). A
mid-operation failure can persist a partial result — e.g. a category with no
parent link (an orphan). The fix adds one method to the repository port,
`atomic() -> AbstractContextManager[None]`, and wraps each of the five
operations in `with self._repo.atomic():`.

- **DjangoRepository** returns `transaction.atomic(using=self._using)`. The
  existing per-method `transaction.atomic` blocks nest as savepoints under the
  outer block and roll back together.
- **JsonRepository / YAMLRepository / InMemoryRepository** return
  `contextlib.nullcontext()` — a documented best-effort no-op.
- Any **raw** (non-`TaxomeshError`) exception escaping an affected operation is
  re-raised as `TaxomeshRepositoryError` chaining the original; existing
  `TaxomeshError` subclasses propagate unchanged. No new exception class.

Scope is strictly operation-level (L2) atomicity over taxomesh's own data. No
unit-of-work/session/batch abstraction; `atomic()` is the only new port method.

## Technical Context

**Language/Version**: Python 3.11 (targets 3.11–3.14)
**Primary Dependencies**: Pydantic v2 (domain models), Django ≥ 6.0 (optional adapter — transactional backend), pyyaml ≥ 6.0 (YAML adapter); stdlib `contextlib` (nullcontext / `AbstractContextManager`)
**Storage**: JsonRepository (JSON file), YAMLRepository (YAML file), DjangoRepository (Django ORM), InMemoryRepository (test fixture)
**Testing**: pytest, pytest-cov, pytest-django (for the Django rollback tests)
**Target Platform**: Library (imported by consuming apps/CLIs)
**Project Type**: Single library (hexagonal: domain / ports / application / adapters)
**Performance Goals**: No regression; `atomic()` adds one context-manager entry/exit per affected operation (negligible)
**Constraints**: mypy `--strict`; ruff line length 119; pytest coverage ≥ 80%; domain layer keeps zero outward deps
**Scale/Scope**: 1 new port method; 4 adapter implementations (+ test doubles); 5 service call-sites wrapped; failure-injection test suite

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Hexagonal — dependency direction | ✅ Pass | `atomic()` is a **port** method; the service depends on the port, adapters implement it. No new outward import in domain/application. `contextlib` is stdlib. |
| II. TaxomeshService single facade | ✅ Pass | No new public entry point; the five methods keep their signatures and return types. |
| III. Repository as Protocol | ✅ Pass | One method added to `TaxomeshRepositoryBase`; structural compliance verified by mypy. All backends implement it. |
| IV. Pydantic + mypy strict | ✅ Pass | No model changes. Return type annotated `AbstractContextManager[None]`; Django's untyped `transaction.atomic` handled with a localized `# type: ignore` at the return, consistent with existing Django-import ignores. |
| V. Exception hierarchy | ✅ Pass | Reuses existing `TaxomeshRepositoryError`; no new exception. (Principle V's diagram is illustrative — `TaxomeshRootCategoryError`/`TaxomeshRelationError` already live outside it — so no amendment needed regardless.) |
| VI. DAG integrity in domain | ✅ Pass | `reparent_category` still calls `add_category_parent` (domain cycle detection) inside the boundary; logic unchanged. |
| VII. Spec-driven | ✅ Pass | This plan follows an approved spec + clarify. |
| VIII. Quality gates | ✅ Pass | ruff / ruff format / mypy --strict / pytest ≥ 80% all in scope. |
| IX. Framework-agnostic contrib.api | ✅ Pass | Untouched. `TaxomeshRepositoryError` already maps to HTTP 500 in `contrib/api/errors.py`; no mapping change. |
| X. Named constants | ✅ Pass | No new magic literals; `contextlib.nullcontext()` needs none. |
| XI. Object-oriented | ✅ Pass | `atomic()` is an instance method on each adapter class. |
| Docstrings (Google style) | ✅ Pass | `atomic()` gets a module/port docstring documenting the two-tier guarantee (satisfies FR-008); each adapter override documents its backend's behavior. |

**Result**: PASS — no violations, Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/058-atomic-operations/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── repository-atomic.md   # Port contract for atomic()
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit.tasks output
```

### Source Code (repository root)

```text
taxomesh/
├── ports/
│   └── repository.py                     # + atomic() on TaxomeshRepositoryBase
├── application/
│   └── service.py                        # wrap 5 operations in `with self._repo.atomic():`
└── adapters/
    └── repositories/
        ├── django_repository.py          # atomic() -> transaction.atomic(using=self._using)
        ├── json_repository.py            # atomic() -> contextlib.nullcontext()
        └── yaml_repository.py            # atomic() -> contextlib.nullcontext()

tests/
├── service/
│   ├── conftest.py                       # InMemoryRepository gains atomic(); + failure-injection double
│   ├── test_atomic_operations.py         # NEW — failure-injection tests (all 5 ops)
│   └── ... (existing service tests must stay green)
└── adapters/
    └── ... (any test double passed to TaxomeshService needs atomic())
```

**Structure Decision**: Single-library hexagonal layout (existing). The change
touches exactly one port, three production adapters, one service module, and the
test doubles. No new package or module is introduced.

## Design Decisions (resolved via /speckit.clarify + planning Q&A)

1. **Mechanism**: single port method `def atomic(self) -> AbstractContextManager[None]: ...`.
   Callers use `with self._repo.atomic():`. No batch/composite/session API.
2. **Boundary scope + error contract**: the `with self._repo.atomic():` block
   and its `try/except` enclose the **write sequence only** — pre-write
   validation, existence checks, reads, and `pydantic` model construction stay
   **outside** the boundary. This is required: `create_category` raises
   `pydantic.ValidationError` and `reorder_subcategories`/
   `reorder_items_in_category` raise builtin `ValueError` during pre-write
   validation; wrapping those would convert them to `TaxomeshRepositoryError` and
   break documented `Raises:` contracts + existing tests (FR-007 / US2). Within
   the write phase, a **raw** (non-`TaxomeshError`) escaping exception is
   re-raised as `TaxomeshRepositoryError` chaining the original; existing
   `TaxomeshError` subclasses propagate unchanged. See research.md Decision 4 for
   the per-method table of what goes inside the boundary.
3. **Django nesting**: keep the inner per-method `transaction.atomic` blocks;
   they become savepoints under the outer block. Verified against Django's
   documented nested-atomic (savepoint) semantics in Phase 0.
4. **Best-effort backends**: `contextlib.nullcontext()` for JSON/YAML/in-memory;
   documented as a per-adapter limitation in each `atomic()` docstring (FR-008).
5. **Cache invalidation** (`clear_all_caches()`, corpus reset) stays **after** the
   `with` block on the success path, so it is unaffected by rollback and is not
   reached when the operation fails.

## Complexity Tracking

No constitution violations — section intentionally empty.
