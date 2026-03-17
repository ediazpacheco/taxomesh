# Tasks: Search Performance for Autocomplete

**Input**: Design documents from `specs/039-search-perf/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/public-api.md ✅

**Tests**: TDD is mandatory per CLAUDE.md — all implementation tasks have a preceding test task that must FAIL before implementation begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are included in every task

---

## Phase 1: Setup

**Purpose**: Create new test file skeleton so test tasks in later phases have a target file.

- [x] T001 Create `tests/service/test_search_engine.py` with module docstring, imports (`pytest`, `SearchEngine`, `SearchCandidate` placeholder), and empty body — no test functions yet

---

## Phase 2: Foundational (Blocking Prerequisite)

**Purpose**: Confirm the existing test suite is green before any changes are made. This is the baseline all subsequent tests measure against.

**⚠️ CRITICAL**: Must pass before any user story work begins.

- [x] T002 Run `pytest tests/service/test_service_search.py -v` and confirm all existing tests pass; record failure count as baseline (expected: 0 failures)

**Checkpoint**: Baseline confirmed — user story implementation can now begin.

---

## Phase 3: User Story 1 — Fast Autocomplete Results (Priority: P1) 🎯 MVP

**Goal**: `search_items()` and `search_categories()` return the same top-`limit` results as today, but use `heapq.nlargest` instead of a full sort when `limit < len(scored)`, reducing O(N log N) to O(N log k).

**Independent Test**: Run `pytest tests/service/test_service_search.py -v -k "topk or fuzzy_limit"` — all new tests pass, no existing tests regress.

### Tests for User Story 1

> **⚠️ Write these tests FIRST — they MUST FAIL before implementation (T005)**

- [x] T003 [P] [US1] Add test `test_topk_matches_full_sort` to `tests/service/test_service_search.py`: build a catalog of 50 items, run `search_items(query, limit=5)` with the optimized path and compare result IDs and order to a brute-force full-sort reference across ≥10 distinct queries (50-item catalog × 10 queries = 50 query/catalog combinations, satisfying SC-002); assert lists are identical
- [x] T004 [P] [US1] Add test `test_fuzzy_match_survives_small_limit` to `tests/service/test_service_search.py`: given a catalog where a fuzzy match ranks in the top 3, calling `search_items(typo_query, limit=3, fuzzy=True)` must include the expected item

### Implementation for User Story 1

- [x] T005 [US1] In `taxomesh/application/service.py` `_score_and_rank`: replace `scored.sort(key=lambda t: (-t[0], t[1]))` + `scored[:limit]` with `heapq.nlargest(limit, scored, key=lambda t: (-t[0], t[1]))` when `limit < len(scored)`, keeping the sort path as fallback; add `import heapq` at top of file — run T003 and T004 and confirm they now pass

**Checkpoint**: User Story 1 complete — top-k selection is live. `pytest tests/service/test_service_search.py -v` must be fully green.

---

## Phase 4: User Story 2 — Pre-Normalized Candidate Fields (Priority: P2)

**Goal**: Candidate fields (name, slug, external_id) are normalized once per search call via `SearchCandidate`, eliminating the current double-normalization of names and the repeated slug/ext normalization per candidate.

**Independent Test**: Run `pytest tests/service/test_search_engine.py -v` — all new engine-level tests pass; run `pytest tests/service/test_service_search.py -v` — no regressions.

### Tests for User Story 2

> **⚠️ Write these tests FIRST — they MUST FAIL before implementation (T008, T009, T010)**

- [x] T006 [P] [US2] Add test `test_search_candidate_stores_prenormalized_fields` to `tests/service/test_search_engine.py`: construct a `SearchCandidate` with a raw name containing diacritics (e.g. `"Ñoño"`) and assert `norm_name == SearchEngine.normalize("Ñoño")`; repeat for slug and external_id
- [x] T007 [P] [US2] Add test `test_score_prenorm_matches_score_candidate` to `tests/service/test_search_engine.py`: for each match type (exact, prefix, word-prefix, substring, fuzzy), assert that `SearchEngine._score_prenorm(norm_q, norm_name, norm_slug, norm_ext, fuzzy=True)` returns the same value as `SearchEngine().score_candidate(norm_q, raw_name, raw_slug, raw_ext, fuzzy=True)` when the pre-normalized fields were produced by `SearchEngine.normalize()`

### Implementation for User Story 2

- [x] T008 [P] [US2] Add `SearchCandidate` class to `taxomesh/application/search.py`: private generic class (Principle XI) with `obj: _T`, `norm_name: str`, `norm_slug: str`, `norm_ext: str`; use `TypeVar` and `Generic`; add Google-style docstring; do NOT export from module `__all__`
- [x] T009 [US2] Add `SearchEngine._score_prenorm()` private method to `taxomesh/application/search.py` (depends on T008): accepts `(norm_q, norm_name, norm_slug, norm_ext, *, fuzzy)` — all pre-normalized; delegates to existing `_compute_boost` and `_compute_fuzzy`; refactor `score_candidate` to normalize its inputs then call `_score_prenorm` (eliminates logic duplication per research.md Finding 2); add Google-style docstring to `_score_prenorm`
- [x] T010 [US2] Refactor `TaxomeshService._score_and_rank()` in `taxomesh/application/service.py` (depends on T008, T009): build `list[SearchCandidate[_T]]` from `candidates` at the start of the method (pre-normalize name, slug, ext once each); replace `engine.score_candidate(norm_q, norm_name, get_slug(c), get_ext(c), ...)` with `engine._score_prenorm(norm_q, sc.norm_name, sc.norm_slug, sc.norm_ext, ...)`; keep `heapq.nlargest` from T005; run T006 and T007 and confirm they now pass

**Checkpoint**: User Story 2 complete — each candidate field normalized once per call. `pytest tests/service/ -v` must be fully green.

---

## Phase 5: User Story 3 — Deterministic Ordering (Priority: P3)

**Goal**: Tie-breaking by normalized name is stable and produces identical output to the pre-optimization behavior for all result positions up to `limit`.

**Independent Test**: Run `pytest tests/service/test_service_search.py -v -k "ordering or tiebreak"` — all ordering tests pass.

### Tests for User Story 3

> **⚠️ Write these tests FIRST — they MUST FAIL (or at minimum be written) before verification (T013)**

- [x] T011 [P] [US3] Add test `test_tie_breaking_by_norm_name` to `tests/service/test_service_search.py`: create 5 items with identical names that produce equal scores for a given query; assert the result list is sorted by `SearchEngine.normalize(item.name)` ascending
- [x] T012 [P] [US3] Add test `test_topk_order_identical_to_full_sort` to `tests/service/test_service_search.py`: for a catalog of 100 items and `limit=10`, assert that result IDs and their order are identical to a reference list produced by the original `sorted(...) + [:limit]` logic across ≥5 distinct queries

### Implementation for User Story 3

- [x] T013 [US3] Run `pytest tests/service/test_service_search.py -v -k "ordering or tiebreak"` after T010 to confirm T011 and T012 pass; if any ordering regression is found, fix the `key=lambda t: (-t[0], t[1])` expression in `_score_and_rank` in `taxomesh/application/service.py` and re-run until green

**Checkpoint**: All three user stories complete. `pytest tests/service/ -v` must be fully green.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, quality gates, final validation.

- [x] T014 [P] Add an `[Unreleased]` section entry to `CHANGELOG.md`: "Performance: `search_items()` and `search_categories()` now pre-normalize candidate fields once per call and use top-k heap selection when `limit` is smaller than the result set, reducing per-keystroke cost for autocomplete workloads"
- [x] T015 [P] Update `README.md` search section: note that `search_items()` and `search_categories()` are optimized for autocomplete (per-keystroke) usage patterns with no API changes required
- [x] T016 Run full quality gates in order: `ruff check .`, `ruff format --check .`, `mypy --strict .`, `pytest --cov=taxomesh --cov-fail-under=80`; fix any issues before proposing a commit

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1
- **US1 (Phase 3)**: Depends on Phase 2
- **US2 (Phase 4)**: Depends on Phase 2; T009 depends on T008; T010 depends on T008+T009+T005
- **US3 (Phase 5)**: Depends on Phase 4 (ordering validation is meaningful only after refactor is complete)
- **Polish (Phase 6)**: Depends on Phase 5

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependency on US2 or US3
- **US2 (P2)**: Can start after Phase 2 — T010 depends on T005 from US1 being done first (shares `_score_and_rank`)
- **US3 (P3)**: Verification only — depends on US2 completion (ordering must hold after full refactor)

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- T008 (SearchCandidate class) must precede T009 (_score_prenorm) and T010 (wiring)
- T005 (heapq) must precede T010 (combined refactor)
- T013 is a run-and-fix task that depends on T011, T012 existing

### Parallel Opportunities

- T003 and T004 can be written in parallel (different test functions, same file — coordinate to avoid conflicts)
- T006 and T007 can be written in parallel (different test functions, same file — coordinate)
- T008 (search.py) and T005 (service.py) can be worked in parallel (different files)
- T011 and T012 can be written in parallel (different test functions)
- T014 and T015 can be done in parallel (different files)

---

## Parallel Example: User Story 2

```bash
# These two test tasks touch different test functions in test_search_engine.py — coordinate or do sequentially:
Task T006: "Add test_search_candidate_stores_prenormalized_fields to tests/service/test_search_engine.py"
Task T007: "Add test_score_prenorm_matches_score_candidate to tests/service/test_search_engine.py"

# Once tests exist and fail, these two implementation tasks touch different files:
Task T008: "Add SearchCandidate class to taxomesh/application/search.py"
# (no parallel partner for T009/T010 — they depend on T008 and T005)
```

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational baseline check
3. Write T003, T004 → confirm they fail
4. Implement T005 (heapq swap) → run T003, T004 → confirm pass
5. **STOP and VALIDATE**: `pytest tests/service/test_service_search.py -v` fully green
6. This alone delivers the top-k performance gain

### Incremental Delivery

1. Setup + Foundational → green baseline
2. US1 (T003–T005) → top-k selection live ✅
3. US2 (T006–T010) → pre-normalization live ✅ (larger gain for large catalogs)
4. US3 (T011–T013) → ordering stability verified ✅
5. Polish (T014–T016) → docs + quality gates ✅

---

## Notes

- [P] tasks = different files or non-conflicting additions; safe to parallelize
- TDD is mandatory — every impl task has a preceding test task that must fail first
- `score_candidate` public method must remain unchanged; optimization goes through `_score_prenorm`
- `SearchCandidate` is private; must not appear in any public signature or `__all__`
- All quality gates (ruff, mypy --strict, pytest ≥80% cov) must pass before proposing a commit
