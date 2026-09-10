# Tasks: Safe HTTP 500 response bodies

**Input**: Design documents from `/specs/059-safe-error-bodies/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/error-mapping.md

**Tests**: Test tasks are included and are **mandatory**. `CLAUDE.md` requires TDD with no
exceptions — every implementation task below is preceded by a test task that must be
written first and must fail before the implementation task starts.

**Organization**: Grouped by user story. US1 (redact) and US2 (preserve) are both P1 and
are two halves of one correct change: shipping US1 without US2 would over-redact. They
are separate phases because each is independently testable, but neither is releasable
alone.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to

## Path Conventions

Single library package: `taxomesh/` and `tests/` at repository root.

---

## Phase 1: Setup

**Purpose**: Nothing to scaffold — the module, its test file, and the docs page all
exist. This phase only establishes the failing baseline TDD requires.

- [X] T001 Confirm the current behavior is the defect by running `uv run pytest tests/contrib/test_api_errors.py -v` and recording that `test_base_error_fallback_is_500` currently asserts `body["detail"] == "unexpected"` at `tests/contrib/test_api_errors.py:84` — the assertion this feature inverts

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The named constant and the module logger. Both user stories reference them,
so they land first.

**⚠️ Blocks all user story phases.**

- [X] T002 Write a failing test asserting `GENERIC_SERVER_ERROR_DETAIL` is importable from `taxomesh.contrib.api.errors`, is a non-empty `str`, and contains none of the words `sql`, `constraint`, `table`, `traceback`, or a path separator, in `tests/contrib/test_api_errors.py`
- [X] T003 Add `GENERIC_SERVER_ERROR_DETAIL: Final[str] = "An internal error occurred."` as a public module constant in `taxomesh/contrib/api/errors.py`, alongside the existing `_HTTP_*` constants (constitution X)
- [X] T004 Add `logger = logging.getLogger(__name__)` at module level in `taxomesh/contrib/api/errors.py`, matching the convention at `taxomesh/application/service.py:38`

**Checkpoint**: T002 passes. No behavior has changed yet.

---

## Phase 3: User Story 1 — A failing backend does not describe itself (Priority: P1)

**Goal**: Both 500 branches return the constant instead of `str(exc)`.

**Independent Test**: Plant a marker in a `TaxomeshRepositoryError` message, map it, and
assert the marker is absent from the body.

### Tests (write first — all must fail before Phase 3 implementation)

- [X] T005 [P] [US1] Write a failing test that maps `TaxomeshRepositoryError("constraint taxomesh_item_external_id_key on table taxomesh_item")` and asserts the returned body equals `{"detail": GENERIC_SERVER_ERROR_DETAIL}`, in `tests/contrib/test_api_errors.py`
- [X] T006 [P] [US1] Write a failing leak test that plants a marker string in the exception message and asserts **no 8-character window** of the original message appears in `body["detail"]` — proving G3 by absence rather than by equality (SC-001, research §8), in `tests/contrib/test_api_errors.py`
- [X] T007 [P] [US1] Write a failing test that the unmatched-`TaxomeshError` fallback branch also returns the constant, and extend it to cover `TaxomeshConfigError` and `TaxomeshRootCategoryError`, which reach the same branch (research §1), in `tests/contrib/test_api_errors.py`
- [X] T008 [US1] Update the existing `test_base_error_fallback_is_500` at `tests/contrib/test_api_errors.py:84` — its `assert body["detail"] == "unexpected"` encodes the old contract and must now assert the constant

### Implementation

- [X] T009 [US1] In `taxomesh/contrib/api/errors.py::to_tuple`, stop building `body` once up front; construct the body inside each branch so the 4xx branches use `str(exc)` and the two 500 branches use `GENERIC_SERVER_ERROR_DETAIL`

**Checkpoint**: T005–T008 pass. US2's tests may now fail if T009 over-redacted — that is exactly what Phase 4 checks.

---

## Phase 4: User Story 2 — Actionable client errors keep their message (Priority: P1)

**Goal**: Prove the redaction is narrow. 404/409/422 bodies are byte-identical to before.

**Independent Test**: Map one exception per non-500 branch; assert each body still
contains `str(exc)` verbatim.

### Tests (write first)

- [X] T010 [P] [US2] Write a failing-if-over-redacted test asserting `TaxomeshDuplicateSlugError` and `TaxomeshExternalIdConflictError` map to 409 with `body["detail"] == str(exc)` verbatim, in `tests/contrib/test_api_errors.py`
- [X] T011 [P] [US2] Write the equivalent test for the 404 branch across `TaxomeshNotFoundError` and its three subclasses, in `tests/contrib/test_api_errors.py`
- [X] T012 [P] [US2] Write the equivalent test for the 422 branch across `TaxomeshValidationError`, `TaxomeshCyclicDependencyError`, and `TaxomeshRelationError`, in `tests/contrib/test_api_errors.py`

### Implementation

- [X] T013 [US2] **No production change was required** — T009's redaction was already correctly scoped and T010–T012 passed on first run. Original task text: No production change expected — T009 already scoped the redaction. If T010–T012 fail, narrow `to_tuple` in `taxomesh/contrib/api/errors.py` until they pass without breaking Phase 3

**Checkpoint**: G2 and G3 hold simultaneously. The mapping is now correct.

---

## Phase 5: User Story 3 — An operator can diagnose what the client was not told (Priority: P2)

**Goal**: The redacted detail reaches the `taxomesh` logger and nowhere else.

**Independent Test**: Attach a capturing handler, map a repository error, assert the
record carries the exception; with no handler configured, assert stderr stays empty.

### Tests (write first)

- [X] T014 [P] [US3] Write a failing `caplog` test asserting that mapping a `TaxomeshRepositoryError` emits exactly one record on the `taxomesh.contrib.api.errors` logger at `ERROR` with `record.exc_info` populated (G4, SC-003), in `tests/contrib/test_api_errors.py`
- [X] T015 [P] [US3] Write a failing test asserting the log record's **formatted message** (`record.getMessage()`) contains none of the exception text — the detail must live in `exc_info`, not the message (data-model.md), in `tests/contrib/test_api_errors.py`
- [X] T016 [P] [US3] Write a failing test asserting that 404/409/422 mappings emit **zero** records (G5, FR-007), in `tests/contrib/test_api_errors.py`
- [X] T017 [P] [US3] Write a test asserting that with no handler configured, mapping a 500 writes nothing to stderr (G6, SC-005), using `capsys`, in `tests/contrib/test_api_errors.py`

### Implementation

- [X] T018 [US3] In `taxomesh/contrib/api/errors.py`, call `logger.error(<static message>, exc_info=exc)` on both 500 branches only — use `exc_info=exc`, never `logger.exception`, which depends on an active `except` block (research §3)

**Checkpoint**: All three stories pass. The feature is functionally complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T019 [P] Update `to_tuple`'s docstring in `taxomesh/contrib/api/errors.py` to state that 500 bodies are generic and the detail goes to the logger, following the docstring conventions in `.specify/memory/constitution.md` (§Docstrings)
- [X] T020 [P] Update `docs/http-api-integration.md` to document the generic 500 body and how to attach a handler to retrieve the detail (FR-011)
- [X] T021 [P] Add the `0.1.0a50` entry to `CHANGELOG.md` describing this as a behavior change, noting explicitly that a client which displayed the 500 `detail` now sees a fixed string
- [X] T022 Verify the existing exhaustiveness guard (`EXPECTED_STATUS` + `_all_taxomesh_error_types`) in `tests/contrib/test_api_errors.py` still proves every `TaxomeshError` subclass is mapped (G1, SC-002) — status values must be unchanged from before this feature
- [X] T023 Run all four quality gates and confirm green: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy --strict .`, `uv run pytest` (SC-004)

---

## Dependencies

```text
Phase 1 (T001)
  └─> Phase 2 (T002 → T003, T004)          [blocks everything below]
        ├─> Phase 3 / US1 (T005-T008 → T009)
        │     └─> Phase 4 / US2 (T010-T012 → T013)   [verifies US1 was narrow]
        └─> Phase 5 / US3 (T014-T017 → T018)         [independent of US1/US2 given Phase 2]
              └─> Phase 6 (T019-T023)
```

**Story independence**: US3 depends only on Phase 2 and can be built in parallel with
US1/US2. US2 must follow US1 — it exists to prove US1 did not overreach, so running it
first would be vacuous.

## Parallel Execution Examples

Within Phase 3, the three new test tasks touch independent test functions:

```text
T005, T006, T007 in parallel  →  then T008 (edits an existing function)  →  then T009
```

Within Phase 5:

```text
T014, T015, T016, T017 in parallel  →  then T018
```

Phase 6 documentation tasks:

```text
T019, T020, T021 in parallel  →  then T022, T023
```

## Implementation Strategy

**Not an MVP-slicing feature.** US1 alone would over-redact and US2 alone is a no-op, so
the releasable unit is Phases 2–4 together, with Phase 5 required before shipping —
redacting without logging would destroy the information rather than relocate it, which
principle V forbids.

Sequence: establish the failing baseline (T001), land the constant and logger (Phase 2),
redact (Phase 3), prove narrowness (Phase 4), relocate the detail (Phase 5), document
(Phase 6).

## Task Summary

| Phase | Story | Tasks | Count |
|---|---|---|---|
| 1 Setup | — | T001 | 1 |
| 2 Foundational | — | T002–T004 | 3 |
| 3 | US1 | T005–T009 | 5 |
| 4 | US2 | T010–T013 | 4 |
| 5 | US3 | T014–T018 | 5 |
| 6 Polish | — | T019–T023 | 5 |
| **Total** | | | **23** |

Test tasks: 13. Implementation tasks: 4. Documentation/verification: 6.

Every implementation task (T009, T013, T018) is preceded by test tasks in its own phase,
satisfying the TDD rule in `CLAUDE.md`.
