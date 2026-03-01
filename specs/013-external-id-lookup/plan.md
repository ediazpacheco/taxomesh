# Implementation Plan: External-ID Lookup & Assignable Categories (013)

**Branch**: `013-external-id-lookup` | **Date**: 2026-02-28 | **Spec**: `specs/013-external-id-lookup/spec.md`
**Input**: Feature specification from `/specs/013-external-id-lookup/spec.md`

## Summary

Expose two `TaxomeshService` façade methods — `get_items_by_external_id` and
`get_categories_by_external_id` — that let consumers bridge from their own identifiers to
taxomesh internal IDs. Extend `TaxomeshRepositoryBase` with corresponding protocol stubs
and implement them across all three backends (JSON, YAML, Django). `DjangoRepository` also
gains a non-protocol `assignable_categories_qs()` extra for Django admin autocomplete.

**Status**: Implementation complete. All 25 tasks marked `[X]`. Quality gates pass (ruff, mypy --strict, pytest 384 tests, 93.79% coverage).

---

## Technical Context

**Language/Version**: Python 3.11 (targets 3.11–3.13)
**Primary Dependencies**: Pydantic v2 (domain models, transitive via FastAPI), Typer ≥ 0.12, Rich ≥ 13.0, pyyaml ≥ 6.0, Django ≥ 4.2 (optional)
**Storage**: JsonRepository (JSON file), YAMLRepository (YAML file), DjangoRepository (Django ORM, optional)
**Testing**: pytest ≥ 8.0, pytest-cov ≥ 5.0, pytest-django ≥ 4.8
**Target Platform**: Python library (CPython 3.11–3.13, cross-platform)
**Project Type**: Library (pluggable taxonomy management)
**Performance Goals**: O(n) scan for file backends is acceptable at expected taxonomy scale (hundreds-to-thousands of entities); Django ORM filter is index-efficient.
**Constraints**: No new migrations; exact-type external_id matching; mypy --strict passes.
**Scale/Scope**: Small-to-medium taxonomy datasets; no streaming or pagination required.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Hexagonal Architecture | ✅ Pass | Root exclusion is at service layer; repo backends stay ignorant of root concept. One pre-existing justified violation: `django_repository.py` imports `ROOT_CATEGORY_NAME` from `service.py` (documented in D-004). |
| II. TaxomeshService Is Facade | ✅ Pass | Both lookup methods are on `TaxomeshService`. |
| III. Repository as Protocol | ✅ Pass | `TaxomeshRepositoryBase` extended with protocol stubs. |
| IV. Pydantic + mypy --strict | ✅ Pass | All new method return types are `list[Item]` / `list[Category]` / `Any`. |
| V. Custom Exception Hierarchy | ✅ Pass | FR-012 requires `TaxomeshRepositoryError` propagation; documented in docstrings. |
| VI. DAG Integrity | ✅ Pass | Lookup methods are read-only; no DAG mutations. |
| VII. Spec-Driven Development | ✅ Pass | This plan file exists. |
| VIII. Quality Gates | ✅ Pass | All gates pass at plan time (verified). |
| IX. Pluggable REST Views | N/A | No REST surface added this feature. |
| X. Named Constants | ✅ Pass | `ROOT_CATEGORY_NAME` from `service.py`; no magic `"__root__"` literals. |
| XI. OO by Default | ✅ Pass | All new methods belong to their respective classes. |

**Complexity Tracking** — one justified violation:

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| `django_repository.py` imports `ROOT_CATEGORY_NAME` from `application.service` (adapter → application) | `ROOT_CATEGORY_NAME` is defined once in `service.py` (Principle X — single source). Moving it would touch all usages. | Moving `ROOT_CATEGORY_NAME` to `domain.constants` is the clean long-term fix; deferred to future refactor as it has no correctness impact on this feature. |

---

## Project Structure

### Documentation (this feature)

```text
specs/013-external-id-lookup/
├── plan.md              ← This file
├── research.md          ← Phase 0 output (decisions D-001 through D-007)
├── data-model.md        ← Phase 1 output (entities + method table + root-exclusion rule)
├── quickstart.md        ← Phase 1 output (usage examples)
├── contracts/
│   └── orm-schema.md    ← Phase 1 output (ORM filter contracts)
└── tasks.md             ← Phase 2 output (task list; delta tasks added in D-007)
```

### Source Code (repository root)

```text
taxomesh/
├── ports/
│   └── repository.py            # TaxomeshRepositoryBase — protocol stubs [DONE]
├── application/
│   └── service.py               # get_items_by_external_id [DONE]
│                                # get_categories_by_external_id [DONE]
├── adapters/
│   └── repositories/
│       ├── json_repository.py   # list_items/categories_by_external_id [DONE]
│       ├── yaml_repository.py   # list_items/categories_by_external_id [DONE]
│       └── django_repository.py # list_items/categories_by_external_id + assignable_categories_qs [DONE]
└── contrib/
    └── django/
        └── models.py            # CategoryModel, ItemModel (no changes needed) [DONE]

tests/
├── service/
│   └── conftest.py              # InMemoryRepository with protocol methods [DONE]
├── test_service_external_id.py  # Service-layer tests [DONE; +1 test needed]
└── contrib/
    └── django/
        ├── test_assignable_categories_qs.py  # [DONE]
        └── test_django_repository.py         # [DONE]
```

---

## Phase 0: Research

All research decisions are recorded in `research.md`. No NEEDS CLARIFICATION items remain.

Key decisions:
- **D-001**: Python scan for JSON/YAML repos (in-memory dict, O(n), YAGNI-safe at expected scale)
- **D-002**: ORM `filter(external_id=external_id)` on a single `CharField` for DjangoRepository (no type discriminator — all external IDs are stored as `str`)
- **D-003**: `assignable_categories_qs()` is outside the protocol (Django-specific `QuerySet` return)
- **D-004**: `ROOT_CATEGORY_NAME` imported from `service.py` in `django_repository.py` (justified cross-layer — see Complexity Tracking)
- **D-005**: `assignable_categories_qs()` annotated `-> Any` (Django not resolvable by mypy)
- **D-006**: `InMemoryRepository` (test fixture) updated to satisfy updated protocol
- **D-007**: Root exclusion lives at service layer, not repository layer (see below)

---

## Phase 1: Design

### D-007 — Root exclusion in `get_categories_by_external_id` (post-clarification decision)

**Decision**: `TaxomeshService.get_categories_by_external_id` MUST filter out the root
category (`category_id == self._root_id`) from the list returned by the repository.

**Rationale**: The `__root__` category is an implementation detail. Every other
category-facing API — `get_graph()`, `assignable_categories_qs()` — already hides it.
Consistency requires `get_categories_by_external_id` to do the same. Crucially, the root
is stored with `external_id = ""` by default, so a call with `external_id=""` would
otherwise leak the root to consumers.

The filter belongs at the service layer (not the repository layer) because:
- The repository has no knowledge of the "root concept" (it just stores categories).
- `self._root_id` is maintained by the service, not the repository.
- All three backends (`JsonRepository`, `YAMLRepository`, `DjangoRepository`) would need
  identical workarounds if done at the repo level — service layer is the single point of truth.

**Implementation**: One-line change to `get_categories_by_external_id` in `service.py`:
```python
results = self._repo.list_categories_by_external_id(external_id)
return [cat for cat in results if cat.category_id != self._root_id]
```

---

### Interfaces / Contracts

See `contracts/orm-schema.md` — documents the ORM filter predicates for all three new
Django methods. No REST surface changes.

### Entity Summary

See `data-model.md`. No new entities. Additions:
- Two new protocol stubs on `TaxomeshRepositoryBase`.
- Two new service methods on `TaxomeshService`.
- One non-protocol extra on `DjangoRepository`.
- Root exclusion filter at service layer (D-007).

---

## Quality Gates

All gates verified at implementation completion:

```bash
uv run ruff check .          # ✅ no issues
uv run ruff format --check . # ✅ no reformats needed
uv run mypy --strict .       # ✅ no issues (60 source files)
uv run pytest --cov=taxomesh --cov-fail-under=80  # ✅ 384 passed, 93.79% coverage
```

---

## Verification Snippet

```python
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.json_repository import JsonRepository
from pathlib import Path
import tempfile

with tempfile.TemporaryDirectory() as d:
    svc = TaxomeshService(repository=JsonRepository(Path(d) / "t.json"))
    # Root must not appear when searching by its own external_id ("")
    assert svc.get_categories_by_external_id("") == []
    # Normal item lookup
    svc.create_item("my-entity-uuid")
    assert len(svc.get_items_by_external_id("my-entity-uuid")) == 1
print("OK")
```
