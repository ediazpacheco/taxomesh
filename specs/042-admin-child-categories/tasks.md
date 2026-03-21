# Tasks: Admin Child Categories Display

**Input**: Design documents from `/specs/042-admin-child-categories/`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅

**Organization**: Single user story (P1). No setup or foundational phases — no new files, no migrations, no new dependencies.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to

---

## Phase 1: User Story 1 — View Child Categories on Category Change Page (Priority: P1) 🎯 MVP

**Goal**: Add a read-only `CategoryChildLinkInline` to `CategoryModelAdmin` so admins can see direct child categories on the category change page.

**Independent Test**: Open any category change page that has at least one child category and confirm a "Child categories" section is present and lists the correct children. Open a leaf category (no children) and confirm the section is present but empty.

### Tests for User Story 1

> **Write these tests FIRST — they MUST fail before T003–T004 are implemented**

- [ ] T001 [US1] Add test `test_category_child_link_inline_registered_on_category_admin` to `tests/contrib/django/test_admin.py` — assert `CategoryChildLinkInline` is in `CategoryModelAdmin` inline classes
- [ ] T002 [US1] Add test `test_category_child_link_inline_is_read_only` to `tests/contrib/django/test_admin.py` — assert `has_add_permission`, `has_change_permission`, and `has_delete_permission` all return `False`

### Implementation for User Story 1

- [ ] T003 [US1] Add `CategoryChildLinkInline` class to `taxomesh/contrib/django/admin.py` (after `CategoryParentLinkInline`, before the Item inlines section) — `model = CategoryParentLinkModel`, `fk_name = "parent_category"`, `extra = 0`, `verbose_name = "Child category"`, `verbose_name_plural = "Child categories"`, all three permission methods returning `False`
- [ ] T004 [US1] Add `CategoryChildLinkInline` to `CategoryModelAdmin.inlines` in `taxomesh/contrib/django/admin.py` (append after `CategoryParentLinkInline`)

**Checkpoint**: T001–T002 fail → implement T003–T004 → T001–T002 pass → US1 complete

---

## Phase 2: Polish & Quality Gates

**Purpose**: Verify all quality gates pass before proposing a commit.

- [ ] T005 Run `ruff check .` and fix any linting errors in `taxomesh/contrib/django/admin.py`
- [ ] T006 Run `ruff format --check .` and fix any formatting issues in `taxomesh/contrib/django/admin.py`
- [ ] T007 Run `mypy --strict .` and fix any type errors introduced by the new inline class
- [ ] T008 Run `pytest tests/contrib/django/test_admin.py -v` and confirm all tests pass
- [ ] T009 Run `pytest --cov=taxomesh --cov-fail-under=80` and confirm overall coverage gate passes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (US1)**: No blocking prerequisites — can start immediately
- **Phase 2 (Polish)**: Depends on Phase 1 completion

### Within User Story 1

- T001 and T002 MUST be written first (TDD) and MUST fail before T003–T004
- T003 (add class) MUST precede T004 (register in admin), since T004 references the class
- T005–T009 are sequential quality gates after all implementation tasks

### Parallel Opportunities

- T001 and T002 can be written in parallel (both in the same file, different test functions — write sequentially to avoid merge issues)
- T005, T006, T007 can be run in parallel (independent linters)

---

## Parallel Example: User Story 1

```bash
# Write tests first (sequentially — same file):
T001: test_category_child_link_inline_registered_on_category_admin
T002: test_category_child_link_inline_is_read_only

# Run failing tests to confirm TDD baseline:
pytest tests/contrib/django/test_admin.py::TestCategoryChildLinkInline -v  # expect FAIL

# Implement (T003 before T004 — T004 references the class from T003):
T003: Add CategoryChildLinkInline class
T004: Register in CategoryModelAdmin.inlines

# Validate:
pytest tests/contrib/django/test_admin.py -v  # expect PASS
```

---

## Implementation Strategy

### MVP (this feature is already minimal)

1. T001 → T002 (write failing tests)
2. T003 → T004 (implement)
3. T005–T009 (quality gates)
4. Propose commit

---

## Notes

- Total tasks: 9
- Tasks for US1: 4 (2 test + 2 implementation)
- Quality gate tasks: 5
- Parallel opportunities: T005/T006/T007 (linters), T001/T002 (test authoring)
- No new files created — all changes go into existing `admin.py` and `test_admin.py`
- No migrations, no new dependencies, no schema changes
