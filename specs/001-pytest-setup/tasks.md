---
description: "Task list for Dev Toolchain Bootstrap (amended: enable PL rules in ruff)"
---

# Tasks: Dev Toolchain Bootstrap

**Input**: Design documents from `specs/001-pytest-setup/`
**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | quickstart.md ✅

**Tests**: Not requested in spec — no test tasks generated. The quality gate runs
(T008–T010, T012) serve as the acceptance verification for each user story.

**Organization**: Two user stories. US1 (P1) verifies the full dev environment works,
including pylint-equivalent (PL) rule enforcement. US2 (P2) adds and verifies the smoke
test using a module-level import (required by PLC0415). US2 can only be verified after
US1's foundational phase (tools must be installed), but the smoke test file (T011) can
be written in parallel with T008–T010.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (no shared file dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)
- Exact file paths are included in every implementation task

## Path Conventions

- Source: `taxomesh/` at repository root
- Tests: `tests/` at repository root
- Config: `pyproject.toml` at repository root

---

## Phase 1: Setup

**Purpose**: Confirm working branch and verify existing project structure.

- [x] T001 Confirm branch `001-pytest-setup` is active and `taxomesh/__init__.py`, `tests/__init__.py` exist

**Checkpoint**: Branch confirmed, existing files present — proceed to Foundational phase.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Update `pyproject.toml` with all required dependency declarations and tool
configurations, including pylint-equivalent (PL) rules in the ruff linter. All tasks in
this phase edit the same file and MUST be completed sequentially before any user story
verification can begin.

**⚠️ CRITICAL**: No user story work can begin until this phase AND `uv sync` (T007) are complete.

- [x] T002 Add `fastapi>=0.110` to `[project.dependencies]` in `pyproject.toml` (replace `dependencies = []`)
- [x] T003 Add `ruff>=0.4` and `mypy>=1.10` to `[project.optional-dependencies] dev` in `pyproject.toml` (also add `fastapi>=0.110` to dev group; keep existing pytest and pytest-cov entries)
- [x] T004 Add `[tool.ruff]` and `[tool.ruff.lint]` config sections to `pyproject.toml` per plan.md Phase 1 design (`target-version = "py311"`, `line-length = 119`, `select = ["E", "F", "I", "UP", "B", "SIM", "PL"]`) — `PL` enables pylint-equivalent checks (PLC, PLE, PLR, PLW)
- [x] T005 Add `[tool.mypy]` config section to `pyproject.toml` per plan.md Phase 1 design (`python_version = "3.11"`, `strict = true`, `warn_return_any = true`, `warn_unused_configs = true`)
- [x] T006 Add `[tool.pytest.ini_options]` config section to `pyproject.toml` per plan.md Phase 1 design (`addopts = "--cov=taxomesh --cov-report=term-missing --cov-fail-under=80"`, `testpaths = ["tests"]`)
- [x] T007 Run `uv sync --extra dev` from repo root and confirm zero errors — all dependencies resolved and installed

**Checkpoint**: `pyproject.toml` complete, dependencies installed — user story phases can now begin.

---

## Phase 3: User Story 1 — Fresh Dev Environment Setup (Priority: P1) 🎯 MVP

**Goal**: Confirm the three non-test quality gates (lint, format, type check) pass on
the current minimal codebase, including zero PL rule violations.

**Independent Test**: Run T008, T009, T010 after T007 completes. All three must exit
with code 0 and zero reported issues (including zero PL violations).

### Implementation for User Story 1

- [x] T008 [P] [US1] Run `uv run ruff check .` from repo root — verify exit code 0 and zero violations including PL rule checks (PLC, PLE, PLR, PLW)
- [x] T009 [P] [US1] Run `uv run ruff format --check .` from repo root — verify exit code 0 and zero formatting issues reported
- [x] T010 [P] [US1] Run `uv run mypy --strict .` from repo root — verify exit code 0 and zero type errors reported

**Checkpoint**: User Story 1 complete — lint (with PL rules), format, and type check all
pass on the initial codebase. A contributor can now run these gates locally with confidence.

---

## Phase 4: User Story 2 — Smoke Test for Library Import (Priority: P2)

**Goal**: Add one test that verifies `taxomesh` is importable, pytest is correctly wired
up with coverage reporting, and the test file itself passes PL rule checks.

**Independent Test**: Run `uv run pytest` after T011 completes. Output must show
"1 passed" and a coverage table — no additional flags needed.

### Implementation for User Story 2

- [x] T011 [US2] Create `tests/test_smoke.py` with the following exact content (module-level import satisfies PLC0415; no noqa suppressions required):
  ```python
  import taxomesh


  def test_taxomesh_importable() -> None:
      assert taxomesh.__version__ is not None
  ```
- [x] T012 [US2] Run `uv run pytest` from repo root — verify output shows "1 passed", a coverage table for `taxomesh/`, coverage ≥ 80%, and exit code 0

**Checkpoint**: User Story 2 complete — pytest discovers and runs the smoke test,
coverage is reported automatically, and no PL violations exist in the test file.

---

## Phase 5: Polish & Verification

**Purpose**: Confirm all four quality gates pass together as a single workflow with
PL rules fully active.

- [x] T013 Run all four gates in sequence from repo root and confirm all pass:
  ```bash
  uv run ruff check .
  uv run ruff format --check .
  uv run mypy --strict .
  uv run pytest
  ```

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — T002→T003→T004→T005→T006→T007 sequential (same file edits)
- **US1 (Phase 3)**: Depends on T007 (uv sync complete) — T008, T009, T010 can run in parallel
- **US2 (Phase 4)**: T011 (write test) can start after T007; T012 (run pytest) depends on T011
- **Polish (Phase 5)**: Depends on all phases complete

### Within-Story Dependencies

```
T001 → T002 → T003 → T004 → T005 → T006 → T007
                                              ↓
                   ┌──────────────────────────┼──────────────────┬──────────────────┐
                 T008 [P]                 T009 [P]           T010 [P]           T011 [P]
                 (ruff check)           (ruff fmt)           (mypy)         (smoke test)
                                                                                  ↓
                                                                            T012 (pytest)
                                                                                  ↓
                                                                            T013 (full gate run)
```

### Parallel Opportunities

- **T008, T009, T010**: All read-only quality gate runs — fully parallel after T007
- **T011**: Write `tests/test_smoke.py` — parallel with T008/T009/T010 (different file)

---

## Parallel Execution Example

```bash
# After T007 (uv sync) completes, launch in parallel:
Task: "Run ruff check . — T008"
Task: "Run ruff format --check . — T009"
Task: "Run mypy --strict . — T010"
Task: "Create tests/test_smoke.py — T011"

# After T011 completes:
Task: "Run pytest — T012"

# After all above:
Task: "Full gate sequence — T013"
```

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 2: Foundational (T002–T007)
3. Complete Phase 3: US1 (T008–T010)
4. **STOP and VALIDATE**: Three quality gates pass with PL rules active → contributor environment works

### Full Delivery (Both Stories)

1. Phases 1–3 as above
2. Phase 4: US2 (T011–T012) → pytest runs with coverage, no PL violations in test file
3. Phase 5: Polish (T013) → full gate sequence confirmed green

---

## Notes

- T002–T006 all edit `pyproject.toml` — complete sequentially, not in parallel
- T004 includes `"PL"` in ruff select — enables PLC, PLE, PLR, PLW without any new dependency
- T011 uses a module-level import — satisfies PLC0415 (import-outside-top-level); no `noqa` needed
- T008, T009, T010 are read-only shell commands — safe to run in parallel
- T011 creates a new file — safe to run in parallel with T008–T010
- All `uv run` commands assume `uv sync --extra dev` has been completed (T007)
