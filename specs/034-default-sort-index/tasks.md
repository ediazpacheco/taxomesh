# Tasks: Default sort_index Ordering for All Collection-Returning Methods

**Input**: Design documents from `/specs/034-default-sort-index/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅

**TDD**: Tests are mandatory per project constitution. Every implementation task is preceded
by its failing test task. Tests MUST fail before implementation begins.

**Organization**: Tasks grouped by user story. US1 and US2 are both P1 — they can be
worked in parallel once Phase 2 is done, but are sequenced here for clarity.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no conflicting dependencies)
- **[Story]**: User story label (US1–US3)

---

## Phase 1: Setup

**Purpose**: Verify test infrastructure is in place before any implementation begins.
No new project structure required — all changes are inside existing modules.

- [X] T001 Verify `tests/repositories/` directory exists or create it with an empty `__init__.py`

---

## Phase 2: Foundational

**Purpose**: Document the ordering contract in the Protocol before any adapter work begins.
This defines the target behaviour that all tests and implementations must satisfy.

- [X] T002 Update docstrings for all 7 affected methods in `taxomesh/ports/repository.py` to document the ordering contract: `list_category_parent_links()` → `(parent_category_id ASC, sort_index ASC, category_id ASC)`; `list_item_parent_links()` → `(category_id ASC, sort_index ASC, item_id ASC)`; `list_item_relation_links()` → `(sort_index ASC, source_item_id ASC, target_item_id ASC)`; `list_categories()` → name ASC (unfiltered) or link sort_index (filtered); `list_items()` → name ASC (unfiltered) or link sort_index (filtered); `list_items_by_external_id()` → name ASC; `list_categories_by_external_id()` → name ASC

**Checkpoint**: Protocol contract documented — adapter implementation can now begin

---

## Phase 3: User Story 1 — Link-List Ordering (Priority: P1) 🎯 MVP

**Goal**: `list_category_parent_links()`, `list_item_parent_links()`, and
`list_item_relation_links()` return results in defined order across all three adapters.

**Independent Test**: Create repositories with link records inserted in non-ascending
sort_index order spanning multiple parents; verify all three link-list methods return
records grouped by parent and ordered by sort_index within each group.

### Tests for User Story 1

> **Write these tests FIRST — they MUST FAIL before any implementation task starts**

- [X] T003 [US1] Write failing tests for link ordering in `tests/repositories/test_json_repository_ordering.py`: (a) `list_category_parent_links()` groups by `parent_category_id` then `sort_index`; (b) `list_item_parent_links()` groups by `category_id` then `sort_index`; (c) `list_item_relation_links()` ordered by `sort_index` then IDs; (d) tie-breaker: equal `sort_index` ordered by secondary ID field
- [X] T004 [P] [US1] Write failing tests for link ordering in `tests/repositories/test_yaml_repository_ordering.py` — same scenarios as T003 for the YAML adapter
- [X] T005 [P] [US1] Write failing tests for link ordering in `tests/repositories/test_django_repository_ordering.py` — same scenarios as T003 for the Django adapter (use existing Django test setup and in-memory SQLite)

### Implementation for User Story 1

- [X] T006 [US1] Fix `list_category_parent_links()` in `taxomesh/adapters/repositories/json_repository.py`: return `sorted(self._category_parent_links, key=lambda l: (str(l.parent_category_id), l.sort_index, str(l.category_id)))` (depends on T003 failing)
- [X] T007 [P] [US1] Fix `list_item_parent_links()` in `taxomesh/adapters/repositories/json_repository.py`: return `sorted(self._item_parent_links, key=lambda l: (str(l.category_id), l.sort_index, str(l.item_id)))`
- [X] T008 [P] [US1] Fix `list_item_relation_links()` in `taxomesh/adapters/repositories/json_repository.py`: wrap final result in `sorted(..., key=lambda l: (l.sort_index, str(l.source_item_id), str(l.target_item_id)))`
- [X] T009 [P] [US1] Fix `list_category_parent_links()` in `taxomesh/adapters/repositories/yaml_repository.py`: same sort key as T006
- [X] T010 [P] [US1] Fix `list_item_parent_links()` in `taxomesh/adapters/repositories/yaml_repository.py`: same sort key as T007
- [X] T011 [P] [US1] Fix `list_item_relation_links()` in `taxomesh/adapters/repositories/yaml_repository.py`: same sort key as T008
- [X] T012 [P] [US1] Fix `list_category_parent_links()` in `taxomesh/adapters/repositories/django_repository.py`: add `.order_by("parent_category_id", "sort_index", "category_id")` to the queryset
- [X] T013 [P] [US1] Fix `list_item_parent_links()` in `taxomesh/adapters/repositories/django_repository.py`: add `.order_by("category_id", "sort_index", "item_id")` to the queryset
- [X] T014 [P] [US1] Fix `list_item_relation_links()` in `taxomesh/adapters/repositories/django_repository.py`: add `.order_by("sort_index", "source_item_id", "target_item_id")` to the queryset

**Checkpoint**: Run `pytest tests/repositories/test_json_repository_ordering.py tests/repositories/test_yaml_repository_ordering.py tests/repositories/test_django_repository_ordering.py` — all link-ordering tests MUST pass

---

## Phase 4: User Story 2 — Category and Item Listing Order (Priority: P1)

**Goal**: `list_categories()` and `list_items()` return results in defined order across
all three adapters. Unfiltered: by name. Filtered (service layer, already correct): by
parent-link sort_index.

**Independent Test**: Create repositories with Category and Item records inserted in
non-alphabetical name order; verify `list_categories()` and `list_items()` return records
in ascending alphabetical order by name.

### Tests for User Story 2

> **Write these tests FIRST — they MUST FAIL before any implementation task starts**

- [X] T015 [US2] Add failing tests for category/item name ordering to `tests/repositories/test_json_repository_ordering.py`: (a) `list_categories()` returns all categories sorted by name ASC, secondary by `category_id`; (b) `list_items()` returns all items sorted by name ASC, secondary by `item_id`; (c) tie-breaker: equal names ordered by ID
- [X] T016 [P] [US2] Add failing tests for category/item name ordering to `tests/repositories/test_yaml_repository_ordering.py` — same scenarios as T015
- [X] T017 [P] [US2] Add failing tests for category/item name ordering to `tests/repositories/test_django_repository_ordering.py` — same scenarios as T015

### Implementation for User Story 2

- [X] T018 [US2] Fix `list_categories()` in `taxomesh/adapters/repositories/json_repository.py`: return `sorted(self._categories.values(), key=lambda c: (c.name, str(c.category_id)))` (depends on T015 failing)
- [X] T019 [P] [US2] Fix `list_items()` in `taxomesh/adapters/repositories/json_repository.py`: return `sorted(self._items.values(), key=lambda i: (i.name, str(i.item_id)))`
- [X] T020 [P] [US2] Fix `list_categories()` in `taxomesh/adapters/repositories/yaml_repository.py`: same sort key as T018
- [X] T021 [P] [US2] Fix `list_items()` in `taxomesh/adapters/repositories/yaml_repository.py`: same sort key as T019
- [X] T022 [P] [US2] Fix `list_categories()` in `taxomesh/adapters/repositories/django_repository.py`: add `.order_by("name", "category_id")` to the queryset
- [X] T023 [P] [US2] Fix `list_items()` in `taxomesh/adapters/repositories/django_repository.py`: add `.order_by("name", "item_id")` to the queryset

**Checkpoint**: Run `pytest tests/repositories/` — all category/item ordering tests MUST pass on top of passing link tests from Phase 3

---

## Phase 5: User Story 3 — get_* Collection Methods Ordered (Priority: P2)

**Goal**: `list_items_by_external_id()` and `list_categories_by_external_id()` return
results sorted by name across all three adapters. Service-level `get_items_by_external_id()`
and `get_categories_by_external_id()` inherit correct ordering automatically.

**Independent Test**: Create repositories where multiple items (or categories) share the
same `external_id` but have names in non-alphabetical order; verify the `by_external_id`
methods return them sorted by name ASC.

### Tests for User Story 3

> **Write these tests FIRST — they MUST FAIL before any implementation task starts**

- [X] T024 [US3] Add failing tests for external_id list ordering to `tests/repositories/test_json_repository_ordering.py`: (a) `list_items_by_external_id()` returns items sorted by name ASC then item_id; (b) `list_categories_by_external_id()` returns categories sorted by name ASC then category_id; (c) single-result case returns correctly (no regression)
- [X] T025 [P] [US3] Add failing tests for external_id list ordering to `tests/repositories/test_yaml_repository_ordering.py` — same scenarios as T024
- [X] T026 [P] [US3] Add failing tests for external_id list ordering to `tests/repositories/test_django_repository_ordering.py` — same scenarios as T024

### Implementation for User Story 3

- [X] T027 [US3] Fix `list_items_by_external_id()` in `taxomesh/adapters/repositories/json_repository.py`: wrap comprehension in `sorted(..., key=lambda i: (i.name, str(i.item_id)))` (depends on T024 failing)
- [X] T028 [P] [US3] Fix `list_categories_by_external_id()` in `taxomesh/adapters/repositories/json_repository.py`: wrap comprehension in `sorted(..., key=lambda c: (c.name, str(c.category_id)))`
- [X] T029 [P] [US3] Fix `list_items_by_external_id()` in `taxomesh/adapters/repositories/yaml_repository.py`: same sort key as T027
- [X] T030 [P] [US3] Fix `list_categories_by_external_id()` in `taxomesh/adapters/repositories/yaml_repository.py`: same sort key as T028
- [X] T031 [P] [US3] Fix `list_items_by_external_id()` in `taxomesh/adapters/repositories/django_repository.py`: add `.order_by("name", "item_id")` to the filter queryset
- [X] T032 [P] [US3] Fix `list_categories_by_external_id()` in `taxomesh/adapters/repositories/django_repository.py`: add `.order_by("name", "category_id")` to the filter queryset

**Checkpoint**: Run `pytest tests/repositories/` — all ordering tests MUST pass across all three adapters

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates and final validation.

- [X] T033 [P] Run `ruff check .` and fix any linting errors introduced by the new `sorted()` calls or `.order_by()` additions
- [X] T034 [P] Run `ruff format --check .` and fix any formatting issues
- [X] T035 [P] Run `mypy --strict .` and fix any type errors (ensure sort key lambdas are correctly typed)
- [X] T036 Run `pytest --cov=taxomesh --cov-fail-under=80` and confirm all tests pass with coverage ≥ 80%

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1
- **Phase 3 (US1)**: Depends on Phase 2 — tests must be written and failing before T006+
- **Phase 4 (US2)**: Depends on Phase 2 — can run in parallel with Phase 3 (different methods)
- **Phase 5 (US3)**: Depends on Phase 2 — can run in parallel with Phase 3 and 4
- **Phase 6 (Polish)**: Depends on Phase 3, 4, and 5 all complete

### User Story Dependencies

- **US1 (P1)**: No dependency on US2 or US3 — independently testable
- **US2 (P1)**: No dependency on US1 or US3 — independently testable
- **US3 (P2)**: No dependency on US1 or US2 — independently testable

### Within Each Phase

```
Tests (T003-T005, T015-T017, T024-T026) → MUST FAIL → Implementation → MUST PASS
```

All `[P]`-marked tasks within a phase operate on different files and can run concurrently.

---

## Parallel Execution Examples

### Phase 3 (US1) — after T003-T005 all fail:

```
T006 json list_category_parent_links  ┐
T007 json list_item_parent_links      ├─ parallel (different methods, same file — order matters within file)
T008 json list_item_relation_links    ┘
T009 yaml list_category_parent_links  ┐
T010 yaml list_item_parent_links      ├─ parallel
T011 yaml list_item_relation_links    ┘
T012 django list_category_parent_links ┐
T013 django list_item_parent_links     ├─ parallel
T014 django list_item_relation_links   ┘
```

### US1, US2, US3 — can all start after Phase 2 (T002):

```
Phase 3 (US1 link methods)    ─┐
Phase 4 (US2 list methods)    ─┤─ all parallel if capacity allows
Phase 5 (US3 by_ext_id)       ─┘
```

---

## Implementation Strategy

### MVP First (US1 + US2, highest impact)

1. Complete T001–T002 (Setup + Foundational)
2. Complete Phase 3 (US1 — link methods)
3. Complete Phase 4 (US2 — category/item listing)
4. **STOP and VALIDATE**: `pytest tests/repositories/` → all green
5. Phase 5 (US3) adds the external_id methods

### Incremental Delivery

1. T001–T002 → Protocol contract documented
2. Phase 3 → Link ordering fixed and tested
3. Phase 4 → Category/item ordering fixed and tested
4. Phase 5 → External_id ordering fixed and tested
5. Phase 6 → All quality gates pass

---

## Notes

- All three adapters (JSON, YAML, Django) must be updated for every method — no partial fixes
- Sort lambdas use `str()` on UUID fields to ensure consistent lexicographic ordering across all Python versions
- DjangoRepository ordering is delegated to the database engine via `.order_by()` — no Python-level sort needed
- `list_item_relation_links()` already filters before sorting — apply `sorted()` to the final filtered result, not the full collection
- `list_tags()` is explicitly out of scope — do not add any ordering to that method
- Service-layer methods (`list_item_relations()`, `get_items_by_external_id()`, `get_categories_by_external_id()`) need no changes — they inherit ordering from the repository layer
