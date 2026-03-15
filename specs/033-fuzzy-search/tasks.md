# Tasks: Fuzzy Search APIs

**Input**: Design documents from `/specs/033-fuzzy-search/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: TDD is mandatory per project constitution. Every implementation task is preceded by a
failing-test task. Gate: tests must be red before implementation begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete sibling tasks)
- **[Story]**: Which user story this task belongs to (US1–US5)

---

## Phase 1: Setup

**Purpose**: Add the new runtime dependency so the project environment is ready.

- [ ] T001 Add `rapidfuzz>=3.0` to `[project] dependencies` in `pyproject.toml`
- [ ] T002 Run `uv sync` (or `pip install -e ".[dev]"`) to install `rapidfuzz` and verify `import rapidfuzz` works

---

## Phase 2: Foundational — `SearchEngine` (Blocking Prerequisite)

**Purpose**: Implement the `SearchEngine` class that ALL user stories depend on. No user story
work can begin until this phase is complete.

**⚠️ CRITICAL**: Phase 3–7 depend entirely on this phase.

### Normalization

- [ ] T003 Write failing tests for `SearchEngine.normalize()` in `tests/service/test_service_search.py`: accent removal (`Agustín` → `agustin`), apostrophe-to-space (`D'Arienzo` → `d arienzo`), dash-to-space (`gallo-ciego` → `gallo ciego`), whitespace collapse, lowercase; confirm tests are RED
- [ ] T004 Create `taxomesh/application/search.py` with module docstring and `SearchEngine` class skeleton: all method signatures must carry full type annotations (`normalize(text: str) -> str` and `score_candidate(query: str, name: str, slug: str, external_id: str, *, fuzzy: bool = True) -> float | None`); method bodies use `...`; the file must pass `mypy --strict` before any implementation begins
- [ ] T005 Implement `SearchEngine.normalize(text: str) -> str` as a `@staticmethod` in `taxomesh/application/search.py` using `unicodedata` NFD decomposition + combining-mark removal + punctuation-to-space + collapse + lowercase
- [ ] T006 Gate: run `pytest tests/service/test_service_search.py -k normalize` — all normalization tests must pass

### Non-Fuzzy Scoring

- [ ] T007 Define all scoring constants in `taxomesh/application/search.py` as `Final[int]`: `BOOST_EXACT=1000`, `BOOST_PREFIX_NAME=500`, `BOOST_PREFIX_SLUG=400`, `BOOST_WORD_PREFIX=300`, `BOOST_SUBSTRING_NAME=200`, `BOOST_SUBSTRING_SLUG=150`, `BOOST_SUBSTRING_EXT=50`, `FUZZY_THRESHOLD=70`
- [ ] T008 Add failing tests for `SearchEngine.score_candidate()` non-fuzzy signals to `tests/service/test_service_search.py`: exact name → score ≥ `BOOST_EXACT`; prefix name → score ≥ `BOOST_PREFIX_NAME`; word-prefix → score ≥ `BOOST_WORD_PREFIX`; substring name → score ≥ `BOOST_SUBSTRING_NAME`; substring slug → score ≥ `BOOST_SUBSTRING_SLUG`; substring external_id (non-empty) → score ≥ `BOOST_SUBSTRING_EXT`; `external_id=""` sentinel → external_id boost NOT applied; no match → returns `None`; confirm tests are RED
- [ ] T009 Implement the non-fuzzy boost logic in `SearchEngine.score_candidate(query: str, name: str, slug: str, external_id: str, *, fuzzy: bool = True) -> float | None` in `taxomesh/application/search.py` (skip RapidFuzz for now — return `None` when no boost and no fuzzy, or accumulated boost when `fuzzy=False`)
- [ ] T010 Gate: run `pytest tests/service/test_service_search.py -k score_candidate` — non-fuzzy scoring tests must pass

### Fuzzy Scoring

- [ ] T011 Add failing tests for fuzzy path of `SearchEngine.score_candidate()` to `tests/service/test_service_search.py`: typo match `"piazola"` against `"piazzolla"` returns score > 0; `fuzzy=False` with no boost → returns `None`; unrelated string scores below threshold → returns `None`; confirm tests are RED
- [ ] T012 Implement the RapidFuzz path in `SearchEngine.score_candidate()` in `taxomesh/application/search.py`: compute `fuzz.ratio`, `fuzz.partial_ratio`, `fuzz.token_set_ratio` against normalized name and slug; include candidate if any score ≥ `FUZZY_THRESHOLD`; score = boost + additive fuzzy component
- [ ] T013 Gate: run `pytest tests/service/test_service_search.py -k score_candidate` — all scoring tests (non-fuzzy + fuzzy) must pass

**Checkpoint — Foundational complete**: `SearchEngine.normalize()` and `SearchEngine.score_candidate()` are implemented and tested. User story implementation can now begin.

---

## Phase 3: User Story 1 — Typo-Tolerant Item Search (Priority: P1) 🎯 MVP

**Goal**: `TaxomeshService.search_items(query)` returns items ranked by match quality, with
typo tolerance, accent-insensitivity, and punctuation-insensitivity.

**Independent Test**: `pytest tests/service/test_service_search.py -k "search_items and not (category_id or recursive or limit or empty)"` — all basic item-search tests pass.

- [ ] T014 [US1] Add 10 failing item-search test functions to `tests/service/test_service_search.py`: (1) exact name match, (2) exact slug match, (3) prefix name match, (4) prefix slug match, (5) substring match, (6) typo-tolerant (`"piazola"` finds "Piazzolla"), (7) accent-insensitive (`"agustin"` finds "Agustín"), (8) punctuation-insensitive (`"d arienzo"` finds "D'Arienzo"), (9) `enabled_only=True` excludes a disabled item that would otherwise match, (10) `fuzzy=False` with a typo query (`"piazola"`) returns no match; confirm all 10 tests are RED
- [ ] T015 [US1] Implement `TaxomeshService.search_items(self, query: str, *, limit: int = 20, category_id: UUID | None = None, enabled_only: bool = True, fuzzy: bool = True, recursive: bool = False) -> list[Item]` in `taxomesh/application/service.py` — initial version: normalize query, load all items via `self._repo.list_items()`, filter by `enabled_only`, score each item via `SearchEngine.score_candidate()`, sort by `(-score, norm_name)`, return `[:limit]`; no `category_id` or `recursive` handling yet
- [ ] T016 [US1] Gate: run `pytest tests/service/test_service_search.py -k search_items` — all 10 item-search tests from T014 must pass

**Checkpoint — US1 complete**: `search_items()` exists and returns typo-tolerant ranked results for any query.

---

## Phase 4: User Story 2 — Ranked Results (Priority: P2)

**Goal**: Verify that exact matches outrank fuzzy matches, prefix outranks substring, and
a likely intended typo outranks weaker false positives.

**Independent Test**: `pytest tests/service/test_service_search.py -k ranking` — all ranking tests pass.

- [ ] T017 [US2] Add 3 failing ranking-behavior tests to `tests/service/test_service_search.py`: (1) exact `"gallo ciego"` ranks above `"gallo"` when both exist; (2) prefix match ranks above substring-only match; (3) `"piazola"` result ranks before a weaker unrelated partial match; confirm tests are RED
- [ ] T018 [US2] Run `pytest tests/service/test_service_search.py -k ranking` — if any fail, adjust scoring constant values in `taxomesh/application/search.py` (do not change logic, only tune constant values) until all 3 ranking tests pass
- [ ] T019 [US2] Gate: `pytest tests/service/test_service_search.py` — all tests from Phase 2 and 3 must still pass (no regressions)

**Checkpoint — US2 complete**: Result ordering guarantees are verified by tests.

---

## Phase 5: User Story 3 — Typo-Tolerant Category Search (Priority: P2)

**Goal**: `TaxomeshService.search_categories(query)` returns categories with the same
typo tolerance and ranking as item search.

**Independent Test**: `pytest tests/service/test_service_search.py -k "search_categories and not (parent_id or limit or empty)"` — all basic category-search tests pass.

- [ ] T020 [US3] Add 4 failing category-search test functions to `tests/service/test_service_search.py`: (1) exact name match, (2) exact slug match, (3) typo-tolerant (`"orkesta tipika"` finds "Orquesta Típica"), (4) accent-insensitive (`"tango romantico"` finds "Tango Romántico"); confirm tests are RED
- [ ] T021 [US3] Implement `TaxomeshService.search_categories(self, query: str, *, limit: int = 20, parent_id: UUID | None = None, enabled_only: bool = True, fuzzy: bool = True) -> list[Category]` in `taxomesh/application/service.py` — initial version: normalize query, load all categories via `self._repo.list_categories()` filtered to exclude root (`category.category_id != self._root_id`), apply `enabled_only`, score each via `SearchEngine.score_candidate()`, sort and return; no `parent_id` handling yet
- [ ] T022 [US3] Gate: `pytest tests/service/test_service_search.py -k search_categories` — 4 category-search tests must pass

**Checkpoint — US3 complete**: `search_categories()` exists and returns typo-tolerant ranked results.

---

## Phase 6: User Story 4 — Scoped Search With Filters (Priority: P3)

**Goal**: `category_id` filter on `search_items()` and `parent_id` filter on
`search_categories()` restrict candidates; `recursive=True` includes descendants;
non-existent IDs raise `TaxomeshCategoryNotFoundError`.

**Independent Test**: `pytest tests/service/test_service_search.py -k "category_id or parent_id or recursive"` — all filter tests pass.

### Item `category_id` filter

- [ ] T023 [US4] Add 5 failing filter tests for `search_items` to `tests/service/test_service_search.py`: (1) `category_id=A` returns only items directly in A (not items in B); (2) invalid `category_id` raises `TaxomeshCategoryNotFoundError`; (3) `category_id=X, recursive=True` returns items from X AND from child category C; (4) `recursive=True` without `category_id` returns all items (same as no filter — `recursive` is silently ignored); (5) an item that belongs to both category X and child C appears only once when `recursive=True` (deduplication by `item_id`); confirm all 5 tests are RED
- [ ] T024 [US4] Add `category_id` (non-recursive) path to `TaxomeshService.search_items()` in `taxomesh/application/service.py`: when `category_id` is set and `recursive=False`, load candidates via `self.list_items(category_id=category_id)` (which already validates existence and raises `TaxomeshCategoryNotFoundError`)
- [ ] T025 [US4] Implement `TaxomeshService._collect_descendant_ids(self, category_id: UUID) -> set[UUID]` in `taxomesh/application/service.py`: BFS over `self._repo.list_category_parent_links()` returning all descendant category UUIDs (not including the starting `category_id`)
- [ ] T026 [US4] Add `recursive=True` path to `TaxomeshService.search_items()` in `taxomesh/application/service.py`: collect descendant IDs via `_collect_descendant_ids`, load items from all categories (`[category_id] + descendants`), deduplicate by `item_id` before scoring
- [ ] T027 [US4] Gate: `pytest tests/service/test_service_search.py -k category_id` — all 5 item filter tests from T023 must pass

### Category `parent_id` filter

- [ ] T028 [US4] Add 2 failing filter tests for `search_categories` to `tests/service/test_service_search.py`: (1) `parent_id=X` returns only direct children of X; (2) invalid `parent_id` raises `TaxomeshCategoryNotFoundError`; confirm tests are RED
- [ ] T029 [US4] Add `parent_id` path to `TaxomeshService.search_categories()` in `taxomesh/application/service.py`: when `parent_id` is set, load candidates via `self.list_categories(parent_id=parent_id)` (which already validates existence)
- [ ] T030 [US4] Gate: `pytest tests/service/test_service_search.py -k parent_id` — both parent filter tests must pass

**Checkpoint — US4 complete**: Both search methods support scoped filtering and raise on invalid IDs.

---

## Phase 7: User Story 5 — Empty Query and Limit Behavior (Priority: P3)

**Goal**: Empty/whitespace queries return `[]`; `limit <= 0` raises `ValueError`; `limit` is
respected when results exceed it.

**Independent Test**: `pytest tests/service/test_service_search.py -k "empty or limit"` — all edge-case tests pass.

- [ ] T031 [US5] Add 6 failing edge-case tests to `tests/service/test_service_search.py`: (1) `search_items("")` → `[]`; (2) `search_items("   ")` → `[]`; (3) `search_items("tango", limit=0)` → `ValueError`; (4) `search_items("tango", limit=-1)` → `ValueError`; (5) when 30 matching items exist, `search_items("tango", limit=10)` returns exactly 10; (6) when only 3 items match, `search_items("tango", limit=100)` returns exactly 3 (limit does not pad results); plus matching cases for `search_categories`; confirm all tests are RED
- [ ] T032 [US5] Add guard clauses to `TaxomeshService.search_items()` in `taxomesh/application/service.py`: `if limit <= 0: raise ValueError(...)` before any loading; `if not query.strip(): return []` before normalization
- [ ] T033 [US5] Add the same guard clauses to `TaxomeshService.search_categories()` in `taxomesh/application/service.py`
- [ ] T034 [US5] Gate: `pytest tests/service/test_service_search.py -k "empty or limit"` — all edge-case tests must pass

**Checkpoint — US5 complete**: All boundary conditions are handled.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Docstrings, disabled-item tests, `fuzzy=False` test, and full quality gates.

- [ ] T035 [P] Add `enabled_only=False` test case to `tests/service/test_service_search.py`: disabled items ARE included when `enabled_only=False`; gate: test passes (the `enabled_only=True` exclusion case was written as part of T014)
- [ ] T036 [P] Gate: run `pytest tests/service/test_service_search.py -k "fuzzy_false or fuzzy=False"` — confirm the `fuzzy=False` test written in T014 still passes after all phases are complete
- [ ] T037 [P] Add Google-style docstring to `taxomesh/application/search.py` module, `SearchEngine` class, `SearchEngine.normalize`, and `SearchEngine.score_candidate` in `taxomesh/application/search.py`
- [ ] T038 [P] Add Google-style docstring to `TaxomeshService.search_items`, `TaxomeshService.search_categories`, and `TaxomeshService._collect_descendant_ids` in `taxomesh/application/service.py`
- [ ] T039 Run `ruff check .` and fix any violations in `taxomesh/application/search.py` and `taxomesh/application/service.py`
- [ ] T040 Run `ruff format --check .` and fix any formatting violations
- [ ] T041 Run `mypy --strict .` (excluding Django paths per `pyproject.toml`) and fix any type errors in `taxomesh/application/search.py` and `taxomesh/application/service.py`
- [ ] T042 Run `pytest --cov=taxomesh --cov-fail-under=80` — all tests must pass; coverage must stay ≥ 80%

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Phase 2
- **US2 (Phase 4)**: Depends on Phase 3 (ranking tests verify search_items behavior)
- **US3 (Phase 5)**: Depends on Phase 2 — **can run in parallel with US1/US2**
- **US4 (Phase 6)**: Depends on US1 (search_items) AND US3 (search_categories) being complete
- **US5 (Phase 7)**: Depends on US1 (search_items) AND US3 (search_categories) being complete
- **Polish (Phase 8)**: Depends on all user stories complete

### User Story Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational: SearchEngine)
    ├──→ Phase 3 (US1: search_items basic)
    │        ↓
    │    Phase 4 (US2: ranking quality)
    │        ↓
    │    Phase 6 (US4: filters) ←──────────┐
    ↓                                       │
Phase 5 (US3: search_categories) ──────────┘
    ↓
Phase 7 (US5: edge cases)
    ↓
Phase 8 (Polish)
```

### Within Each Phase

- Test tasks are written FIRST and must FAIL (red) before implementation begins
- Gate tasks confirm tests pass (green) after implementation
- Always run the full test suite at each gate to prevent regressions

### Parallel Opportunities

- Phase 3 (US1) and Phase 5 (US3) can be worked in parallel once Phase 2 is done
- T037 and T038 (docstrings) are independent and can run in parallel
- T039–T041 (quality gates) can be investigated in parallel

---

## Parallel Example: Phase 2 Foundational

```bash
# These can proceed in parallel once T004 (skeleton) is done:
# Worker A: T005–T006 (normalize implementation + gate)
# Worker B: T007 (define scoring constants) — no dependency on T005
# Sequential: T008–T010 (failing tests then boost logic) must follow T007
# Sequential: T011–T013 (fuzzy logic) must follow T010
```

## Parallel Example: Phase 3 + Phase 5

```bash
# Once Phase 2 is complete, two workers can proceed in parallel:
# Worker A: T014–T016 (US1 item search)
# Worker B: T020–T022 (US3 category search)
```

---

## Implementation Strategy

### MVP First (User Stories 1–3 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: US1 — basic item search
4. Complete Phase 4: US2 — ranking verification
5. Complete Phase 5: US3 — basic category search
6. **STOP and VALIDATE**: `pytest tests/service/test_service_search.py` — all tests green
7. Demo: both search methods work with typo tolerance and ranking

### Full Delivery

8. Complete Phase 6: US4 — filters and recursive
9. Complete Phase 7: US5 — edge cases and guard clauses
10. Complete Phase 8: Polish — docstrings, quality gates

### Incremental Delivery

- After Phase 3: `search_items()` is useful for basic text search
- After Phase 5: `search_categories()` added; both methods at parity
- After Phase 6: Scoped search available for catalog apps
- After Phase 7: Production-ready error handling
- After Phase 8: All quality gates green; ready for PR

---

## Notes

- `[P]` tasks = different files, no blocking dependencies on sibling tasks
- `[Story]` label maps each task to its user story for traceability
- Scoring constants (`BOOST_*`, `FUZZY_THRESHOLD`) are tunable in `taxomesh/application/search.py`
- The `InMemoryRepository` fixture in `tests/service/conftest.py` is used for all search tests
- `external_id=""` sentinel: skip external_id matching when the field equals the empty-string default
- Root category (`__root__`) must always be excluded from `search_categories()` results
- `search_categories(parent_id=None)` loads from `self._repo.list_categories()`, NOT from `self.list_categories()` (which returns roots-only)
