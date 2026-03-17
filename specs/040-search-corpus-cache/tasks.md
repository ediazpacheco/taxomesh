# Tasks: Search Corpus Cache

**Input**: Design documents from `/specs/040-search-corpus-cache/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅

**Tests**: TDD is mandatory per project constitution. Test tasks appear **before** their corresponding implementation tasks in every phase. Each test task must produce failing tests before implementation begins.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)

---

## Phase 1: Setup

**Purpose**: Create the new test file skeleton with shared fixtures and imports, ready to receive test cases in subsequent phases.

- [x] T001 Create `tests/service/test_search_corpus_cache.py` with module docstring, imports (`pytest`, `unittest.mock.patch`, `unittest.mock.call`), and a `make_service` fixture that returns a `TaxomeshService` backed by the in-memory test repository (or `JsonRepository` with `tmp_path`). Add a `populate_items` helper fixture that creates 3 items with distinct names. No test functions yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the in-process call-count verification pattern used by all subsequent test groups, and verify the current (unfixed) behavior fails the target assertions. This confirms the test baseline before any implementation changes.

**⚠️ CRITICAL**: Complete before any US implementation.

- [x] T002 In `tests/service/test_search_corpus_cache.py`, add helper `count_calls(mock_fn)` that returns `mock_fn.call_count`. Then add `test_baseline_item_search_calls_repository_directly` — patch `service._repository.list_items`, call `search_items("a")` twice, assert `list_items` was called **twice** (confirming current bypassing behavior). This test documents the pre-fix baseline; it will be **removed or inverted** once T008 is implemented. Run `pytest tests/service/test_search_corpus_cache.py` and confirm it passes (current behavior).

**Checkpoint**: Baseline documented — corpus cache and hot-path fix implementation can begin.

---

## Phase 3: User Story 1 — Faster Repeated Searches (Priority: P1) 🎯 MVP

**Goal**: `search_items()` and `search_categories()` reuse memoized service data for candidate loading, and reuse pre-normalized candidate corpora across repeated searches on the same service instance.

**Independent Test**: Call `search_items(query)` twice on a warm-cache service; assert repository's `list_items` is called at most once and `service._item_corpus` is the same object on both calls.

### Tests for User Story 1 — write FIRST, confirm they FAIL before implementation

- [x] T003 [US1] In `tests/service/test_search_corpus_cache.py`, add `test_item_search_reuses_memoized_list_items`: patch `service._repository.list_items` as a wrapping spy; call `search_items("a")` then `search_items("b")`; assert `list_items` was called exactly **once** across both calls. Run pytest and confirm **FAIL**.

- [x] T004 [US1] In `tests/service/test_search_corpus_cache.py`, add `test_item_corpus_built_once_and_reused`: call `search_items("a")`; capture `corpus_id_1 = id(service._item_corpus)`; call `search_items("b")`; assert `id(service._item_corpus) == corpus_id_1` (same list object). Run pytest and confirm **FAIL**.

- [x] T005 [US1] In `tests/service/test_search_corpus_cache.py`, add `test_category_search_reuses_memoized_load` and `test_category_corpus_built_once_and_reused` — same patterns as T003/T004 but for `search_categories("a")` and `service._category_corpus`. Run pytest and confirm **FAIL**.

- [x] T006 [US1] In `tests/service/test_search_corpus_cache.py`, add `test_cold_cache_item_search_returns_correct_results`: create service with no prior calls; call `search_items("exact_name")`; assert the matching item is in results and count equals expected. This guards FR-004 (cold cache works). Run pytest and confirm **PASS** (current behavior correct on cold cache).

### Implementation for User Story 1

- [x] T007 [US1] In `taxomesh/application/service.py`, add two private nullable instance attributes to `TaxomeshService.__init__` after the `_engine` initialization line:
  ```python
  self._item_corpus: list[SearchCandidate[Item]] | None = None
  self._category_corpus: list[SearchCandidate[Category]] | None = None
  ```
  Ensure `SearchCandidate` import is already present (it is — used in `_score_and_rank`). Run `mypy --strict taxomesh/application/service.py` and confirm no errors.

- [x] T008 [US1] In `taxomesh/application/service.py`, fix `_load_item_candidates()`: change the `category_id is None` branch from `self._repository.list_items()` to `self.list_items()`. This single-line change routes unfiltered candidate loading through the memoized service method. Run T003 and confirm it now **PASSES**.

- [x] T009 [US1] In `taxomesh/application/service.py`, add private method `_get_item_corpus(self) -> list[SearchCandidate[Item]]`. If `_item_corpus is None`, call `self.list_items()`, build a `SearchCandidate` for each item using `SearchEngine.normalize()` on `item.name`, `item.slug`, and `item.external_id` (use `""` if `external_id` is falsy), assign to `self._item_corpus`, and return it. If already built, return it directly. Add Google-style docstring. Run `mypy --strict taxomesh/application/service.py`.

- [x] T010 [US1] In `taxomesh/application/service.py`, add private method `_get_category_corpus(self) -> list[SearchCandidate[Category]]`. Same pattern as `_get_item_corpus()`: load all categories via the service memoized path (exclude the internal root category using `self._root_id`), build `SearchCandidate` wrappers, cache in `self._category_corpus`. Add Google-style docstring. Run `mypy --strict taxomesh/application/service.py`.

- [x] T011 [US1] In `taxomesh/application/service.py`, add private method `_score_corpus(self, norm_q: str, corpus: list[SearchCandidate[_T]], *, fuzzy: bool, limit: int) -> list[_T]`. This method iterates the corpus and calls `self._engine._score_prenorm(norm_q, cand.norm_name, cand.norm_slug, cand.norm_ext, fuzzy=fuzzy)` for each candidate — skipping field normalization (already done at corpus build time). Apply the same heapq/sort logic as `_score_and_rank()` for ranking. Add Google-style docstring. Add `_T = TypeVar("_T")` at module level if not already present. Run `mypy --strict taxomesh/application/service.py`.

- [x] T012 [US1] In `taxomesh/application/service.py`, update `search_items()`: in the `category_id is None` path (after the empty-query guard), replace the existing candidate-load + `_score_and_rank()` call with: get corpus via `_get_item_corpus()`, filter by `enabled_only` if applicable, call `_score_corpus(norm_q, filtered_corpus, fuzzy=fuzzy, limit=limit)`. The `category_id is not None` path is left completely unchanged. Run T003, T004, T006 and confirm all **PASS**.

- [x] T013 [US1] In `taxomesh/application/service.py`, update `search_categories()`: in the `parent_id is None` path, replace existing candidate load with `_get_category_corpus()` and use `_score_corpus()`. The `parent_id is not None` path is left unchanged. Run T005 and confirm **PASS**.

- [x] T014 [US1] Remove the baseline test `test_baseline_item_search_calls_repository_directly` added in T002 — it documented pre-fix behavior and is now inverted by T003. Run `pytest tests/service/test_search_corpus_cache.py` and confirm all US1 tests pass.

**Checkpoint**: User Story 1 complete. `search_items()` and `search_categories()` reuse memoized data and pre-normalized corpora on warm cache. Verify independently with `pytest tests/service/test_search_corpus_cache.py`.

---

## Phase 4: User Story 2 — Cache Invalidation on Writes (Priority: P2)

**Goal**: All item and category write operations invalidate the respective corpus cache. Searches after writes return results consistent with the updated state.

**Independent Test**: Create an item, call `search_items()`, create another item, call `search_items()` again — second call must include the new item.

### Tests for User Story 2 — write FIRST, confirm they FAIL before implementation

- [x] T015 [P] [US2] In `tests/service/test_search_corpus_cache.py`, add the following three tests (item corpus invalidated by writes):
  - `test_create_item_invalidates_item_corpus`: warm corpus, call `create_item(...)`, assert `service._item_corpus is None`.
  - `test_update_item_invalidates_item_corpus`: warm corpus, call `update_item(...)`, assert `service._item_corpus is None`.
  - `test_delete_item_invalidates_item_corpus`: warm corpus, call `delete_item(...)`, assert `service._item_corpus is None`.
  Run pytest and confirm all three **FAIL**.

- [x] T016 [P] [US2] In `tests/service/test_search_corpus_cache.py`, add the following three tests (category corpus invalidated by writes):
  - `test_create_category_invalidates_category_corpus`: warm corpus, call `create_category(...)`, assert `service._category_corpus is None`.
  - `test_update_category_invalidates_category_corpus`: warm corpus, call `update_category(...)`, assert `service._category_corpus is None`.
  - `test_delete_category_invalidates_category_corpus`: warm corpus, call `delete_category(...)`, assert `service._category_corpus is None`.
  Run pytest and confirm all three **FAIL**.

- [x] T017 [US2] In `tests/service/test_search_corpus_cache.py`, add correctness tests:
  - `test_new_item_appears_in_search_after_create`: warm corpus, create item named `"Piazzolla Tango"`, call `search_items("piazzolla")`, assert item in results.
  - `test_updated_item_name_searchable_after_update`: warm corpus, update item name, search with new name, assert updated item in results.
  - `test_deleted_item_absent_from_search_after_delete`: warm corpus, delete item, search by its original name, assert item not in results.
  - `test_new_category_appears_in_search_after_create`: symmetric for categories.
  Run pytest and confirm all four **FAIL** (corpus not yet invalidated).

### Implementation for User Story 2

- [x] T018 [P] [US2] In `taxomesh/application/service.py`, add `self._item_corpus = None` immediately after the `clear_all_caches()` call in each of: `create_item()`, `update_item()`, `delete_item()`. Place the assignment on its own line following the `clear_all_caches()` call. Run T015 and confirm all three **PASS**.

- [x] T019 [P] [US2] In `taxomesh/application/service.py`, add `self._category_corpus = None` immediately after the `clear_all_caches()` call in each of: `create_category()`, `update_category()`, `delete_category()`. Run T016 and confirm all three **PASS**.

- [x] T020 [US2] Run the full User Story 2 test group including T017 and confirm all correctness tests pass. If any fail, diagnose and fix the ordering of `_item_corpus = None` relative to the write operation.

**Checkpoint**: User Story 2 complete. Writes correctly invalidate corpora. Searches after writes are always consistent.

---

## Phase 5: User Story 3 — Stable Public Search Behavior (Priority: P3)

**Goal**: Existing search behavior and ranking semantics are unaffected by the optimization. Fuzzy and non-fuzzy search, empty queries, and cross-backend compatibility all pass.

**Independent Test**: Run the full existing search test suite against Django, YAML, and JSON repository fixtures with the optimization applied; zero regressions.

### Tests for User Story 3 — write FIRST, confirm they FAIL or PASS appropriately

- [x] T021 [US3] In `tests/service/test_search_corpus_cache.py`, add ranking regression tests:
  - `test_exact_match_ranked_first`: create items `"Piazzolla"` and `"Piazzolla Tango Nuevo"`; call `search_items("piazzolla")`; assert `"Piazzolla"` is `results[0]`.
  - `test_fuzzy_search_returns_near_match`: create item `"Piazzolla"`; call `search_items("piazola", fuzzy=True)`; assert item in results.
  - `test_non_fuzzy_excludes_fuzzy_only_match`: create item `"Piazzolla"`; call `search_items("piazola", fuzzy=False)`; assert item **not** in results (no deterministic match for misspelling).
  - `test_empty_query_returns_empty`: assert `search_items("") == []`.
  - `test_whitespace_query_returns_empty`: assert `search_items("   ") == []`.
  Run pytest. `test_empty_query_returns_empty` and `test_whitespace_query_returns_empty` should already **PASS** (behavior unchanged). Ranking tests should **PASS** if `_score_corpus` is correctly implemented. If any ranking tests fail, record the failure — it indicates a scoring regression introduced by `_score_corpus()`.

### Implementation for User Story 3

- [x] T022 [US3] If any ranking test from T021 fails, diagnose `_score_corpus()` in `taxomesh/application/service.py`: compare its sort key `(-score, cand.norm_name)` and result extraction against `_score_and_rank()`. Align behavior. If all tests already pass, this task is a no-op — confirm with `pytest tests/service/test_search_corpus_cache.py -k "ranking or empty or whitespace"`.

- [x] T023 [US3] Run the **existing** search test suite to verify zero regressions: `pytest tests/ -k "search" -v`. All pre-existing search tests must pass. If any fail, diagnose the failure — likely caused by an unintended change to `_score_and_rank()` or the filtered path in `search_items()`/`search_categories()`. Fix without modifying the filtered paths.

**Checkpoint**: User Story 3 complete. All existing search semantics and ranking behavior preserved.

---

## Phase 6: User Story 4 — Filtered and Recursive Search Unaffected (Priority: P4)

**Goal**: `search_items(category_id=X)` and recursive search still work correctly. Item placement changes do not invalidate the item corpus. Category parent-link changes do not invalidate the category corpus.

**Independent Test**: Search with `category_id=X` returns only items in X; placing an item in a category does not reset `service._item_corpus`.

### Tests for User Story 4 — write FIRST, confirm they FAIL or PASS appropriately

- [x] T024 [US4] In `tests/service/test_search_corpus_cache.py`, add:
  - `test_filtered_search_with_category_id_restricts_results`: place item A in category C1, item B in category C2; search `category_id=C1` for a query matching both; assert only item A is returned.
  - `test_recursive_search_returns_subtree_items`: create root category R, child category C, place item in C; search with `category_id=R, recursive=True`; assert item in results.
  - `test_place_item_in_category_does_not_invalidate_corpus`: warm item corpus, `place_item_in_category(...)`, assert `service._item_corpus is not None` (corpus survives).
  - `test_add_category_parent_does_not_invalidate_category_corpus`: warm category corpus, `add_category_parent(...)`, assert `service._category_corpus is not None`.
  Run pytest. The placement/link non-invalidation tests should **FAIL** if T018/T019 incorrectly invalidated on all writes; filtered search tests should **PASS** since the filtered path was not changed.

### Implementation for User Story 4

- [x] T025 [US4] Verify that `place_item_in_category()`, `remove_item_from_category()`, and `reparent_item()` in `taxomesh/application/service.py` do **not** have `self._item_corpus = None` added (i.e., confirm T018 only touched `create_item`, `update_item`, `delete_item`). Similarly verify `add_category_parent()`, `remove_category_parent()`, `reparent_category()` do not clear `_category_corpus`. If they do, remove the erroneous assignments. Run T024 corpus-survival tests and confirm **PASS**.

- [x] T026 [US4] Run the full `pytest tests/ -v` suite to confirm the complete test suite passes with zero failures or regressions.

**Checkpoint**: User Story 4 complete. All placement and link operations leave corpus caches intact.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Docstring accuracy, type safety, code style, and quality gate passage.

- [x] T027 [P] Update the docstring of `search_items()` in `taxomesh/application/service.py` to note that unfiltered search reuses a pre-normalized internal candidate corpus for performance. Keep docstring generic (no backend-specific mention). Follow Google style.

- [x] T028 [P] Update the docstring of `search_categories()` in `taxomesh/application/service.py` symmetrically.

- [x] T029 [P] Add Google-style module-level docstrings to `_get_item_corpus()`, `_get_category_corpus()`, and `_score_corpus()` if not already added in T009–T011. Confirm private methods are prefixed with `_` and exempt from public docstring requirement per constitution.

- [x] T030 Run all quality gates from repository root and confirm all pass:
  ```bash
  ruff check .
  ruff format --check .
  mypy --strict .
  pytest --cov=taxomesh --cov-fail-under=80
  ```
  Fix any ruff, mypy, or coverage failures before marking this task complete. Line length must be 119 (per `pyproject.toml`). No `Any` without justification.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1 (test file must exist).
- **US1 (Phase 3)**: Depends on Phase 2 completion — write tests first (T003–T006), then implement (T007–T014).
- **US2 (Phase 4)**: Depends on Phase 3 completion — corpus must exist before invalidation logic is meaningful.
- **US3 (Phase 5)**: Can start after Phase 3 is complete — regression tests run on the already-implemented corpus path.
- **US4 (Phase 6)**: Can start after Phase 4 — placement non-invalidation tests require invalidation to be wired first.
- **Polish (Phase 7)**: Depends on Phases 3–6 completion.

### User Story Dependencies

- **US1 (P1)**: No dependency on other user stories. Delivers the core optimization.
- **US2 (P2)**: Depends on US1 — the corpus must exist to be invalidated.
- **US3 (P3)**: Independent of US2 — regression tests run on the optimized path from US1.
- **US4 (P4)**: Depends on US2 — verifies placement ops do not invalidate corpus set up in US2.

### Within Each User Story

- Test tasks MUST be written and confirmed FAILING before implementation begins.
- Attributes before methods before callers (T007 → T009/T010/T011 → T012/T013).
- Each phase ends with a `pytest` run to confirm all tests in that phase pass.

### Parallel Opportunities

- T003 and T004 (US1 tests) can be written in parallel — different functions in same file.
- T005 and T006 can be written in parallel with T003/T004.
- T009 (`_get_item_corpus`) and T010 (`_get_category_corpus`) can be implemented in parallel — independent methods.
- T015 and T016 (US2 tests) can be written in parallel — different entity types.
- T018 and T019 (US2 impl) can be applied in parallel — different write methods.
- T027, T028, T029 (docstrings) can be written in parallel.

---

## Parallel Example: User Story 1

```
Write these failing tests together:
  T003: test_item_search_reuses_memoized_list_items
  T004: test_item_corpus_built_once_and_reused
  T005: test_category_search_reuses_memoized_load / test_category_corpus_built_once_and_reused
  T006: test_cold_cache_item_search_returns_correct_results

Then implement these independently (different methods in same file):
  T009: _get_item_corpus()
  T010: _get_category_corpus()
  T011: _score_corpus()
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Create test file skeleton (T001)
2. Complete Phase 2: Baseline documentation (T002)
3. Complete Phase 3: Write failing tests → implement hot-path fix + corpus caches
4. **STOP and VALIDATE**: `pytest tests/service/test_search_corpus_cache.py`
5. The library already delivers hot-path reuse at this point

### Incremental Delivery

1. Phase 1+2+3 → US1 done → corpus caches working
2. Phase 4 (US2) → writes correctly invalidate → correctness confirmed
3. Phase 5 (US3) → zero regressions confirmed
4. Phase 6 (US4) → filtered/placement behavior confirmed
5. Phase 7 → quality gates pass → ready for PR

---

## Notes

- All changes confined to `taxomesh/application/service.py` and `tests/service/test_search_corpus_cache.py`
- No new modules, no repository changes, no public API changes
- TDD is mandatory: failing tests before every implementation block
- `[P]` tasks = different methods or independent fixtures — safe to write in one session
- Corpus caches are `None`-sentinel, not TTL-based — see `research.md` R-002 for rationale
- Placement operations (`place_item_in_category`, `add_category_parent`, etc.) must NOT invalidate the corpus — see `data-model.md` invalidation matrix
