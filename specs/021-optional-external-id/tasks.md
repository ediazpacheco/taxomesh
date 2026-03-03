# Tasks: Optional Item external_id

**Input**: Design documents from `specs/021-optional-external-id/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, quickstart.md ✅

**Tests**: TDD is mandatory per project constitution. Test tasks appear before their implementation tasks in every phase. Verify each test **fails** before writing the implementation.

**Organization**: Two user stories. US2 (domain/service/CLI layer) is implemented before US1 (Django layer) because US1 depends on the domain model fix.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: User story label (US1 = Django admin fix, US2 = domain model fix)

---

## Phase 1: Setup

*No project initialization required — taxomesh is an established project.*

---

## Phase 2: Foundational (Blocking Prerequisite)

**Purpose**: Add `DEFAULT_ITEM_EXTERNAL_ID` constant. Every subsequent task imports or depends on this value.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T001 Add `DEFAULT_ITEM_EXTERNAL_ID: Final[str] = ""` constant to `taxomesh/domain/constants.py` with an inline comment explaining it is the "no external reference" sentinel
- [X] T002 Add `test_default_item_external_id_is_empty_string` to `tests/domain/test_constants.py` — assert the constant equals `""`; run the test to confirm it passes (constant is non-code, so test is written after)

**Checkpoint**: `DEFAULT_ITEM_EXTERNAL_ID` exists and is importable. All downstream tasks can reference it.

---

## Phase 3: User Story 2 — Item Domain Model, Service & CLI (Priority: P2 in spec; Phase 3 in execution)

> **Note on execution order**: US2 (domain-level changes) is implemented first even though it is P2 in the spec, because US1 (Django admin fix) depends on the domain model having a default. The Django admin form error is a symptom of the missing default in the domain layer.

**Goal**: `Item` can be constructed without `external_id`; `TaxomeshService.create_item()` and the CLI `item add` command accept no `external_id`.

**Independent Test**: `Item(name="test")` succeeds, `external_id == ""`; `svc.create_item(name="x")` succeeds; `taxomesh item add --name x` exits with code 0.

### Tests for User Story 2 — write first, verify they FAIL before T006–T008

- [X] T003 [US2] Add `test_external_id_defaults_empty_string` to `tests/domain/test_models.py` — construct `Item(name="test")` with no `external_id`; assert `item.external_id == ""`
- [X] T004 [P] [US2] Add `test_external_id_none_coerces_to_empty_string` to `tests/domain/test_models.py` — construct `Item(name="test", external_id=None)`; assert `item.external_id == ""`
- [X] T005 [P] [US2] Add `test_create_item_without_external_id` to `tests/service/test_service_items.py` — call `svc.create_item(name="x")` with no `external_id`; assert returned item has `external_id == ""`
- [X] T006 [P] [US2] Add `test_item_add_without_external_id` to `tests/test_cli.py` — invoke `runner.invoke(app, ["item", "add", "--name", "x"])` with no `--external-id`; assert exit code 0 and item appears in output

### Implementation for User Story 2

- [X] T007 [US2] Add `= DEFAULT_ITEM_EXTERNAL_ID` default to `external_id` field in `taxomesh/domain/models/item.py`; import `DEFAULT_ITEM_EXTERNAL_ID` from `taxomesh.domain.constants`
- [X] T008 [P] [US2] Make `external_id` optional in `TaxomeshService.create_item()` in `taxomesh/application/service.py` — change signature to `external_id: ExternalId = DEFAULT_ITEM_EXTERNAL_ID`; update docstring `Args:` section to mark field as optional
- [X] T009 [P] [US2] Make `--external-id` optional in `taxomesh/adapters/cli/main.py` — change `typer.Option(..., ...)` to `typer.Option("", ...)` and update help text to note the flag is optional

**Checkpoint**: `pytest tests/domain/test_models.py tests/service/test_service_items.py tests/test_cli.py` — T003–T006 pass. US2 is independently complete.

---

## Phase 4: User Story 1 — Django ORM & Migration (Priority: P1 in spec; Phase 4 in execution)

**Goal**: `ItemModel.external_id` allows blank values in the Django admin form; a migration reflects the change.

**Independent Test**: Open the Django admin Item creation form, leave `external_id` blank, submit — item is saved with `external_id = ""`.

### Tests for User Story 1 — write first, verify they FAIL before T012–T013

- [X] T010 [US1] Add `test_item_model_save_without_external_id` to `tests/contrib/django/test_django_repository.py` — create and save an `ItemModel` with `external_id=""` via the repository; assert it is retrievable
- [X] T011 [P] [US1] Add `test_admin_create_item_blank_external_id` to `tests/contrib/django/test_admin.py` — form validation test: `_ItemForm(data={..., "external_id": ""}).is_valid()` must be True (tests the root cause: `blank=True` on the ORM field)

### Implementation for User Story 1

- [X] T012 [US1] Add `blank=True, default=""` to `ItemModel.external_id` in `taxomesh/contrib/django/models.py`
- [X] T013 [US1] Generate migration `taxomesh/contrib/django/migrations/0002_alter_itemmodel_external_id.py` — `AlterField` on `ItemModel.external_id` with `blank=True, default="", max_length=256`; verify it is named and its `dependencies` reference `("taxomesh_django", "0001_initial")`

**Checkpoint**: `pytest tests/contrib/django/` — T010–T011 pass. US1 is independently complete.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T014 Run full quality gate: `ruff check .` — fix any reported issues
- [X] T015 [P] Run full quality gate: `ruff format --check .` — fix any formatting issues
- [X] T016 [P] Run full quality gate: `mypy --strict .` — fix any type errors
- [X] T017 Run full test suite: `pytest --cov=taxomesh --cov-fail-under=80` — all tests pass, coverage ≥ 80%
- [X] T018 Verify migration applies on a fresh test DB: `python manage.py migrate --settings=tests.django_settings` — no errors
- [X] T019 Verify quickstart.md examples run without error (manual check against `specs/021-optional-external-id/quickstart.md`)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 2 (Foundational)**: No dependencies — start immediately
- **Phase 3 (US2)**: Depends on T001 (constant must exist before domain model import)
- **Phase 4 (US1)**: Depends on T007 (Django admin fix requires domain model default to exist)
- **Phase 5 (Polish)**: Depends on all Phase 3 and Phase 4 tasks

### User Story Dependencies

- **US2 tests (T003–T006)**: Written before implementation; depend on T001
- **US2 implementation (T007–T009)**: Depend on T003–T006 being written and confirmed failing
- **US1 tests (T010–T011)**: Written before implementation; depend on T007 (domain model default must exist for repository tests)
- **US1 implementation (T012–T013)**: Depend on T010–T011 being written and confirmed failing

### Within Each Phase

```
T001 → T002
T001 → T003, T004, T005, T006 (parallel)
T003–T006 → T007
T007 → T008, T009 (parallel)
T007 → T010, T011 (parallel)
T010–T011 → T012
T012 → T013
T013 → T014–T019 (parallel where marked)
```

### Parallel Opportunities

- T003, T004, T005, T006 — four test files, fully independent, write in parallel
- T008, T009 — two independent implementation files (service and CLI)
- T010, T011 — two independent test files (Django repo and Django admin)
- T014, T015, T016 — three independent quality gate checks

---

## Parallel Example: Phase 3 tests

```text
# Write all four failing tests simultaneously:
Task T003: test_external_id_defaults_empty_string → tests/domain/test_models.py
Task T004: test_external_id_none_coerces_to_empty_string → tests/domain/test_models.py  [note: same file as T003, do sequentially]
Task T005: test_create_item_without_external_id → tests/service/test_service_items.py
Task T006: test_item_add_without_external_id → tests/test_cli.py

# T005 and T006 can run in parallel (different files).
# T003 and T004 share a file — write sequentially.
```

---

## Implementation Strategy

### MVP (US1 — Django Admin Fix, the reported bug)

The minimal fix that resolves the reported bug:

1. T001 — constant
2. T003, T007 — domain model test + implementation (prerequisite for Django fix)
3. T010, T012, T013 — Django ORM test + implementation + migration

**STOP and VALIDATE**: Create an item in Django admin without `external_id`. Confirm it saves.

### Full Fix (all layers)

Complete Phase 2 → Phase 3 → Phase 4 → Phase 5 in order for a consistent fix across domain, service, CLI, and Django.

---

## Notes

- TDD is mandatory — verify each test FAILS before writing implementation
- T002 (constant test) is written after the constant exists; it is a sanity check, not a red-green cycle
- T013 (migration) is generated, not hand-written: `python manage.py makemigrations --settings=tests.django_settings` then verify the output file matches the spec in `data-model.md`
- Commit after each checkpoint, not after every individual task
