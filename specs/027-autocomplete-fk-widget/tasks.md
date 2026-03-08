# Tasks: Autocomplete FK Widget for External Admin

**Input**: Design documents from `/specs/027-autocomplete-fk-widget/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: TDD is mandatory per project constitution. Test tasks are written first and MUST
fail before the corresponding implementation task begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and
testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Exact file paths included in all descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new module file. No DB changes, no new packages.

- [x] T001 Create `taxomesh/contrib/django/widgets.py` with module docstring and required imports (`Any`, `AutocompleteSelect`, `format_html`, `mark_safe`, `reverse`, `NoReverseMatch`)

**Checkpoint**: `taxomesh/contrib/django/widgets.py` exists and imports cleanly.

---

## Phase 2: Foundational (Blocking Prerequisites)

*No foundational phase needed — this feature is purely additive. `ItemModelAdmin` and
`CategoryModelAdmin` already have `search_fields`. No migrations, no new packages.*

**Proceed directly to Phase 3.**

---

## Phase 3: User Story 1 — Compact Filterable Selector for Item FK (Priority: P1) 🎯 MVP

**Goal**: External app admins can replace the full Item FK dropdown with a compact Select2
autocomplete + "↗" link to the ItemModel change page.

**Independent Test**: Open any external admin change page that has a FK to `ItemModel`; field
renders as a compact Select2 widget; selecting an existing item shows a "↗" link; clicking it
opens the taxomesh `ItemModel` change page.

### Tests for User Story 1 ⚠️ Write FIRST — must FAIL before T005

- [x] T002 [P] [US1] Write failing test `test_widget_render_no_value` — assert `render()` with `value=None` returns no "↗" link — in `tests/contrib/django/test_admin_linked_fk.py`
- [x] T003 [P] [US1] Write failing test `test_widget_render_with_item_value` — assert `render()` with a valid `ItemModel` pk returns HTML containing an "↗" `<a href="...">` pointing to the correct admin change URL — in `tests/contrib/django/test_admin_linked_fk.py`
- [x] T004 [P] [US1] Write failing test `test_widget_render_unresolvable_url` — assert `render()` with a value whose change URL raises `NoReverseMatch` returns HTML without "↗" link and without raising — in `tests/contrib/django/test_admin_linked_fk.py`

### Implementation for User Story 1

- [x] T005 [US1] Implement `TaxomeshLinkedFKWidget(AutocompleteSelect)` in `taxomesh/contrib/django/widgets.py`: override `render(name, value, attrs)` to append a `format_html`-generated "↗" `<a>` link when value is set, deriving the change URL from `self.field.remote_field.model._meta`; catch `NoReverseMatch` silently
- [x] T006 [US1] Run `pytest tests/contrib/django/test_admin_linked_fk.py::test_widget_render_no_value tests/contrib/django/test_admin_linked_fk.py::test_widget_render_with_item_value tests/contrib/django/test_admin_linked_fk.py::test_widget_render_unresolvable_url` — verify all three pass

**Checkpoint**: US1 complete. `TaxomeshLinkedFKWidget` is fully functional for Item FK fields.

---

## Phase 4: User Story 2 — Compact Filterable Selector for Category FK (Priority: P2)

**Goal**: External app admins can replace the full Category FK dropdown with a compact Select2
autocomplete + "↗" link to the CategoryModel change page.

**Independent Test**: Open any external admin change page that has a FK to `CategoryModel`;
field renders as compact Select2; selecting a category shows a "↗" link to its taxomesh admin
change page.

**Note**: `TaxomeshLinkedFKWidget` is already generic — it derives the change URL from
`self.field.remote_field.model._meta`. No implementation changes are needed; only tests.

### Tests for User Story 2 ⚠️ Write FIRST — must FAIL before verification

- [x] T007 [P] [US2] Write failing test `test_widget_render_with_category_value` — assert `render()` with a valid `CategoryModel` pk returns HTML containing "↗" link pointing to the correct `CategoryModel` admin change URL — in `tests/contrib/django/test_admin_linked_fk.py`

### Verification for User Story 2

- [x] T008 [US2] Run `pytest tests/contrib/django/test_admin_linked_fk.py::test_widget_render_with_category_value` — verify it passes (widget from T005 already handles Category; no new code needed)

**Checkpoint**: US2 complete. Same widget confirmed working for Category FK fields.

---

## Phase 5: User Story 3 — Drop-in Mixin for External ModelAdmin (Priority: P3)

**Goal**: External app developers add `TaxomeshLinkedFKMixin` to their `ModelAdmin` and all
FK fields pointing to `ItemModel` or `CategoryModel` automatically use the compact autocomplete
+ link widget — no per-field configuration required.

**Independent Test**: A `ModelAdmin` subclassing `TaxomeshLinkedFKMixin` with FK fields to
both `ItemModel` and `CategoryModel` renders both as compact autocomplete + link; a FK to an
unrelated model renders normally; a model with no taxomesh FKs raises no error.

### Tests for User Story 3 ⚠️ Write FIRST — must FAIL before T012

- [x] T009 [P] [US3] Write failing test `test_mixin_item_fk_uses_widget` — assert `formfield_for_foreignkey` returns a field whose widget is `TaxomeshLinkedFKWidget` when `db_field.related_model` is `ItemModel` — in `tests/contrib/django/test_admin_linked_fk.py`
- [x] T010 [P] [US3] Write failing test `test_mixin_category_fk_uses_widget` — same assertion for `CategoryModel` — in `tests/contrib/django/test_admin_linked_fk.py`
- [x] T011 [P] [US3] Write failing test `test_mixin_unrelated_fk_unchanged` — assert `formfield_for_foreignkey` for a FK to an unrelated model does NOT use `TaxomeshLinkedFKWidget` — in `tests/contrib/django/test_admin_linked_fk.py`

### Implementation for User Story 3

- [x] T012 [US3] Implement `TaxomeshLinkedFKMixin` in `taxomesh/contrib/django/admin.py`: add class after existing mixin definitions; override `formfield_for_foreignkey` to inject `TaxomeshLinkedFKWidget` when `db_field.related_model in (ItemModel, CategoryModel)`; import `TaxomeshLinkedFKWidget` from `.widgets`
- [x] T013 [US3] Run `pytest tests/contrib/django/test_admin_linked_fk.py::test_mixin_item_fk_uses_widget tests/contrib/django/test_admin_linked_fk.py::test_mixin_category_fk_uses_widget tests/contrib/django/test_admin_linked_fk.py::test_mixin_unrelated_fk_unchanged` — verify all three pass

**Checkpoint**: All three user stories complete and independently verified.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates, type correctness, full test suite.

- [x] T014 [P] Run `ruff check taxomesh/contrib/django/widgets.py tests/contrib/django/test_admin_linked_fk.py` and fix any linting issues
- [x] T015 [P] Run `ruff format --check taxomesh/contrib/django/widgets.py tests/contrib/django/test_admin_linked_fk.py` and fix any formatting issues
- [x] T016 Run `mypy --strict taxomesh/contrib/django/widgets.py taxomesh/contrib/django/admin.py` and fix any type errors
- [x] T017 Run `pytest --cov=taxomesh --cov-fail-under=80` — verify full suite passes and coverage gate holds
- [x] T018 Run `ruff check . && ruff format --check . && mypy --strict . && pytest --cov=taxomesh --cov-fail-under=80` — final full quality gate pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Phase 3 (US1)**: Depends on T001 (Phase 1)
- **Phase 4 (US2)**: Depends on T005 (widget implementation from US1)
- **Phase 5 (US3)**: Depends on T005 (widget must exist to be injected by mixin)
- **Phase 6 (Polish)**: Depends on all user story phases complete

### User Story Dependencies

- **US1 (P1)**: Depends only on T001. Can start immediately after setup.
- **US2 (P2)**: Depends on T005 (widget impl). No new code — only tests.
- **US3 (P3)**: Depends on T005 (widget must exist). Mixin implementation is independent.

### Within Each User Story

- Tests (T002–T004, T007, T009–T011) MUST be written and FAIL before implementation
- Widget implementation (T005) before mixin implementation (T012)

### Parallel Opportunities

- T002, T003, T004 — all in same file but independent test functions, can be written in one pass
- T009, T010, T011 — same file, independent test functions, write in one pass
- T014 and T015 — independent lint/format checks, can run simultaneously

---

## Parallel Example: User Story 1

```bash
# Write all three failing tests together (same file, one pass):
T002: test_widget_render_no_value
T003: test_widget_render_with_item_value
T004: test_widget_render_unresolvable_url

# Then implement widget (T005)
# Then verify (T006)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. T001 — Create `widgets.py`
2. T002–T004 — Write failing tests
3. T005 — Implement `TaxomeshLinkedFKWidget`
4. T006 — Verify tests pass
5. **STOP and VALIDATE** — widget works for Item FK

### Incremental Delivery

1. US1 → `TaxomeshLinkedFKWidget` functional for Item FK
2. US2 → Same widget confirmed for Category FK (tests only)
3. US3 → `TaxomeshLinkedFKMixin` drop-in ready
4. Polish → All quality gates green

---

## Notes

- [P] tasks = different files or independent concerns
- [Story] label maps each task to its user story for traceability
- TDD is mandatory per project constitution — never implement before the failing test exists
- `TaxomeshLinkedFKWidget` is generic; US1 and US2 share the same implementation
- `TaxomeshLinkedFKMixin` is the only class that imports from `widgets.py` (within `admin.py`)
- No migrations, no new settings, no new packages required
