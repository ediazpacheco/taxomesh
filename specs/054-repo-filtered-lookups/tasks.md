# Tasks: Repository-Level Filtered Lookups

**Input**: Design documents from `/specs/054-repo-filtered-lookups/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/repository-port.md, quickstart.md

**Tests**: TDD is mandatory in this project (CLAUDE.md / Constitution VIII) — every implementation task has test tasks that run (and fail) first.

**Organization**: Phase 2 (Foundational) delivers the port + all four adapter implementations — every user story depends on it. Phases 3–6 rewire the service call sites per user story; Phase 7 is polish/gates.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 = related-items (P1), US2 = categories-for-item (P1), US3 = items-in-category recursive + non-recursive (P2), US4 = release (P3)

## Path Conventions

Single library project at repo root: `taxomesh/` (source), `tests/` (tests).

---

## Phase 1: Setup

**Purpose**: Confirm a green baseline so any later failure is attributable to this feature.

- [X] T001 Run baseline quality gates and record they pass on branch `054-repo-filtered-lookups`: `ruff check . && ruff format --check . && mypy --strict . && pytest --cov=taxomesh --cov-fail-under=80`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The two port-contract changes and all four adapter implementations. Every user story phase consumes these.

**⚠️ CRITICAL**: No call-site rewiring (Phases 3–6) may begin until this phase is complete and green.

### Tests first (must FAIL before T006–T010)

- [X] T002 Write contract tests for `get_items_by_ids` in `tests/service/test_repo_filtered_lookups.py`, parametrized over all four backends (reuse the backend-parametrization pattern from `tests/service/conftest.py::service`, but yielding the raw repository instead of the service). Cover: found subset returned as `dict[UUID, Item]`; missing IDs silently absent; empty input ⇒ `{}`; `enabled=True` / `False` / `None` tri-state; result values equal `get_item` output. (Mirror the 052 suite `tests/service/test_service_bulk_external_id.py` structure.)
- [X] T003 In the same file `tests/service/test_repo_filtered_lookups.py`, add contract tests for `list_item_parent_links` filters (all four backends): no-args call returns all links byte-identical to before (regression); `item_id=U` returns only U's links; `category_ids=C` returns only members; **empty `category_ids` collection ⇒ `[]` (not unfiltered)**; both filters ⇒ AND; ordering `(category_id ASC, sort_index ASC, item_id ASC)` holds under every combination (assert against a fixture with sort_index ties). Depends on T002 (same file).
- [X] T004 Run `pytest tests/service/test_repo_filtered_lookups.py` and confirm ALL new tests fail with `AttributeError`/`TypeError` (methods/params don't exist yet). Do not proceed if any unexpectedly passes.

### Implementation

- [X] T005 Extend the port in `taxomesh/ports/repository.py`: add `get_items_by_ids(self, item_ids: Collection[UUID], *, enabled: bool | None = None) -> dict[UUID, Item]` beside `get_items_by_external_ids` (052 section), and add keyword-only params `item_id: UUID | None = None, category_ids: Collection[UUID] | None = None` to `list_item_parent_links`. Use the exact signatures + Google-style docstrings from `specs/054-repo-filtered-lookups/contracts/repository-port.md` (document empty-collection ⇒ `[]`, AND semantics, missing-IDs-absent, ordering contract).
- [X] T006 [P] Implement both methods in `taxomesh/adapters/repositories/json_repository.py`: `get_items_by_ids` as a dict-lookup loop over `self._items` (O(len(ids))) with tri-state enabled filter; `list_item_parent_links` filters as comprehensions applied BEFORE the existing `sorted(...)` call (existing sort key unchanged) — per research.md R5.
- [X] T007 [P] Implement both methods in `taxomesh/adapters/repositories/yaml_repository.py` (same shape as T006).
- [X] T008 [P] Implement both methods in `taxomesh/adapters/repositories/django_repository.py` with **DB-side filtering** per research.md R4: `get_items_by_ids` via `filter(item_id__in=ids)` + conditional `.filter(enabled=...)`, rows mapped through the existing row→domain helper, `DatabaseError` → `TaxomeshRepositoryError`; `list_item_parent_links` via conditional `.filter(item_id=...)` / `.filter(category_id__in=list(category_ids))` chained onto the existing `.order_by("category_id", "sort_index", "item_id")`.
- [X] T009 [P] Implement both methods in the `InMemoryRepository` test fixture in `tests/service/conftest.py` (same shape as T006).
- [X] T010 Run `pytest tests/service/test_repo_filtered_lookups.py` → all pass; then `mypy --strict .` → clean (this structurally verifies all four repos still satisfy `TaxomeshRepositoryBase`); then full `pytest tests/service/` → no regressions.

**Checkpoint**: Port + adapters complete and green. Call-site rewiring can begin; Phases 3, 4, 5 are mutually independent after this point.

---

## Phase 3: User Story 1 — Fast related-items resolution (Priority: P1) 🎯 MVP

**Goal**: `list_related_items_for_sources` builds its item map from only the IDs referenced by matched links, via `get_items_by_ids(..., enabled=True)`.

**Independent Test**: Spy-repo test proves `list_items` is never called; existing resilience suite (`tests/service/test_service_list_related_resilience.py`) passes unchanged.

### Tests first (must FAIL before T013)

- [X] T011 [US1] Create `tests/service/test_service_no_full_scan.py` with a `RecordingRepository` proxy (wraps `InMemoryRepository`, records method names + kwargs via `__getattr__` delegation or explicit wrappers). Add test: seed items + relations, call `list_related_items_for_sources([...])`, assert `list_items` was NOT called and `get_items_by_ids` WAS called with `enabled=True` and exactly `{source ids} | {target ids}` of the matched links. Assert returned structure equals the InMemory ground truth.
- [X] T012 [US1] In `tests/service/test_service_no_full_scan.py`, add parity-trap regressions for research.md R1 (site 1): (a) DISABLED relation target ⇒ skipped + WARNING logged when `skip_on_error=True` (use `caplog`, assert source repr appears) and ⇒ `TaxomeshItemNotFoundError` with message `Item {target_id!r} referenced by relation not found` when `skip_on_error=False`; (b) DISABLED *source* item with a dangling target ⇒ WARNING renders `<unknown source item {id}>`. Run the file: T011/T012 spy assertions must FAIL (service still calls `list_items`), behavior assertions must PASS (they pin current behavior).

### Implementation

- [X] T013 [US1] Rewire site 1 in `taxomesh/application/service.py` (`list_related_items_for_sources`, ~line 1199): replace `all_items = self._repo.list_items()` + full `item_map` with `needed_ids = {l.source_item_id for l in links} | {l.target_item_id for l in links}` and `item_map = self._repo.get_items_by_ids(needed_ids, enabled=True)`. Everything else (skip_on_error branch, WARNING construction, exception message, result assembly, docstring's "two repository calls" claim) unchanged — update the docstring phrase to reflect the bulk lookup.
- [X] T014 [US1] Verify: `pytest tests/service/test_service_no_full_scan.py tests/service/test_service_list_related_resilience.py tests/service/test_service_item_relations.py` → all pass across all backends.

**Checkpoint**: Hottest path fixed and independently verified — deployable MVP.

---

## Phase 4: User Story 2 — Fast categories-for-item lookup (Priority: P1)

**Goal**: `list_categories_by_item` fetches only the target item's links via `list_item_parent_links(item_id=...)`.

**Independent Test**: Spy-repo test proves the unfiltered link scan is gone; `tests/service/test_service_list_categories_by_item.py` passes unchanged.

### Tests first (must FAIL before T016)

- [X] T015 [US2] In `tests/service/test_service_no_full_scan.py`, add test: seed several items with placements, call `list_categories_by_item(item_id)`, assert `list_item_parent_links` was called with `item_id=item_id` (not argument-less), result equals ground truth in `sort_index` order, and `TaxomeshItemNotFoundError` still raised for unknown item (validation precedes link query). Note: `TaxomeshService` memoizes this method — use a fresh service per assertion or `clear_all_caches()` to avoid cache hits masking repo calls. Run → spy assertion FAILS.

### Implementation

- [X] T016 [US2] Rewire site 2 in `taxomesh/application/service.py` (`list_categories_by_item`, ~line 549): replace the `[lnk for lnk in self._repo.list_item_parent_links() if lnk.item_id == item_id]` comprehension with `self._repo.list_item_parent_links(item_id=item_id)`. Keep the stable `sorted(..., key=lambda lnk: lnk.sort_index)`, the `self.get_item(item_id)` validation, the per-link `self.get_category`, and the enabled filter exactly as-is.
- [X] T017 [US2] Verify: `pytest tests/service/test_service_no_full_scan.py tests/service/test_service_list_categories_by_item.py` → all pass across all backends.

**Checkpoint**: Both P1 stories complete.

---

## Phase 5: User Story 3 — Fast items-in-category, recursive + non-recursive (Priority: P2)

**Goal**: Recursive candidates path uses `list_item_parent_links(category_ids=...)` + `get_items_by_ids(..., enabled=True)`; non-recursive `list_items(category_id=...)` uses the category filter while keeping per-link `self.get_item` (research.md R2).

**Independent Test**: Spy-repo tests prove neither path issues full scans; existing search/items suites pass unchanged.

### Tests first (must FAIL before T020–T021)

- [X] T018 [US3] In `tests/service/test_service_no_full_scan.py`, add recursive-path test: seed a category tree (parent + descendants) with items, call the recursive path (e.g. `search_items(..., category_id=..., recursive=True)` or `_load_item_candidates` via its public caller per `taxomesh/application/service.py` ~line 1485), assert `list_items` NOT called, `list_item_parent_links` called with `category_ids=` covering `{category} ∪ descendants`, `get_items_by_ids` called with `enabled=True`. Pin parity traps: dedup order (item in two matching categories appears once, first-link-wins), dangling `item_id` in a link silently skipped, DISABLED item silently excluded (R1), `TaxomeshCategoryNotFoundError` for unknown category.
- [X] T019 [US3] In `tests/service/test_service_no_full_scan.py`, add non-recursive test: call `list_items(category_id=...)`, assert `list_item_parent_links` called with `category_ids=[category_id]` (or equivalent single-element collection) and NOT argument-less; results in `sort_index` order; enabled filter respected; **a dangling link still raises `TaxomeshItemNotFoundError`** (per-link `self.get_item` retained — R2); `TaxomeshCategoryNotFoundError` for unknown category. Run → spy assertions FAIL.

### Implementation

- [X] T020 [US3] Rewire site 3 in `taxomesh/application/service.py` (`_load_item_candidates`, ~lines 1761–1770): replace full `item_map` + full link iteration with `links = self._repo.list_item_parent_links(category_ids=all_category_ids)`, then collect matched `item_id`s preserving first-seen order, fetch `item_map = self._repo.get_items_by_ids(seen_ids, enabled=True)`, and build the result list in the same first-link-wins order skipping IDs absent from the map. Validation `self.get_category(category_id)` stays before the queries.
- [X] T021 [US3] Rewire site 4 in `taxomesh/application/service.py` (`list_items`, ~lines 512–515): replace the `if lnk.category_id == category_id` comprehension with `self._repo.list_item_parent_links(category_ids=[category_id])`. Keep `self.get_category(category_id)` validation, the stable `sorted(..., key=lambda lnk: lnk.sort_index)`, the per-link `items = [self.get_item(lnk.item_id) for lnk in links]`, and the enabled filter exactly as-is.
- [X] T022 [US3] Verify: `pytest tests/service/test_service_no_full_scan.py tests/service/test_service_items.py tests/service/test_service_search.py tests/service/test_service_enabled_filter.py tests/service/test_parity_enabled_filter.py` → all pass across all backends.

**Checkpoint**: All four read paths free of full-table scans (SC-001).

---

## Phase 6: User Story 4 — Releasable version (Priority: P3)

**Goal**: Version bump + CHANGELOG so letrastango can move its pin from `0.1.0a40`.

**Independent Test**: `pyproject.toml` version reads `0.1.0a42`; CHANGELOG has a 054 entry.

- [X] T023 [US4] Bump `version = "0.1.0a41"` → `"0.1.0a42"` in `pyproject.toml` (research.md R7).
- [X] T024 [US4] Add a CHANGELOG.md entry for 0.1.0a42 following the file's existing format: Performance — repository-level filtered lookups (`get_items_by_ids`, `list_item_parent_links` filters) eliminate full-table scans in `list_related_items_for_sources`, `list_categories_by_item`, recursive item candidates, and `list_items(category_id=...)`; note for custom-backend authors (two port methods to add/extend); no observable behavior change.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T025 Audit the four rewired sites' docstrings in `taxomesh/application/service.py` for stale claims (e.g. site 1's "two repository calls" phrasing, any "scans all" language) — update only where now inaccurate.
- [X] T026 Run full quality gates: `ruff check . && ruff format --check . && mypy --strict . && pytest --cov=taxomesh --cov-fail-under=80` — all green (Constitution VIII).
- [X] T027 Validate `specs/054-repo-filtered-lookups/quickstart.md` commands verbatim (the three pytest invocations + gates) and confirm SC-001/SC-002 claims hold; fix quickstart if any command drifted.

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (T001)
   └─► Phase 2 (T002→T003→T004→T005→{T006,T007,T008,T009}→T010)   ⛔ blocks all stories
          ├─► Phase 3 / US1 (T011→T012→T013→T014)  ┐
          ├─► Phase 4 / US2 (T015→T016→T017)        ├─ mutually independent*
          ├─► Phase 5 / US3 (T018→T019→T020→T021→T022) ┘
          └─► Phase 6 / US4 (T023, T024) — should land last (version describes the whole change)
                 └─► Phase 7 (T025→T026→T027)
```

\* US1/US2/US3 touch different methods of `taxomesh/application/service.py` and different test functions of `tests/service/test_service_no_full_scan.py` — independent in content, but sequence them (single-developer flow) to avoid same-file merge noise. T011 creates the shared spy-test file; T015/T018/T019 append to it.

### Parallel Opportunities

- **T006, T007, T008, T009** — four adapter implementations, four different files: fully parallel.
- T023 and T024 are [P]-eligible relative to each other but trivial; keep sequential.
- Everything else is intentionally sequential (TDD ordering or same-file edits).

---

## Implementation Strategy

**MVP first**: Phase 1 → Phase 2 → Phase 3 (US1). That alone removes the dominant cost in letrastango's profile and is independently shippable.

**Incremental delivery**: After each story phase, the checkpoint command set proves no behavioral regression across all four backends — each phase is a safe stopping point. US4 (release) only after all code stories land; Phase 7 gates before proposing the PR (then `/speckit.analyze` per workflow).

**Task count**: 27 total — Setup 1, Foundational 9, US1 4, US2 3, US3 5, US4 2, Polish 3.
