---
description: "Task list for 060-batch-placement-reads"
---

# Tasks: Batch resolution for the placement read paths

**Input**: Design documents from `/specs/060-batch-placement-reads/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/repository-port.md, quickstart.md

**Tests**: MANDATORY. Constitution Principle VIII and the project's TDD rule require a failing
test task before every implementation task. This feature's own spec states the gate is the
deliverable and the code change is the easy half — the test tasks are the feature.

**Organization**: Grouped by user story. US1 is a genuine standalone MVP: it needs no port
change, because `get_items_by_ids` already exists in the port and in all four backends.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2, US3, US4 — maps to the user stories in spec.md

## Path Conventions

Single library at repository root: `taxomesh/` for source, `tests/` for tests.

---

## Phase 1: Setup

**Purpose**: Establish a trustworthy baseline before anything changes.

- [X] T001 Build the venv with `uv sync --extra dev --extra django --python 3.12` and confirm a green baseline with `pytest -q` from the repository root
- [X] T002 Measure the current query counts for all three paths with `CaptureQueriesContext` against a throwaway corpus and record them in `docs/backlog/measurements.md` § F1 beside the existing baseline. Derive the expected post-change constants from the same run — one existence check, one link query, one batch resolve — and record those too: the gates in T005, T024 and T030 assert those derived numbers, and the R3 table in `specs/060-batch-placement-reads/research.md` is a prediction to check against, not the source of truth

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared test machinery every story's gate depends on.

**⚠️ CRITICAL**: No story work begins until this phase is complete.

- [X] T003 [P] Extend `RecordingRepository` with `get_item` and `get_category` spies in `tests/service/test_service_no_full_scan.py` (class at :18), following the existing `get_items_by_ids` recorder at :29-36
- [X] T004 [P] Create `tests/contrib/django/test_django_placement_queries.py` with a corpus-builder fixture parametrised over placement/children counts (5 and 200 per FR-019) and a cold-measurement helper that calls `clear_all_caches()` before each `CaptureQueriesContext` block (FR-021), following the pattern in `tests/contrib/django/test_django_bulk_external_id.py`

**Checkpoint**: Spy and query-count harnesses exist; story gates can now be written.

---

## Phase 3: User Story 1 — Listing a category's contents (Priority: P1) 🎯 MVP

**Goal**: `list_items(category_id=…)` costs a constant number of round-trips regardless of placement count.

**Independent Test**: Populate one category with 5 and then 200 placements; assert the query count is identical and equal to the asserted constant. Requires no port change.

### Tests for User Story 1 ⚠️ Write first, confirm they FAIL

- [X] T005 [P] [US1] Query-count gate for `list_items(category_id=…)` over both corpus sizes, asserting the exact constant and that the two counts are identical, in `tests/contrib/django/test_django_placement_queries.py`
- [X] T006 [P] [US1] Spy gate asserting `get_item` is called ZERO times and `get_items_by_ids` exactly once with the complete id set, in `tests/service/test_service_no_full_scan.py`
- [X] T007 [P] [US1] Create `tests/service/test_batch_placement_reads.py` with ordering tests for `list_items`: `sort_index` ties, negative values, duplicate values, and the feature-034 default (FR-015) `tests/service/` is inside `mypy --strict` scope — only `tests/contrib/django/` is excluded in pyproject.toml — so this must be fully typed with no bare `Any`.
- [X] T008 [P] [US1] Empty-result and not-found tests for `list_items` in `tests/service/test_batch_placement_reads.py`: a category with no placements returns `[]` with no batch call (FR-016), and an unknown `category_id` raises `TaxomeshCategoryNotFoundError` before any link read (FR-013)
- [X] T009 [P] [US1] `enabled=True/False/None` parity for `list_items(category_id=…)` across all four backends in `tests/service/test_parity_enabled_filter.py`, including a disabled endpoint being filtered rather than treated as missing (FR-011)
- [X] T010 [P] [US1] Dangling-link test on the JSON and YAML backends in `tests/service/test_batch_placement_reads.py`: delete an item row leaving its placement link, assert `TaxomeshItemNotFoundError` with the message text `Item not found: {id}` (FR-012, R6)
- [X] T011 [P] [US1] Cache tests for `list_items` in `tests/service/test_service_cache.py`: results still cached for the TTL, still invalidated on write (FR-018)

### Implementation for User Story 1

- [X] T012 [US1] Rewrite `list_items` at `taxomesh/application/service.py:503-529` as one link query plus one `get_items_by_ids(set(...), enabled=None)`, iterating the ordered links and looking up in the map, raising on a miss — the shape at `service.py:1155-1167`. Keep the existing `sorted(..., key=lambda lnk: lnk.sort_index)` (R1) and the post-resolution `enabled` filter (R2)
- [X] T013 [US1] Run `pytest tests/service/ tests/contrib/django/ -q` and confirm every US1 test now passes

**Checkpoint**: The headline defect is fixed and fenced. This alone is shippable.

---

## Phase 4: User Story 2 — Navigating the category tree (Priority: P1)

**Goal**: `list_categories(parent_id=…)` costs a constant number of round-trips AND stops reading every category link in the store.

**Independent Test**: Build a parent with 5 then 200 children alongside unrelated categories under other parents; assert identical query counts and that unrelated links are never read.

### Port contract tests ⚠️ Write first, confirm they FAIL

- [X] T014 [P] [US2] Conformance tests for `get_categories_by_ids` in `tests/service/test_batch_placement_reads.py`, run across all four backends: empty input returns `{}` without reaching storage (FR-004), duplicate ids, absent ids silently missing (FR-003), mixed present/absent, `enabled` tri-state (FR-007), and — in `tests/contrib/django/test_django_placement_queries.py`, the only backend that can fail at the storage boundary — storage failure surfacing as `TaxomeshRepositoryError` for both new methods, filtered and unfiltered (FR-005), following `test_django_bulk_external_id.py:77` `tests/service/` is inside `mypy --strict` scope — only `tests/contrib/django/` is excluded in pyproject.toml — so this must be fully typed with no bare `Any`.
- [X] T015 [P] [US2] Oversized-input test in `tests/contrib/django/test_django_placement_queries.py` — the database backend is the only one with a per-query parameter limit, and building the corpus on the file backends is O(n²) in file rewrites. Assert that a collection past the legacy 999-parameter ceiling is sent as exactly ONE unsplit query and returns every row (FR-006, FR-006b). The wrapping of a limit breach as `TaxomeshRepositoryError` (FR-006a) is covered by the DatabaseError tests in T014, which exercise the same `except DatabaseError` path
- [X] T016 [P] [US2] Conformance tests for the `list_category_parent_links` parent filter in `tests/service/test_batch_placement_reads.py`: `None` means no filter, an EMPTY collection returns `[]` rather than everything (FR-010), a non-empty collection filters, and the `(parent_category_id, sort_index, category_id)` ordering holds under every filter combination

### Port and adapter implementation for User Story 2

- [X] T017 [US2] Add `get_categories_by_ids(category_ids, *, enabled=None) -> dict[UUID, Category]` to `TaxomeshRepositoryBase` in `taxomesh/ports/repository.py`, mirroring the `get_items_by_ids` docstring contract at :332-359 clause for clause
- [X] T018 [US2] Widen `list_category_parent_links` in `taxomesh/ports/repository.py:225` to `(*, parent_category_ids: Collection[UUID] | None = None)`, documenting the empty-collection rule exactly as `list_item_parent_links` does at :285-288
- [X] T019 [P] [US2] Implement both port changes in `taxomesh/adapters/repositories/json_repository.py` (batch get in the shape of :624-647; filter applied before the existing `sorted(...)` at :375-385) Include Google-style docstrings on both new methods — ruff selects `E,F,I,UP,B,SIM,PL` and no pydocstyle rules, so the constitution's docstring requirement is not lint-enforced.
- [X] T020 [P] [US2] Implement both port changes in `taxomesh/adapters/repositories/yaml_repository.py` (:648-671 and :399-409) Include Google-style docstrings on both new methods — ruff selects `E,F,I,UP,B,SIM,PL` and no pydocstyle rules, so the constitution's docstring requirement is not lint-enforced.
- [X] T021 [P] [US2] Implement both port changes in `taxomesh/adapters/repositories/django_repository.py`: `category_id__in` queryset in the shape of :807-811, and `parent_category_id__in` applied before the existing `.order_by(...)` at :597-609, both inside the existing `except DatabaseError → TaxomeshRepositoryError` wrapper Include Google-style docstrings on both new methods — ruff selects `E,F,I,UP,B,SIM,PL` and no pydocstyle rules, so the constitution's docstring requirement is not lint-enforced.
- [X] T022 [P] [US2] Implement both port changes in `InMemoryRepository` in `tests/service/conftest.py` (batch get beside :213, filter on the link listing at :139) Include Google-style docstrings on both new methods — ruff selects `E,F,I,UP,B,SIM,PL` and no pydocstyle rules, so the constitution's docstring requirement is not lint-enforced. `tests/service/` is inside `mypy --strict` scope — only `tests/contrib/django/` is excluded in pyproject.toml — so this must be fully typed with no bare `Any`.
- [X] T023 [US2] Extend `RecordingRepository` in `tests/service/test_service_no_full_scan.py` to spy `get_categories_by_ids` and `list_category_parent_links` (depends on T022)

### Story tests for User Story 2 ⚠️ Write before T027/T028, confirm they FAIL

- [X] T024 [P] [US2] Query-count gate for `list_categories(parent_id=…)` over both corpus sizes in `tests/contrib/django/test_django_placement_queries.py`, plus a no-full-scan assertion that adding categories under other parents does not change what is read (SC-003)
- [X] T025 [P] [US2] Spy gate in `tests/service/test_service_no_full_scan.py` asserting `get_category` is called EXACTLY ONCE — the existence check, not one per row — and `get_categories_by_ids` exactly once with the full id set (FR-020, R4). A blanket zero assertion is wrong here and must not be written
- [X] T026 [P] [US2] Behaviour tests for `list_categories` in `tests/service/test_batch_placement_reads.py`: ordering with ties/negative/duplicate `sort_index`, a leaf returning `[]` with no batch call, an unknown `parent_id` raising, the `parent_id=None` root path, and `enabled` tri-state parity added to `tests/service/test_parity_enabled_filter.py` Add TTL and write-invalidation coverage for this method in `tests/service/test_service_cache.py` (FR-018), matching what T011 does for `list_items`.

### Service implementation for User Story 2

- [X] T027 [US2] Rewrite the main branch of `list_categories` at `taxomesh/application/service.py:338-348` to use the filtered link listing plus one `get_categories_by_ids(..., enabled=None)`, keeping the stable `sort_index` re-sort and the post-resolution `enabled` filter
- [X] T028 [US2] Apply the parent filter to the `external_id` branch at `taxomesh/application/service.py:331-336`, which runs its own copy of the unfiltered scan (R7) — the adjacent defect this feature fixes and calls out
- [X] T029 [US2] Run `pytest tests/service/ tests/contrib/django/ -q` and confirm every US1 and US2 test passes

**Checkpoint**: Both P1 stories complete; the tree path no longer scans the whole link table.

---

## Phase 5: User Story 3 — Reading an item's placements (Priority: P2)

**Goal**: `list_categories_by_item(item_id)` costs a constant number of round-trips.

**Independent Test**: Place one item in 5 then 200 categories; assert identical query counts.

**Depends on**: US2 — `get_categories_by_ids` must exist (T017, T019-T022).

### Tests for User Story 3 ⚠️ Write first, confirm they FAIL

- [X] T030 [P] [US3] Query-count gate for `list_categories_by_item` over both corpus sizes in `tests/contrib/django/test_django_placement_queries.py`
- [X] T031 [P] [US3] Spy gate in `tests/service/test_service_no_full_scan.py`: `get_item` called once (the existence check), `get_category` ZERO times, `get_categories_by_ids` exactly once
- [X] T032 [P] [US3] Ordering test in `tests/service/test_batch_placement_reads.py` pinning the composite `(sort_index, category_id)` order that R1 identifies — the link list arrives in category order and the stable re-sort produces the observable result. This test is what fails if someone deletes the re-sort as redundant
- [X] T033 [P] [US3] Empty-result, unknown-`item_id`, `enabled` tri-state and dangling-category-link coverage for `list_categories_by_item` in `tests/service/test_batch_placement_reads.py` and `tests/service/test_parity_enabled_filter.py` Add TTL and write-invalidation coverage for this method in `tests/service/test_service_cache.py` (FR-018), matching what T011 does for `list_items`.

### Implementation for User Story 3

- [X] T034 [US3] Rewrite `list_categories_by_item` at `taxomesh/application/service.py:531-565` to one link query plus one `get_categories_by_ids(..., enabled=None)`, preserving the re-sort and the post-resolution filter
- [X] T035 [US3] Run `pytest tests/service/ tests/contrib/django/ -q` and confirm all three stories pass

**Checkpoint**: All three read paths batched.

---

## Phase 6: User Story 4 — The regression fence actually bites (Priority: P1)

**Goal**: A future regression to per-row resolution fails CI rather than merely running slower.

**Independent Test**: Revert a method; the suite must go red.

- [X] T036 [US4] Verify the fence for each of the three methods in turn: reintroduce per-row resolution in `taxomesh/application/service.py`, confirm the suite fails, restore. Record which test caught each reversion; a reversion caught by nothing means the gate is decorative and must be strengthened
- [X] T037 [US4] Confirm per-backend coverage is delivered by the right instruments: the behaviour and `enabled` parity assertions in `tests/service/` run on all four backends via the parametrised `service` fixture (`tests/service/conftest.py:351`) — run `pytest tests/service/ -q` and check the parametrisation ids — while the round-trip counts in `tests/contrib/django/test_django_placement_queries.py` supply the database-level evidence. The call-shape spy runs on the in-memory backend only, by design (FR-020); do not attempt to parametrise it
- [X] T038 [US4] Confirm every query-count assertion in `tests/contrib/django/test_django_placement_queries.py` is measured cold: temporarily remove the `clear_all_caches()` call, check the counts change, then restore it (FR-021)

**Checkpoint**: The deliverable the backlog actually asked for is verified, not assumed.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T039 [P] Add the CHANGELOG entry in `CHANGELOG.md`, including the Protocol-widening note: adding a method to `TaxomeshRepositoryBase` breaks `mypy --strict` conformance for consumers with their own repository implementations, which is a minor-version concern
- [X] T040 [P] Record the unbounded-`IN` finding in `docs/backlog/findings.md` § F, covering all four existing operations (`get_items_by_ids` :808, `get_items_by_external_ids` :841, `get_categories_by_external_ids` :877, `list_item_relation_links_for_items` :1001) plus the two this feature adds — deliberately not repaired here
- [X] T041 [P] Update `docs/backlog/findings.md` § F1 to record F1 as resolved, citing the new gates
- [X] T042 Run the full quality gates from the repository root: `ruff check .`, `ruff format --check .`, `mypy --strict .`, `pytest --cov=taxomesh --cov-fail-under=80`. `mypy --strict` is what verifies FR-017 — any change to the three methods' signatures, return types or raised error types fails here
- [X] T043 Run the `specs/060-batch-placement-reads/quickstart.md` validation, including the manual smoke check

**Not a task here**: README updates. The project rule is that README changes are proposed only after `/speckit.analyze` returns zero deviations, never during implement.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)** → no dependencies
- **Foundational (Phase 2)** → depends on Setup; BLOCKS all stories
- **US1 (Phase 3)** → depends only on Foundational. Needs no port change
- **US2 (Phase 4)** → depends on Foundational. Independent of US1
- **US3 (Phase 5)** → depends on US2's port work (T017, T019-T022)
- **US4 (Phase 6)** → depends on whichever stories are complete; strongest after all three
- **Polish (Phase 7)** → depends on all desired stories

### The one cross-story dependency

US3 cannot start before US2 delivers `get_categories_by_ids`. US1 and US2 are
genuinely parallel. If only one story ships, it should be US1 — it carries the
measured headline (5,220 queries → a constant) and needs nothing from the port.

### Within each story

Test tasks come first and must fail before their implementation task. Port
changes precede adapter implementations; adapters precede the service rewrite
that calls them.

---

## Parallel Opportunities

```bash
# Phase 2 — both harness tasks together
T003  RecordingRepository spies
T004  Django corpus fixture

# US1 — all seven test tasks in parallel (different files or independent classes)
T005 T006 T007 T008 T009 T010 T011

# US2 — the four adapter implementations, once T017 and T018 define the port
T019  json_repository.py
T020  yaml_repository.py
T021  django_repository.py
T022  conftest.py InMemoryRepository

# Phase 7 — the three documentation tasks
T039 T040 T041
```

The four adapter tasks in US2 are the widest parallel opportunity: four
separate files implementing the same two methods against one contract.

---

## Implementation Strategy

### MVP: User Story 1 only

1. Phase 1 Setup
2. Phase 2 Foundational
3. Phase 3 US1 — rewrite `list_items`, gates green
4. **STOP and validate**: the 705 ms / 5,220-query call is now a constant

US1 is a true MVP here in a way it often is not: `get_items_by_ids` already
exists in the port and in all four backends, so US1 touches one method in one
file plus its tests. It delivers the measured headline on its own.

### Incremental delivery

US1 → US2 (port work lands here) → US3 (cheap once US2 is in) → US4 (verify
the fence) → Polish. Each story leaves the suite green.

### Total

43 tasks: 2 setup, 2 foundational, 9 US1, 16 US2, 6 US3, 3 US4, 5 polish.
