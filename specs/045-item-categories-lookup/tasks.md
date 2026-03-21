# Tasks: Item-to-Categories Lookup

**Input**: Design documents from `/specs/045-item-categories-lookup/`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/service-api.md ✅

**Tests**: TDD is mandatory (CLAUDE.md). All test tasks must be written and confirmed RED before the implementation task runs.

**Organization**: Tasks grouped by user story to enable independent verification of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared in-flight dependencies)
- **[Story]**: User story this task belongs to (US1–US4)

---

## Phase 1: Setup

**Purpose**: No new project structure or dependencies required — this feature adds a single service method using existing infrastructure. No setup tasks.

*(Skipped — nothing to set up)*

---

## Phase 2: Foundational

**Purpose**: No new protocol methods, no new domain entities, no new repository changes — all foundations are in place.

*(Skipped — `list_item_parent_links()` confirmed present in all backends; `clear_all_caches()` covers all write paths)*

---

## Phase 3: User Story 1 — Resolve item placement from the service (Priority: P1) 🎯 MVP

**Goal**: `service.list_categories_by_item(item_id)` returns the correct categories for an item, ordered by `sort_index` ascending.

**Independent Test**:
```bash
pytest tests/service/test_service_list_categories_by_item.py -k "us1"
```

### Tests for User Story 1 ⚠️ Write FIRST — must be RED before T003

- [x] T001 [US1] Create `tests/service/test_service_list_categories_by_item.py` with three US1 test cases: `test_single_category_returned`, `test_multiple_categories_ordered_by_sort_index`, `test_removed_placement_not_in_result`
- [x] T002 [US1] Verify T001 is RED: run `pytest tests/service/test_service_list_categories_by_item.py` — all three tests must fail with `AttributeError` (method does not exist yet)

### Implementation for User Story 1

- [x] T003 [US1] Add `list_categories_by_item(self, item_id: UUID) -> list[Category]` to `taxomesh/application/service.py` immediately after `list_items` — decorated with `@memoize(DEFAULT_CACHE_TTL)`, with full Google-style docstring per constitution
- [x] T004 [US1] Verify T001 is GREEN: run `pytest tests/service/test_service_list_categories_by_item.py -k "us1"` — all three tests must pass

**Checkpoint**: `list_categories_by_item` functional for the happy path. US1 independently testable.

---

## Phase 4: User Story 2 — Handle items with no categorical placement (Priority: P2)

**Goal**: Method returns `[]` for an item that exists but has never been placed in any category.

**Independent Test**:
```bash
pytest tests/service/test_service_list_categories_by_item.py -k "us2"
```

### Test for User Story 2 ⚠️ Write FIRST — must be verified RED or GREEN

- [x] T005 [US2] Add test `test_empty_when_item_has_no_placements` to `tests/service/test_service_list_categories_by_item.py`
- [x] T006 [US2] Verify T005 passes: run `pytest tests/service/test_service_list_categories_by_item.py -k "us2"` — this should pass as a consequence of the T003 implementation; if it fails, fix `list_categories_by_item` in `taxomesh/application/service.py`

**Checkpoint**: Empty-list case confirmed. US2 independently testable.

---

## Phase 5: User Story 3 — Reject lookup for non-existent items (Priority: P2)

**Goal**: Method raises `TaxomeshItemNotFoundError` when called with an item UUID that does not exist.

**Independent Test**:
```bash
pytest tests/service/test_service_list_categories_by_item.py -k "us3"
```

### Test for User Story 3 ⚠️ Write FIRST — must be verified RED or GREEN

- [x] T007 [US3] Add test `test_nonexistent_item_raises` to `tests/service/test_service_list_categories_by_item.py` — call with `uuid4()` never created, assert `TaxomeshItemNotFoundError` is raised
- [x] T008 [US3] Verify T007 passes: run `pytest tests/service/test_service_list_categories_by_item.py -k "us3"` — this should pass via `self.get_item(item_id)` guard in T003; if it fails, fix in `taxomesh/application/service.py`

**Checkpoint**: Error contract confirmed. US3 independently testable.

---

## Phase 6: User Story 4 — Include disabled categories in structural reads (Priority: P3)

**Goal**: Method returns disabled categories unchanged; cache is invalidated after placement changes.

**Independent Test**:
```bash
pytest tests/service/test_service_list_categories_by_item.py -k "us4"
```

### Tests for User Story 4 ⚠️ Write FIRST — must be verified RED or GREEN

- [x] T009 [P] [US4] Add test `test_disabled_category_included` to `tests/service/test_service_list_categories_by_item.py` — place item in category, disable category via direct `service._repo.save_category()` + `clear_all_caches()` (no public `update_category(enabled=...)` exists), assert disabled category still appears in result
- [x] T010 [P] [US4] Add test `test_cache_invalidated_after_place` to `tests/service/test_service_list_categories_by_item.py` — call method once (cache primed), then `place_item_in_category` for a new category, call again and assert new category is in result
- [x] T011 [US4] Verify T009 and T010 pass: run `pytest tests/service/test_service_list_categories_by_item.py -k "us4"` — both tests must pass; if either fails, fix in `taxomesh/application/service.py`

**Checkpoint**: All seven test cases green. US4 independently testable.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation updates and final quality verification.

- [x] T012 [P] Update `README.md` — add subsection "Resolving which categories an item belongs to" per plan.md T-03, between the quick-start example and the "Resolving items and categories by external_id" section
- [x] T013 [P] Update `CHANGELOG.md` — add entry under `## [Unreleased]` per plan.md T-04 describing `list_categories_by_item` behavior, sort order, error, caching, and no-filter contract
- [x] T014 Run full quality gate: `ruff check . && ruff format --check . && mypy --strict . && pytest --cov=taxomesh --cov-fail-under=80` — all must pass before proposing a commit

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 & 2**: Skipped — no setup or foundational work required
- **Phase 3 (US1)**: No dependencies — start immediately
- **Phase 4 (US2)**: Depends on T003 (method must exist to be testable)
- **Phase 5 (US3)**: Depends on T003 (method must exist to be testable)
- **Phase 6 (US4)**: Depends on T003 (method must exist to be testable)
- **Phase 7**: Depends on all story phases complete (T011 done)

### Task-Level Dependencies

```
T001 → T002 → T003 → T004
                ↓
T005 → T006 (verify)
T007 → T008 (verify)
T009 ┐
     ├→ T011 (verify)
T010 ┘
             ↓
       T012, T013 [parallel] → T014
```

### User Story Dependencies

- **US1 (P1)**: No dependencies — core deliverable
- **US2 (P2)**: Depends on US1 implementation (same method)
- **US3 (P2)**: Depends on US1 implementation (same method)
- **US4 (P3)**: Depends on US1 implementation (same method)

---

## Parallel Opportunities

```bash
# T009 and T010 (US4 tests) can be written in parallel — different test functions, same file
# T012 and T013 (docs) can be written in parallel — different files
```

---

## Implementation Strategy

### MVP (User Story 1 only)

1. T001 → T002 (write tests, confirm red)
2. T003 (implement method)
3. T004 (confirm green)
4. **STOP and validate**: `pytest tests/service/test_service_list_categories_by_item.py -k "us1"`

### Full Delivery (all stories)

1. Complete Phase 3 (US1) — core implementation
2. Phase 4 (US2) → Phase 5 (US3) → Phase 6 (US4) — add tests, verify each passes
3. Phase 7 — docs + quality gate
4. Propose commit

---

## Notes

- TDD gate at T002: do not proceed to T003 unless tests are confirmed failing
- All 7 test cases live in `tests/service/test_service_list_categories_by_item.py` — one file, one method under test
- `service` fixture from `tests/service/conftest.py` is parametrized over InMemoryRepository, JsonRepository, YAMLRepository, and DjangoRepository — all backends run every test
- No repository, protocol, or domain-model changes required
- The implementation body is ~5 lines (see plan.md T-02 for exact code)
