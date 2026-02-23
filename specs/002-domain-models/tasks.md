# Tasks: Extract ExternalId TypeAlias (002-domain-models)

**Input**: Design documents from `/specs/002-domain-models/`
**Branch**: `002-domain-models`
**Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

**Scope**: Pure structural refactoring. Observable behaviour of `Item.external_id` is
unchanged. No new user stories; this amendment serves **US1** (Reference external items)
by giving the polymorphic identifier type a stable, importable name.

**Tests**: Not requested for this refactoring. Existing test suite (100% coverage)
covers all `Item.external_id` behaviour and must continue to pass after the change.

**Pre-existing implementations** (out of this amendment's scope — no tasks required):
FR-001 (`ModelBase`), FR-002 (`Item` auto-UUID), FR-004–FR-010, and US2–US6 are fully
implemented and verified by the existing test suite. This tasks.md covers only the
TypeAlias extraction (FR-003, US1 amendment).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on each other)
- **[Story]**: User story from spec.md

---

## Phase 1: Foundational — New Types Module

**Purpose**: Create the `taxomesh/domain/types.py` module that all future layers
will import from. This is the only blocking prerequisite for the refactoring.

**⚠️ CRITICAL**: Phase 2 cannot begin until this phase is complete.

- [x] T001 Create `taxomesh/domain/types.py` and declare `ExternalId: TypeAlias = UUID | Annotated[str, Field(max_length=256)] | int`

**Checkpoint**: `taxomesh/domain/types.py` exists and is importable.

---

## Phase 2: User Story 1 — Reference External Items (Priority: P1)

**Goal**: Replace the inline union in `Item.external_id` with the `ExternalId` alias.
After this phase, `Item` is identical in behaviour but references the canonical type name.

**Independent Test**: `pytest tests/domain/test_models.py` must pass with zero changes
to the test file. All collected tests must pass; coverage must stay at 100%.

### Implementation

- [x] T002 [US1] Add `from taxomesh.domain.types import ExternalId` import to `taxomesh/domain/models.py`
- [x] T003 [US1] Replace `external_id: UUID | Annotated[str, Field(max_length=256)] | int` with `external_id: ExternalId` in `Item` in `taxomesh/domain/models.py`

**Checkpoint**: `Item.external_id` is annotated as `ExternalId`. No test changes needed.

---

## Phase 3: Polish & Quality Gates

**Purpose**: Verify all quality gates pass and commit all artifacts (spec + implementation).

- [x] T004 [P] Run `uv run ruff check .` — must report no issues
- [x] T005 [P] Run `uv run ruff format --check .` — must report all files formatted
- [x] T006 [P] Run `uv run mypy --strict .` — must report no issues in 8 source files
- [x] T007 Run `uv run pytest --cov=taxomesh --cov-fail-under=80` — must pass all collected tests at ≥ 80% coverage (depends on T004–T006 all passing)
- [ ] T008 Commit spec artifacts: `specs/002-domain-models/plan.md`, `specs/002-domain-models/research.md`, `specs/002-domain-models/data-model.md`, `specs/002-domain-models/contracts/python-api.md`, `specs/002-domain-models/quickstart.md`, `specs/002-domain-models/spec.md`, `specs/002-domain-models/tasks.md`, `CLAUDE.md`
- [ ] T009 Commit implementation: `taxomesh/domain/types.py`, `taxomesh/domain/models.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** (T001): No dependencies — start immediately
- **Phase 2** (T002–T003): Depends on T001 — `ExternalId` must exist before it can be imported
- **Phase 3** (T004–T009): Depends on Phase 2 completion

### Within Phase 2

- T002 before T003 — import must be added before the field annotation is changed

### Within Phase 3

- T004, T005, T006: Parallel — all check different tools, no shared state
- T007: After T004–T006 — full gate run as final integration check
- T008: After T007 — only commit when gates are green
- T009: After T008 — implementation commit follows spec commit

---

## Parallel Opportunities

```bash
# Phase 3 quality checks can all launch together:
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict .
```

---

## Implementation Strategy

### Single-increment delivery (this change is atomic)

1. T001 — create `types.py`
2. T002–T003 — update `models.py`
3. T004–T007 — verify all quality gates
4. T008–T009 — commit spec then implementation

Total: 9 tasks, all blocking in sequence except the three parallel quality checks.

---

## Notes

- This is a pure refactoring — no new tests required, no behaviour change.
- `UUID` stays in `models.py` (`from uuid import UUID, uuid4`) — still used for all PK fields.
- `Annotated` stays in `models.py` — still used by `Category.name`, `Category.description`, `Tag.name`.
- `typing.TypeAlias` is the correct Python 3.11 form; do NOT use PEP 695 `type X = ...` syntax (requires 3.12+).
- Commit spec artifacts and implementation as two separate commits for clean history.
