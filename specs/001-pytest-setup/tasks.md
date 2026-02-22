---
description: "Task list for Dev Toolchain Bootstrap"
---

# Tasks: Dev Toolchain Bootstrap

**Input**: Design documents from `specs/001-pytest-setup/`
**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | quickstart.md ✅

**Tests**: Not requested in spec — no test tasks generated. The quality gate runs
(T007–T009, T011) serve as the acceptance verification for each user story.

**Organization**: Two user stories. US1 (P1) verifies the full dev environment works.
US2 (P2) adds and verifies the smoke test. US2 can only be verified after US1's
foundational phase (tools must be installed), but the smoke test file itself (T010)
can be written in parallel with T007–T009.

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

- [ ] T001 Confirm branch `001-pytest-setup` is active and `taxomesh/__init__.py`, `tests/__init__.py` exist

**Checkpoint**: Branch confirmed, existing files present — proceed to Foundational phase.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Update `pyproject.toml` with all required dependency declarations and tool
configurations. All tasks in this phase edit the same file and MUST be completed sequentially
before any user story verification can begin.

**⚠️ CRITICAL**: No user story work can begin until this phase AND `uv sync` (T007) are complete.

- [ ] T002 Add `fastapi>=0.110` to `[project.dependencies]` in `pyproject.toml` (replace `dependencies = []`)
- [ ] T003 Add `ruff>=0.4` and `mypy>=1.10` to `[project.optional-dependencies] dev` in `pyproject.toml` (also add `fastapi>=0.110` to dev group; keep existing pytest and pytest-cov entries)
- [ ] T004 Add `[tool.ruff]` and `[tool.ruff.lint]` config sections to `pyproject.toml` per plan.md Phase 1 design (`target-version = "py311"`, `line-length = 119`, `select = ["E", "F", "I", "UP", "B", "SIM"]`)
- [ ] T005 Add `[tool.mypy]` config section to `pyproject.toml` per plan.md Phase 1 design (`python_version = "3.11"`, `strict = true`, `warn_return_any = true`, `warn_unused_configs = true`)
- [ ] T006 Add `[tool.pytest.ini_options]` config section to `pyproject.toml` per plan.md Phase 1 design (`addopts = "--cov=taxomesh --cov-report=term-missing"`, `testpaths = ["tests"]`)
- [ ] T007 Run `uv sync --extra dev` from repo root and confirm zero errors — all dependencies resolved and installed

**Checkpoint**: `pyproject.toml` complete, dependencies installed — user story phases can now begin.

---

## Phase 3: User Story 1 — Fresh Dev Environment Setup (Priority: P1) 🎯 MVP

**Goal**: Confirm the three non-test quality gates (lint, format, type check) pass on
the current minimal codebase immediately after a fresh install.

**Independent Test**: Run T008, T009, T010 after T007 completes. All three must exit
with code 0 and zero reported issues.

### Implementation for User Story 1

- [ ] T008 [P] [US1] Run `uv run ruff check .` from repo root — verify exit code 0 and zero violations reported
- [ ] T009 [P] [US1] Run `uv run ruff format --check .` from repo root — verify exit code 0 and zero formatting issues reported
- [ ] T010 [P] [US1] Run `uv run mypy --strict .` from repo root — verify exit code 0 and zero type errors reported

**Checkpoint**: User Story 1 complete — lint, format, and type check all pass on the
initial codebase. A contributor can now run these gates locally with confidence.

---

## Phase 4: User Story 2 — Smoke Test for Library Import (Priority: P2)

**Goal**: Add one test that verifies `taxomesh` is importable and pytest is correctly
wired up with coverage reporting.

**Independent Test**: Run `uv run pytest` after T011 completes. Output must show
"1 passed" and a coverage table — no additional flags needed.

### Implementation for User Story 2

- [ ] T011 [US2] Create `tests/test_smoke.py` with the following exact content:
  ```python
  def test_taxomesh_importable() -> None:
      import taxomesh  # noqa: F401
      assert taxomesh.__version__ is not None
  ```
- [ ] T012 [US2] Run `uv run pytest` from repo root — verify output shows "1 passed", a coverage table for `taxomesh/`, and exit code 0

**Checkpoint**: User Story 2 complete — pytest discovers and runs the smoke test,
coverage is reported automatically, all without extra flags.

---

## Phase 5: Polish & Verification

**Purpose**: Confirm all four quality gates pass together as a single workflow.

- [ ] T013 Run all four gates in sequence from repo root and confirm all pass:
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
                            ┌─────────────────┼──────────────────┐
                           T008 [P]         T009 [P]           T010 [P]
                           (ruff check)   (ruff fmt)         (mypy)
                                        + T011 can start here (different file)
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
4. **STOP and VALIDATE**: Three quality gates pass → contributor environment works

### Full Delivery (Both Stories)

1. Phases 1–3 as above
2. Phase 4: US2 (T011–T012) → pytest runs with coverage
3. Phase 5: Polish (T013) → full gate sequence confirmed green

---

## Notes

- T002–T006 all edit `pyproject.toml` — complete sequentially, not in parallel
- T008, T009, T010 are read-only shell commands — safe to run in parallel
- T011 creates a new file — safe to run in parallel with T008–T010
- `--cov-fail-under=80` is intentionally absent; threshold added in a future feature
- All `uv run` commands assume `uv sync --extra dev` has been completed (T007)
