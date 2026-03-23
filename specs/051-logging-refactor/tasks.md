# Tasks: Logging Refactor — Public-Library Best Practices

**Input**: Design documents from `/specs/051-logging-refactor/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅

---

## Phase 1: Foundational — NullHandler (blocks all stories)

**Purpose**: Register the `NullHandler` on the `"taxomesh"` root logger. This is a prerequisite for all other logging work to be "correct" from a library standpoint.

**⚠️ CRITICAL**: US2 depends on this being done first.

### Tests for Phase 1

> **Write tests FIRST — ensure they FAIL before implementation**

- [ ] T001 [US2] Write `tests/test_logging.py` with three tests:
  - `test_null_handler_registered`: assert `NullHandler` present after `import taxomesh`
  - `test_no_stderr_output_without_configuration`: smoke-check no last-resort output fires
  - `test_no_timestamp_in_message_text`: assert no ISO-8601 pattern in any taxomesh WARNING message text (use caplog + dangling-link scenario from conftest)

### Implementation for Phase 1

- [ ] T002 [US2] Add `NullHandler` to `taxomesh/__init__.py`:
  - `import logging` (top of file, after existing imports)
  - `logging.getLogger("taxomesh").addHandler(logging.NullHandler())`
  - Run `pytest tests/test_logging.py` → all 3 tests must pass

**Checkpoint**: `import taxomesh` produces zero stderr output. `pytest tests/test_logging.py` green.

---

## Phase 2: User Story 1 — Improved dangling-link warning (Priority: P1)

**Goal**: The `list_related_items_for_sources` warning includes method name, source item `str()`, and orphaned-target label.

**Independent Test**: Run `pytest tests/service/test_service_list_related_resilience.py` — all tests pass with the updated assertions.

### Tests for User Story 1

> **Write tests FIRST — ensure they FAIL before implementation**

- [ ] T003 [US1] Update `tests/service/test_service_list_related_resilience.py`:
  - In `test_single_dangling_link_no_exception`: add assertions for:
    - `"list_related_items_for_sources"` in message
    - source item name (e.g. `"Source"`) in message (via `str(source_item)`)
    - `"orphaned"` in message
    - `str(missing_target_id)` still in message (existing assertion kept)
    - relation type still in message (existing assertion kept)
  - Add `test_source_str_safe_fallback`: inject an `Item` whose `__str__` raises; assert the warning still emits (no exception propagates) and message contains `"str() failed"` or `"unknown source"`.
  - Run `pytest tests/service/test_service_list_related_resilience.py` → T003 tests must **FAIL** (implementation not yet done)

### Implementation for User Story 1

- [ ] T004 [US1] Update dangling-link warning in `taxomesh/application/service.py`:
  - At the `if link.target_item_id not in item_map:` / `skip_on_error` branch:
    1. `source_item = item_map.get(link.source_item_id)`
    2. Build `source_repr`: if `source_item` is not `None`, try `str(source_item)` except `Exception` → `f"<item {link.source_item_id} str() failed>"`. If `source_item` is `None` → `f"<unknown source item {link.source_item_id}>"`
    3. Replace existing `logger.warning(...)` call with the new format (see plan.md Step 2)
  - Run `pytest tests/service/test_service_list_related_resilience.py` → all tests must pass

**Checkpoint**: All tests in `test_service_list_related_resilience.py` green.

---

## Phase 3: User Story 3 — DEBUG → WARNING in Django admin helper (Priority: P2)

**Goal**: `_resolve_linked_url` emits `WARNING` (not `DEBUG`) for missing setting key and URL resolution failure.

**Independent Test**: Run `pytest tests/contrib/django/test_admin_logging.py` — all tests pass.

### Tests for Phase 3

> **Write tests FIRST — ensure they FAIL before implementation**

- [ ] T005 [US3] Create `tests/contrib/django/test_admin_logging.py`:
  - `test_missing_setting_key_emits_warning`: call `_resolve_linked_url("ext-1", "TAXOMESH_NONEXISTENT_SETTING")` with Django test settings that do not include that key; assert `caplog` captures one `WARNING` containing `"TAXOMESH_NONEXISTENT_SETTING"`.
  - `test_url_resolution_failure_emits_warning`: call `_resolve_linked_url("ext-1", setting_name)` where the setting is present but the model label causes `get_model()` or `reverse()` to raise; assert `caplog` captures one `WARNING` containing `"ext-1"`, the setting name, and the exception text.
  - `test_successful_resolution_no_warning`: call `_resolve_linked_url` with valid config; assert no `WARNING` emitted (result may be `None` or a URL — don't assert the value, just no WARNING).
  - Run `pytest tests/contrib/django/test_admin_logging.py` → tests must **FAIL**

### Implementation for Phase 3

- [ ] T006 [US3] Change log level in `taxomesh/contrib/django/admin.py`:
  - Line ~97: `logger.debug(...)` → `logger.warning(...)` (missing setting key case)
  - Line ~104: `logger.debug(...)` → `logger.warning(...)` (URL resolution failure case)
  - Run `pytest tests/contrib/django/test_admin_logging.py` → all tests must pass

**Checkpoint**: All tests in `test_admin_logging.py` green.

---

## Phase 4: User Story 4 — Logger name audit (Priority: P2)

**Goal**: Confirm all `getLogger()` calls use `__name__`. This is a verification task, not a code change.

- [ ] T007 [P] [US4] Audit logger initialisations:
  - `grep -rn "getLogger" taxomesh/` — verify every call uses `__name__`, not a hard-coded string
  - If any hard-coded names found: fix them (change to `__name__`)
  - Document result in a comment in `plan.md` or skip if no changes needed
  - Expected: no changes required (research confirmed both existing calls already use `__name__`)

---

## Phase 5: Documentation (Priority: P3)

**Goal**: Publish the logging guide from `quickstart.md` into the project's public documentation.

- [ ] T008 [US5] Update `README.md`:
  - Add a "Logging" section based on `specs/051-logging-refactor/quickstart.md`
  - Include: logger hierarchy, NullHandler behaviour, how to capture/suppress, timestamp configuration, descriptions of the two warning messages
  - Keep the section concise (reference quickstart.md for full detail if README gets long)

---

## Phase 6: Quality Gates

**Purpose**: Confirm all gates pass before proposing a commit.

- [ ] T009 Run full quality gate suite:
  ```bash
  ruff check .
  ruff format --check .
  mypy --strict .
  pytest --cov=taxomesh --cov-fail-under=80
  ```
  All must pass. Fix any failures before proposing a commit.

---

## Dependencies & Execution Order

```
T001 (tests: NullHandler)
  → T002 (impl: NullHandler)          [BLOCKS all US1/US3 logging correctness]

T003 (tests: dangling-link message)
  → T004 (impl: dangling-link message)

T005 (tests: admin WARNING)
  → T006 (impl: admin WARNING)

T007 [P] — independent audit, no deps
T008 [P] — independent docs, no deps (can be done any time after T004/T006)
T009 — must be last
```

**Parallel opportunities**:
- T001→T002 and T003→T004 and T005→T006 can proceed in parallel once T002 is done.
- T007 and T008 are fully independent.

---

## Notes

- TDD is mandatory: tests must FAIL before implementation for T001, T003, T005.
- No task is done until `pytest [relevant test file]` passes.
- `str()` safe fallback in T004 must handle `None` source item AND `__str__` raising.
- The Django test in T005 must use the existing `tests/django_settings.py` fixture pattern.
