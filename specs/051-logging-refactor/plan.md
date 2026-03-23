# Implementation Plan: Logging Refactor — Public-Library Best Practices

**Branch**: `051-logging-refactor` | **Date**: 2026-03-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/051-logging-refactor/spec.md`

---

## Summary

Register a `NullHandler` on taxomesh's root logger, improve the dangling-relation warning message to include method name and human-readable item representations, upgrade two mislevelled `DEBUG` calls in the Django admin helper to `WARNING`, update the existing tests to assert the new message content, and add a dedicated logging test module plus a quickstart guide.

No new dependencies. No storage changes. No new domain entities. Three source files change; two test files change or are created.

---

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: stdlib `logging` only — no new runtime deps
**Storage**: N/A — no storage changes
**Testing**: pytest + `caplog` fixture (already used in `test_service_list_related_resilience.py`)
**Target Platform**: Any (library)
**Project Type**: Python library
**Performance Goals**: N/A — logging calls are negligible overhead
**Constraints**: `mypy --strict` must pass; `str()` on `Item` must be called safely
**Scale/Scope**: 3 source files, 2 new/updated test files, 1 documentation file

---

## Constitution Check

| Principle | Status | Notes |
|---|---|---|
| I — Hexagonal Architecture | ✅ PASS | `logging` is stdlib; NullHandler in `__init__.py` (composition root). No layer violations. |
| II — TaxomeshService is the single facade | ✅ PASS | No changes to `TaxomeshService`'s public API. |
| III — Repository as Protocol | ✅ PASS | No repository changes. |
| IV — Pydantic + mypy --strict | ✅ PASS | `str(item)` returns `str`; fallback also `str`. All new code must be fully typed. |
| V — Custom exception hierarchy | ✅ PASS | No new exceptions; existing `TaxomeshItemNotFoundError` path unchanged. |
| VI — DAG integrity | ✅ PASS | Not applicable. |
| VII — Spec-driven development | ✅ PASS | Spec exists at `specs/051-logging-refactor/spec.md`. |
| VIII — Quality gates | ✅ PASS | All gates must pass; verified locally before committing. |
| IX — Framework-agnostic HTTP | ✅ PASS | Not applicable. |
| X — Named constants | ✅ PASS | Log message format strings are diagnostic text, not domain-meaningful values. No constants needed. |
| XI — OO by default | ✅ PASS | No new classes warranted; logging is inherently procedural stdlib. |

**Gate result**: PASS. No violations. Proceed to implementation.

---

## Project Structure

### Documentation (this feature)

```text
specs/051-logging-refactor/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── checklists/
│   └── requirements.md
└── tasks.md             ← Phase 2 output (/speckit.tasks)
```

### Source Code Changes

```text
taxomesh/
├── __init__.py                         ← add NullHandler (2 lines)
├── application/
│   └── service.py                      ← improve dangling-link warning (~10 lines)
└── contrib/
    └── django/
        └── admin.py                    ← DEBUG → WARNING (2 lines)

tests/
├── test_logging.py                     ← new: NullHandler, hierarchy, no-timestamp tests
├── service/
│   └── test_service_list_related_resilience.py  ← update: assert new message fields
└── contrib/
    └── django/
        └── test_admin_logging.py       ← new: WARNING for missing setting and URL failure

docs/ or README.md
└── logging guide section               ← new: from quickstart.md
```

**Structure decision**: Single project layout (Option 1). No new packages or modules beyond the two new test files.

---

## Implementation Steps

### Step 1 — Register NullHandler (FR-001)

**File**: `taxomesh/__init__.py`

Add after the existing imports, before `__VERSION__`:

```python
import logging
logging.getLogger("taxomesh").addHandler(logging.NullHandler())
```

This is the entirety of Step 1. The two lines must appear at module level, executed at import time.

---

### Step 2 — Improve dangling-link warning (FR-002, FR-003)

**File**: `taxomesh/application/service.py`

At the `if link.target_item_id not in item_map:` / `skip_on_error` branch, replace the current `logger.warning(...)` call.

**Logic**:
1. Retrieve `source_item = item_map.get(link.source_item_id)`.
2. Build `source_repr`:
   - If `source_item` is not `None`: `try: str(source_item) except Exception: f"<item {link.source_item_id} str() failed>"`
   - If `source_item` is `None`: `f"<unknown source item {link.source_item_id}>"`
3. Emit:

```python
logger.warning(
    "list_related_items_for_sources: dangling relation skipped — "
    "source: %s, target: <orphaned item %s>, relation_type: %r",
    source_repr,
    link.target_item_id,
    link.relation_type,
)
```

No additional repository queries. No new imports (all stdlib or already imported).

---

### Step 3 — Upgrade DEBUG → WARNING in Django admin helper (FR-004, FR-005)

**File**: `taxomesh/contrib/django/admin.py`

Change the two `logger.debug(...)` calls inside `_resolve_linked_url` to `logger.warning(...)`. Message text stays identical.

---

### Step 4 — Update existing resilience tests (FR-002)

**File**: `tests/service/test_service_list_related_resilience.py`

`test_single_dangling_link_no_exception` currently asserts that `str(source.item_id)` and `str(missing_target_id)` appear in the message. After Step 2, the message format changes. Update assertions to also check:

- The method name substring `"list_related_items_for_sources"` is in the message.
- The source item's `name` (e.g. `"Source"`) appears via `str(source_item)`.
- The string `"orphaned"` appears (identifying the orphaned target).
- `str(missing_target_id)` still appears.
- The relation type still appears.

All other tests in this file (empty source list, mixed valid+dangling, skip_on_error=False) are unaffected or need no assertion changes.

---

### Step 5 — New test: `tests/test_logging.py` (FR-001, FR-006, FR-008)

Three tests:

1. **`test_null_handler_registered`**: After `import taxomesh`, assert `logging.getLogger("taxomesh").handlers` contains a `NullHandler`.
2. **`test_no_stderr_output_without_configuration`** (optional / smoke): Verify no last-resort output fires (can be approximated by checking `logging.lastResort` handler is not invoked).
3. **`test_no_timestamp_in_message_text`**: Emit a real warning via the service (dangling link), capture with `caplog`, assert the `getMessage()` result contains no ISO-8601 or timestamp-like substring (regex: no `\d{4}-\d{2}-\d{2}` pattern in message).

---

### Step 6 — New test: `tests/contrib/django/test_admin_logging.py` (FR-004, FR-005)

Two tests using `caplog`:

1. **`test_missing_setting_key_emits_warning`**: Call `_resolve_linked_url` with a Django settings state that lacks the setting key. Assert `WARNING` is emitted containing the setting name.
2. **`test_url_resolution_failure_emits_warning`**: Call `_resolve_linked_url` with a setting key present but a model that causes `reverse()` to fail. Assert `WARNING` is emitted containing the external_id, setting name, and exception text.

These tests require `pytest-django` (already present) and the test Django settings fixture already used in `tests/django_settings.py`.

---

### Step 7 — Update README / docs (FR-009)

Incorporate the content from `specs/051-logging-refactor/quickstart.md` into the project's `README.md` under a new "Logging" section (or equivalent public docs location). Content: logger hierarchy, NullHandler behaviour, how to capture/suppress, timestamp configuration, and the two warning messages.

---

## Complexity Tracking

No constitution violations to justify.

---

## Phase Artifacts

| Artifact | Path | Status |
|---|---|---|
| Spec | `specs/051-logging-refactor/spec.md` | ✅ Complete |
| Research | `specs/051-logging-refactor/research.md` | ✅ Complete |
| Data model | `specs/051-logging-refactor/data-model.md` | ✅ Complete |
| Quickstart | `specs/051-logging-refactor/quickstart.md` | ✅ Complete |
| Tasks | `specs/051-logging-refactor/tasks.md` | ⏳ `/speckit.tasks` |
