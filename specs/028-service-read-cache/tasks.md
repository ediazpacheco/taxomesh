# Tasks: Service Read Cache Completeness

**Input**: Design documents from `/specs/028-service-read-cache/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓

**Organization**: Tasks are grouped by user story. US3 (write-invalidation bug
fixes) is Foundational because it is a correctness prerequisite for US1 and US2
— read caches are useless without working cache invalidation on writes.

---

## Phase 1: Setup

**Purpose**: No new project structure required. Existing
`taxomesh/application/service.py` and `tests/service/test_service_cache.py`
are the only files affected.

*No setup tasks.*

---

## Phase 2: Foundational — Write-Invalidation Bug Fixes (US3, Priority: P1)

**Purpose**: `relate_items` and `remove_item_relation` mutate relation data but
do not call `clear_all_caches()`. This is a correctness bug that MUST be fixed
before adding read-side caches — otherwise writes would silently serve stale
cached results.

**⚠️ CRITICAL**: Phase 3 and Phase 4 depend on this phase being complete.

- [x] T001 Add `clear_all_caches()` after `self._repo.save_item_relation_link(link)` in `relate_items` in `taxomesh/application/service.py`
- [x] T002 Add `clear_all_caches()` after the `delete_item_relation_link` call in `remove_item_relation` in `taxomesh/application/service.py`
- [x] T003 [P] Write test `test_relate_items_invalidates_cache` in `tests/service/test_service_cache.py` asserting that calling `list_item_relations` after `relate_items` returns the new relation (not a stale cached result)
- [x] T004 [P] Write test `test_remove_item_relation_invalidates_cache` in `tests/service/test_service_cache.py` asserting that calling `list_item_relations` after `remove_item_relation` returns an empty list

**Checkpoint**: `pytest tests/service/test_service_cache.py` — T003 and T004 pass.

---

## Phase 3: User Story 1 — External-ID Lookups Are Cache-Protected (Priority: P1) 🎯 MVP

**Goal**: `get_items_by_external_id` and `get_categories_by_external_id` return
cached results for repeated calls with the same argument within the TTL window,
reducing data-store hits on high-frequency admin page loads.

**Independent Test**: Call each method twice with the same argument and assert
the underlying repository method is called exactly once. Then mutate data and
assert the cache was invalidated.

- [x] T005 [P] [US1] Write test `test_get_items_by_external_id_cached` in `tests/service/test_service_cache.py` — call `get_items_by_external_id` twice with the same ID, assert `repo.list_items_by_external_id` is called once
- [x] T006 [P] [US1] Write test `test_get_categories_by_external_id_cached` in `tests/service/test_service_cache.py` — call `get_categories_by_external_id` twice with the same ID, assert `repo.list_categories_by_external_id` is called once
- [x] T007 [P] [US1] Write test `test_get_items_by_external_id_empty_result_cached` in `tests/service/test_service_cache.py` — verify empty-list result is also cached (SC-001)
- [x] T008 [US1] Add `@memoize(DEFAULT_CACHE_TTL)` decorator to `get_items_by_external_id` in `taxomesh/application/service.py`
- [x] T009 [US1] Add `@memoize(DEFAULT_CACHE_TTL)` decorator to `get_categories_by_external_id` in `taxomesh/application/service.py`

**Checkpoint**: `pytest tests/service/test_service_cache.py` — T005, T006, T007 pass.

---

## Phase 4: User Story 2 — Item Relation Queries Are Cache-Protected (Priority: P2)

**Goal**: `list_item_relations` and `list_related_items` return cached results
for repeated calls with the same `(item_id, relation_type, direction)` combination,
preventing repeated data-store queries during graph rendering and admin inlines.

**Independent Test**: Call each method twice with the same arguments and assert
the repository is queried once. Call again with a different `direction` and assert
it is treated as a distinct cache entry.

- [x] T010 [P] [US2] Write test `test_list_item_relations_cached` in `tests/service/test_service_cache.py` — call `list_item_relations` twice with same args, assert `repo.list_item_relation_links` called once
- [x] T011 [P] [US2] Write test `test_list_item_relations_direction_independent_cache` in `tests/service/test_service_cache.py` — assert `direction="outgoing"` and `direction="incoming"` produce independent cache entries
- [x] T012 [P] [US2] Write test `test_list_related_items_cached` in `tests/service/test_service_cache.py` — call `list_related_items` twice with same args, assert repo queried once
- [x] T013 [US2] Add `@memoize(DEFAULT_CACHE_TTL)` decorator to `list_item_relations` in `taxomesh/application/service.py`
- [x] T014 [US2] Add `@memoize(DEFAULT_CACHE_TTL)` decorator to `list_related_items` in `taxomesh/application/service.py`

**Checkpoint**: `pytest tests/service/test_service_cache.py` — T010, T011, T012 pass.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [x] T015 Run `ruff check taxomesh/application/service.py tests/service/test_service_cache.py` and fix any issues
- [x] T016 Run `mypy --strict taxomesh/application/service.py` and fix any issues
- [x] T017 Run `pytest --cov=taxomesh --cov-fail-under=80` and confirm all 750+ tests pass with ≥ 80% coverage

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — fix the bugs first.
- **US1 (Phase 3)**: Depends on Phase 2 (write bugs fixed before adding read cache).
- **US2 (Phase 4)**: Depends on Phase 2; can run in parallel with Phase 3.
- **Polish (Phase 5)**: Depends on Phases 3 and 4.

### User Story Dependencies

- **US3 / Foundational**: No dependencies. Fix first.
- **US1**: Depends on US3. Can be completed independently.
- **US2**: Depends on US3. Can run in parallel with US1.

### Parallel Opportunities

- T001 and T002 are sequential (same method bodies, but in different methods — could be parallelised by separate developers).
- T003 and T004 are parallel [P] — different test functions.
- T005, T006, T007 are parallel [P] — different test functions.
- T008 and T009 are parallel [P] — different decorator additions.
- T010, T011, T012 are parallel [P] — different test functions.
- T013 and T014 are parallel [P] — different decorator additions.

---

## Implementation Strategy

### MVP (Phase 2 + Phase 3 only)

1. Fix write-invalidation bugs (T001–T004)
2. Cache external-ID lookups (T005–T009)
3. Validate: `pytest tests/service/test_service_cache.py`

### Full Delivery

1. MVP above
2. Cache relation queries (T010–T014)
3. Polish (T015–T017)

---

## Notes

- All implementation tasks (T001, T002, T008, T009, T013, T014) modify only
  `taxomesh/application/service.py`.
- All test tasks modify only `tests/service/test_service_cache.py`.
- `clear_all_caches()` is already imported at the top of `service.py`.
- `memoize` and `DEFAULT_CACHE_TTL` are already imported at the top of `service.py`.
- No migrations, no new files, no dependency changes.
