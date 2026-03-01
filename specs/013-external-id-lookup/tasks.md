# Tasks: External-ID Lookup & Assignable Categories (013)

**Input**: Design documents from `/specs/013-external-id-lookup/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and
testing of each story. TDD is mandatory per project constitution.

**Status note**: Tasks T001–T021 were completed in a prior implementation iteration.
Tasks T022–T025 are the remaining delta introduced by the post-spec clarification session
(root exclusion in `get_categories_by_external_id`, FR-012 docstrings, acceptance test for
US2 scenario 5). These are the only open tasks.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm no project-level setup is needed — all infrastructure exists from spec 012.

- [X] T001 Verify no new dependencies, migrations, or schema changes are required (FR-009)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Extend `TaxomeshRepositoryBase` protocol and update the `InMemoryRepository` test
fixture so all downstream implementations and tests can be wired correctly.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Add `ExternalId` import and declare `list_items_by_external_id` + `list_categories_by_external_id` protocol stubs in `taxomesh/ports/repository.py`
- [X] T003 Add `ExternalId` import and implement both new protocol methods (Python scan) in `tests/service/conftest.py::InMemoryRepository` to satisfy mypy --strict

**Checkpoint**: Protocol updated and test fixture compliant — user story implementation can now begin.

---

## Phase 3: User Story 1 — Look Up Item by External ID (Priority: P1) 🎯 MVP

**Goal**: `TaxomeshService.get_items_by_external_id()` resolves items by consumer external ID
across all three repository backends.

**Independent Test**:
```python
svc = TaxomeshService()
item = svc.create_item("entity-uuid-1")
assert svc.get_items_by_external_id("entity-uuid-1") == [item]
assert svc.get_items_by_external_id("missing") == []
```

### Tests for User Story 1

- [X] T004 [P] [US1] Write service-layer tests for `get_items_by_external_id` (str, int, UUID, not-found, empty store, multiple matches) in `tests/test_service_external_id.py`

### Implementation for User Story 1

- [X] T005 [P] [US1] Implement `list_items_by_external_id` (Python scan) in `taxomesh/adapters/repositories/yaml_repository.py`
- [X] T006 [P] [US1] Implement `list_items_by_external_id` (Python scan) in `taxomesh/adapters/repositories/json_repository.py`
- [X] T007 [P] [US1] Implement `list_items_by_external_id` (ORM `filter(external_id=external_id)` on `CharField`) in `taxomesh/adapters/repositories/django_repository.py`
- [X] T008 [US1] Add `get_items_by_external_id` pass-through method with orphan/duplicate docstring to `taxomesh/application/service.py`

**Checkpoint**: User Story 1 fully functional — `get_items_by_external_id` works on JSON, YAML,
and Django backends.

---

## Phase 4: User Story 2 — Look Up Category by External ID (Priority: P1)

**Goal**: `TaxomeshService.get_categories_by_external_id()` resolves categories by consumer
external ID across all three repository backends, excluding the `__root__` category from all
results (D-007 / FR-002 clarification).

**Independent Test**:
```python
cat = Category(category_id=uuid4(), name="Electronics", external_id="ext-cats-1")
svc.repository.save_category(cat)
assert svc.get_categories_by_external_id("ext-cats-1") == [cat]
assert svc.get_categories_by_external_id("nonexistent") == []
assert svc.get_categories_by_external_id("") == []  # root excluded even when external_id matches
```

### Tests for User Story 2

- [X] T009 [P] [US2] Write service-layer tests for `get_categories_by_external_id` (str, int, UUID, not-found, root-only store, multiple matches) in `tests/test_service_external_id.py`
- [X] T022 [US2] Write failing test `test_get_categories_by_external_id_root_not_returned_for_empty_string` in `tests/test_service_external_id.py` — asserts `svc.get_categories_by_external_id("") == []` (root excluded even when its external_id matches the query); this test MUST fail before T023 is implemented

### Implementation for User Story 2

- [X] T010 [P] [US2] Implement `list_categories_by_external_id` (Python scan) in `taxomesh/adapters/repositories/yaml_repository.py`
- [X] T011 [P] [US2] Implement `list_categories_by_external_id` (Python scan) in `taxomesh/adapters/repositories/json_repository.py`
- [X] T012 [P] [US2] Implement `list_categories_by_external_id` (ORM `filter(external_id=external_id)` on `CharField`) in `taxomesh/adapters/repositories/django_repository.py`
- [X] T013 [US2] Add `get_categories_by_external_id` pass-through method with orphan/duplicate docstring to `taxomesh/application/service.py`
- [X] T023 [US2] Add root-exclusion filter to `get_categories_by_external_id` in `taxomesh/application/service.py`: replace `return self._repo.list_categories_by_external_id(external_id)` with `results = self._repo.list_categories_by_external_id(external_id); return [cat for cat in results if cat.category_id != self._root_id]` (requires T022 to fail first per TDD)

**Checkpoint**: User Stories 1 AND 2 both functional — full external-ID bridge available.
Root category is never returned to consumers from category lookup.

---

## Phase 5: User Story 3 — Assignable Categories for Admin Autocomplete (Priority: P2)

**Goal**: `DjangoRepository.assignable_categories_qs()` returns a lazy ORM queryset of enabled,
non-`__root__` categories suitable for Django admin autocomplete widgets.

**Independent Test**:
```python
repo = DjangoRepository()
qs = repo.assignable_categories_qs()
assert "__root__" not in qs.values_list("name", flat=True)
# qs supports chaining:
filtered = qs.filter(name="Electronics")
```

### Tests for User Story 3

- [X] T014 [US3] Write Django integration tests for `assignable_categories_qs()` (enabled filter, root exclusion, disabled exclusion, empty store, queryset chainability) in `tests/contrib/django/test_assignable_categories_qs.py`

### Implementation for User Story 3

- [X] T015 [US3] Add `from typing import Any` and `from taxomesh.application.service import ROOT_CATEGORY_NAME` imports to `taxomesh/adapters/repositories/django_repository.py`
- [X] T016 [US3] Implement `assignable_categories_qs() -> Any` method (filter `enabled=True`, exclude `name=ROOT_CATEGORY_NAME`, wrap `DatabaseError` → `TaxomeshRepositoryError`) in `taxomesh/adapters/repositories/django_repository.py`

**Checkpoint**: All three user stories independently functional and tested.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: FR-012 docstring compliance and quality gate verification.

- [X] T024 [P] Add `Raises: TaxomeshRepositoryError: If the underlying repository raises it.` to the docstrings of both `get_items_by_external_id` and `get_categories_by_external_id` in `taxomesh/application/service.py` (FR-012 compliance)
- [X] T017 [P] Run `ruff check .` and fix any lint errors (unused imports, etc.)
- [X] T018 [P] Run `ruff format --check .` and fix any formatting issues
- [X] T019 Run `mypy --strict .` — ensure `InMemoryRepository` satisfies updated protocol and `assignable_categories_qs()` `-> Any` annotation is valid under strict mode
- [X] T020 Run `pytest --cov=taxomesh --cov-fail-under=80` — all tests pass, coverage ≥ 80%
- [X] T025 Run `pytest --cov=taxomesh --cov-fail-under=80` after T022–T024 are complete — confirm T022's new test passes and all 386+ tests are green
- [X] T021 Validate smoke-test scenario from `specs/013-external-id-lookup/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately ✅ DONE
- **Foundational (Phase 2)**: Depends on Phase 1 ✅ DONE
- **User Story 1 (Phase 3)**: Depends on Phase 2 completion ✅ DONE
- **User Story 2 (Phase 4)**: Depends on Phase 2 completion — T022 → T023 are the open tasks
- **User Story 3 (Phase 5)**: Depends on Phase 2 completion ✅ DONE
- **Polish (Phase 6)**: T024 can run in parallel with T022/T023; T025 waits for T022–T024

### Open Task Execution Order

```
T022 (write failing test)
  ↓
T023 (implement root exclusion fix)  ←→  T024 (add Raises docstrings) [parallel]
  ↓
T025 (quality gate verification)
```

### User Story Dependencies

- **US1**: Complete ✅
- **US2**: T022 → T023 remaining (root-exclusion delta from post-spec clarification)
- **US3**: Complete ✅

### Within US2 Delta

- T022 MUST be written and confirmed to FAIL before T023 begins (TDD rule)
- T023 is the single-line implementation that makes T022 pass
- T024 is independent (docstring only) — may be done in any order with T022/T023

---

## Parallel Opportunities

### Open tasks (T022–T025)

```
Parallel group A (independent concerns):
  T022: tests/test_service_external_id.py — write failing test
  T024: taxomesh/application/service.py — add Raises docstrings

Sequential after T022:
  T023: taxomesh/application/service.py — root exclusion fix

After T022 + T023 + T024:
  T025: run full quality gate
```

---

## Implementation Strategy

### Remaining Work (Delta Only)

All foundational work and user-story implementations are complete. The only open items are:

1. **T022** — Write the failing test first (US2 acceptance scenario 5):
   ```python
   def test_get_categories_by_external_id_root_not_returned_for_empty_string(
       svc: TaxomeshService,
   ) -> None:
       """Root category is not returned even when searching by its own external_id ('')."""
       results = svc.get_categories_by_external_id("")
       assert results == []
   ```
   Run `pytest tests/test_service_external_id.py` — this test MUST fail at this point.

2. **T023** — Apply the one-line fix in `service.py`:
   ```python
   # Before (T013 implementation — no root exclusion):
   return self._repo.list_categories_by_external_id(external_id)

   # After (T023 fix — root excluded):
   results = self._repo.list_categories_by_external_id(external_id)
   return [cat for cat in results if cat.category_id != self._root_id]
   ```
   Run `pytest tests/test_service_external_id.py` — T022's test must now pass.

3. **T024** — Add `Raises:` section to both service method docstrings (FR-012):
   ```python
   Raises:
       TaxomeshRepositoryError: If the underlying repository raises it.
   ```

4. **T025** — Final quality gate:
   ```bash
   uv run ruff check .
   uv run ruff format --check .
   uv run mypy --strict .
   uv run pytest --cov=taxomesh --cov-fail-under=80
   ```

---

## Notes

- [P] tasks operate on different files with no shared state — safe to parallelize
- TDD is mandatory per constitution: T022 must precede T023 and must FAIL before T023 starts
- T024 is a docstring-only change — no logic impact, safe to parallel with T022/T023
- The root exclusion (T023) uses `self._root_id` which is already available on the service instance
- No repository backends need modification — root exclusion is purely at the service layer (D-007)
- `ROOT_CATEGORY_NAME` lives in `service.py` — D-004 documents the justified cross-layer import
- `assignable_categories_qs()` returns `Any` not `QuerySet` because Django is an optional dep
  and `mypy --strict` cannot resolve the Django type at check time (see D-005)
