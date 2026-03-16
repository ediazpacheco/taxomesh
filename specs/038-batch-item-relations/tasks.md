# Tasks: Batch Item Relation Lookup

**Input**: Design documents from `/specs/038-batch-item-relations/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: TDD is mandatory per project constitution. All implementation tasks have a preceding test task that must fail before implementation begins.

**Organization**: Tasks are grouped by user story to enable independent verification at each phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared state)
- **[Story]**: User story label from spec.md (US1–US4)
- Exact file paths in every description

---

## Phase 1: Foundational — Protocol Declaration

**Purpose**: Declare the new protocol method in `TaxomeshRepositoryBase`. This is the single prerequisite that blocks all adapter and service work.

**⚠️ CRITICAL**: No adapter or service task can begin until this phase is complete.

- [ ] T001 Add `Collection` import from `collections.abc` (if absent) and declare `list_item_relation_links_for_sources` protocol stub with full Google-style docstring in `taxomesh/ports/repository.py` immediately after `list_item_relation_links`

**Checkpoint**: `mypy --strict taxomesh/ports/repository.py` passes. All three adapter files now fail mypy (missing method) — that is expected and correct.

---

## Phase 2: User Story 1 — Core Batch Lookup (Priority: P1) 🎯 MVP

**Goal**: All three adapters and the service implement the full batch method. A consumer can call `service.list_related_items_for_sources(ids)` and receive a grouped `dict[UUID, dict[str, list[Item]]]` in a single storage round-trip.

**Independent Test**: Call `service.list_related_items_for_sources([id1, id2])` with two source items each having outgoing links and verify the returned dict contains both source IDs with correct grouped Item lists.

### Tests for User Story 1 — write first, verify they FAIL before implementing ⚠️

- [ ] T002 [P] [US1] Write failing tests for `JsonRepository.list_item_relation_links_for_sources` covering: multiple sources return all their links, single source, empty `source_item_ids` returns `[]`, unknown source UUID returns `[]` — in `tests/service/test_json_repository_relations.py`
- [ ] T003 [P] [US1] Write failing tests for `YAMLRepository.list_item_relation_links_for_sources` covering the same scenarios as T002 — in `tests/service/test_yaml_repository_relations.py`
- [ ] T004 [P] [US1] Write failing tests for `DjangoRepository.list_item_relation_links_for_sources` covering the same scenarios as T002 plus a `CaptureQueriesContext` assertion confirming exactly one DB query is issued — in `tests/contrib/django/test_django_repository_relations.py`
- [ ] T005 [P] [US1] Write failing tests for `TaxomeshService.list_related_items_for_sources` covering: grouped dict output keyed by source UUID then relation type, empty `source_item_ids` returns `{}` without touching the repo, sources with no links absent from result, correct `Item` objects resolved from target UUIDs — in `tests/service/test_service_item_relations.py`

### Implementation for User Story 1

- [ ] T006 [P] [US1] Implement `JsonRepository.list_item_relation_links_for_sources`: in-memory filter `lnk.source_item_id in source_set`, optional `relation_type in type_set`, sort by `(source_item_id, relation_type, sort_index, target_item_id)` — in `taxomesh/adapters/repositories/json_repository.py`
- [ ] T007 [P] [US1] Implement `YAMLRepository.list_item_relation_links_for_sources` using the identical algorithm as T006 — in `taxomesh/adapters/repositories/yaml_repository.py`
- [ ] T008 [P] [US1] Implement `DjangoRepository.list_item_relation_links_for_sources`: single ORM query `source_item_id__in=source_item_ids`, optional `relation_type__in=relation_types`, `order_by("source_item_id", "relation_type", "sort_index", "target_item_id")`, wrap `DatabaseError` as `TaxomeshRepositoryError` — in `taxomesh/adapters/repositories/django_repository.py`
- [ ] T009 [US1] Implement `TaxomeshService.list_related_items_for_sources`: short-circuit on empty input, deduplicate ids via `set()`, normalize `relation_types` (strip+lower), call `self._repo.list_item_relation_links_for_sources(...)`, resolve targets via one `self._repo.list_items()` call building a `dict[UUID, Item]`, raise `TaxomeshItemNotFoundError` for any missing target, group into `dict[UUID, dict[str, list[Item]]]` omitting empty keys — in `taxomesh/application/service.py` (depends on T006, T007, T008 passing)

**Checkpoint**: `pytest tests/service/test_json_repository_relations.py tests/service/test_yaml_repository_relations.py tests/service/test_service_item_relations.py` all pass. The batch consumer pattern works end-to-end with JSON/YAML backends.

---

## Phase 3: User Story 2 — Filtering by Relation Type (Priority: P2)

**Goal**: The `relation_types` parameter correctly filters results across all adapters and the service. Edge cases (`relation_types=[]`, `relation_types=None`, unknown types, case normalization) all behave as specified.

**Independent Test**: Call `list_item_relation_links_for_sources([id], relation_types=["music_by"])` on a source item that has both `music_by` and `interpreted_by` links; verify only `music_by` links appear.

### Tests for User Story 2 ⚠️ (add to existing test files; verify edge cases fail before Phase 3 implementation if not already covered)

- [ ] T010 [P] [US2] Extend `tests/service/test_json_repository_relations.py`: add tests for `relation_types=["x"]` returns only type x, `relation_types=["x","y"]` returns both, `relation_types=[]` returns all, `relation_types=None` returns all, unknown type returns `[]`
- [ ] T011 [P] [US2] Extend `tests/service/test_yaml_repository_relations.py` with the same filtering edge-case tests as T010
- [ ] T012 [P] [US2] Extend `tests/contrib/django/test_django_repository_relations.py` with the same filtering edge-case tests as T010
- [ ] T013 [P] [US2] Extend `tests/service/test_service_item_relations.py`: add tests for service-level case normalization (`relation_types=["MUSIC_BY"]` matches stored `music_by`), `relation_types=[]` treated as no filter, multiple types in filter return union of results

**Note**: No new implementation tasks — filtering is implemented as part of T006–T009. These tasks add edge-case test coverage and confirm the existing implementation satisfies all filtering contract rules.

**Checkpoint**: `pytest tests/service/test_json_repository_relations.py tests/service/test_yaml_repository_relations.py tests/service/test_service_item_relations.py tests/contrib/django/test_django_repository_relations.py` all pass including new filtering tests.

---

## Phase 4: User Story 3 — Consistent Ordering (Priority: P3)

**Goal**: The ordering contract — `(source_item_id ASC, relation_type ASC, sort_index ASC, target_item_id ASC)` — is verified explicitly for all adapters. Results from JSON, YAML, and Django adapters are identical given the same data.

**Independent Test**: Create links with deliberate sort_index values and ties; assert the returned list matches the expected deterministic order for each adapter independently.

### Tests for User Story 3 ⚠️ (add ordering-specific test cases to existing test files)

- [ ] T014 [P] [US3] Extend `tests/service/test_json_repository_relations.py`: add tests asserting `sort_index ASC` ordering within a `(source, relation_type)` group; tie-breaking by `target_item_id ASC` when `sort_index` is equal; links for two sources come out interleaved by `source_item_id ASC`
- [ ] T015 [P] [US3] Extend `tests/service/test_yaml_repository_relations.py` with the same ordering-specific tests as T014
- [ ] T016 [P] [US3] Extend `tests/contrib/django/test_django_repository_relations.py` with the same ordering-specific tests as T014

**Note**: No new implementation tasks — ordering is implemented as part of T006–T009. These tasks add determinism verification.

**Checkpoint**: All ordering tests pass across all three adapter test files.

---

## Phase 5: User Story 4 — Backward Compatibility Verification (Priority: P1)

**Goal**: Confirm that `list_item_relation_links`, `list_item_relations`, and `list_related_items` are entirely unchanged. All existing tests pass without modification.

**Independent Test**: Run existing relation tests with a filter that excludes the new `for_sources` tests; zero failures.

- [ ] T017 [P] [US4] Run existing per-item relation tests for JSON and YAML repos and confirm zero failures: `pytest tests/service/test_json_repository_relations.py tests/service/test_yaml_repository_relations.py -k "not for_sources"` — fix any regressions found before proceeding
- [ ] T018 [P] [US4] Run existing Django repository relation tests and confirm zero failures: `pytest tests/contrib/django/test_django_repository_relations.py -k "not for_sources"` — fix any regressions found
- [ ] T019 [P] [US4] Run existing service item relation tests and confirm zero failures: `pytest tests/service/test_service_item_relations.py -k "not for_sources"` — fix any regressions found

**Checkpoint**: All pre-existing relation tests pass. No public API has changed in signature or behavior.

---

## Phase 6: Polish & Quality Gates

**Purpose**: Final validation across the full codebase.

- [ ] T020 [P] Run full pytest suite with coverage: `pytest --cov=taxomesh --cov-fail-under=80` — fix any failures or coverage drops
- [ ] T021 [P] Run ruff linter and formatter check: `ruff check . && ruff format --check .` — fix any lint or format issues
- [ ] T022 [P] Run mypy strict type check: `mypy --strict .` — fix any type errors (common: missing `Collection` import, incomplete type annotations on new methods)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Foundational)**: No dependencies — start immediately
- **Phase 2 (US1)**: Depends on Phase 1 completion — BLOCKS all later phases
- **Phase 3 (US2)**: Depends on Phase 2 completion
- **Phase 4 (US3)**: Depends on Phase 2 completion — can run in parallel with Phase 3
- **Phase 5 (US4)**: Depends on Phase 3 and 4 completion
- **Phase 6 (Polish)**: Depends on Phase 5 completion

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 1. No dependency on other stories.
- **US2 (P2)**: Depends on US1 implementations (filtering already built in Phase 2; Phase 3 only adds tests).
- **US3 (P3)**: Depends on US1 implementations (ordering already built in Phase 2; Phase 4 only adds tests). Can proceed in parallel with US2.
- **US4 (P1)**: Depends on US2 and US3 completing their test additions.

### Within Phase 2

1. **T002–T005**: Write all tests (parallel) → confirm they FAIL
2. **T006–T008**: Implement adapters (parallel, depend only on T001)
3. **T009**: Implement service (sequential — depends on T006–T008 passing)

### Parallel Opportunities

Phase 2 offers the most parallelism:
- T002, T003, T004, T005 — all write tests in different files, fully parallel
- T006, T007, T008 — all implement different adapter files, fully parallel

Phase 3 and 4 can run in parallel with each other once Phase 2 completes.

---

## Parallel Example: Phase 2 (US1)

```bash
# Step 1 — Write all tests in parallel (all different files):
Task T002: "Write failing tests for JsonRepository in tests/service/test_json_repository_relations.py"
Task T003: "Write failing tests for YAMLRepository in tests/service/test_yaml_repository_relations.py"
Task T004: "Write failing tests for DjangoRepository in tests/contrib/django/test_django_repository_relations.py"
Task T005: "Write failing tests for TaxomeshService in tests/service/test_service_item_relations.py"

# Step 2 — Confirm all fail (expected)

# Step 3 — Implement adapters in parallel (all different files):
Task T006: "Implement JsonRepository.list_item_relation_links_for_sources in json_repository.py"
Task T007: "Implement YAMLRepository.list_item_relation_links_for_sources in yaml_repository.py"
Task T008: "Implement DjangoRepository.list_item_relation_links_for_sources in django_repository.py"

# Step 4 — After T006–T008 pass:
Task T009: "Implement TaxomeshService.list_related_items_for_sources in service.py"
```

---

## Implementation Strategy

### MVP (Phase 1 + Phase 2 only)

1. Complete Phase 1: Protocol declaration
2. Complete Phase 2: Core batch API (all adapters + service)
3. **STOP and VALIDATE**: Full batch call works end-to-end
4. Consumers can already replace their N+1 loops with one `list_related_items_for_sources()` call

### Incremental Delivery

1. Phase 1 + 2 → Core batch works → MVP deployable
2. Phase 3 → Filtering edge cases verified → US2 complete
3. Phase 4 → Ordering edge cases verified → US3 complete
4. Phase 5 → Backward compat confirmed → US4 complete
5. Phase 6 → Quality gates green → PR ready

### Parallel Team Strategy

With two developers after Phase 1:

- Developer A: T002, T003, T005, T006, T007, T009 (JSON + YAML + service)
- Developer B: T004, T008 (Django adapter)

Both merge after Phase 2. Phases 3–4 can then proceed independently.

---

## Task Summary

| Phase | Tasks | Parallelizable | Story |
|-------|-------|---------------|-------|
| 1 — Foundational | T001 | — | — |
| 2 — Core Batch (US1 P1) | T002–T009 | T002–T008 parallel | US1 |
| 3 — Filtering (US2 P2) | T010–T013 | T010–T013 parallel | US2 |
| 4 — Ordering (US3 P3) | T014–T016 | T014–T016 parallel | US3 |
| 5 — Backward Compat (US4 P1) | T017–T019 | T017–T019 parallel | US4 |
| 6 — Polish | T020–T022 | T020–T022 parallel | — |

**Total tasks**: 22
**Test tasks**: T002–T005, T010–T016, T017–T019 (15)
**Implementation tasks**: T001, T006–T009 (5)
**Quality gate tasks**: T020–T022 (3)

---

## Notes

- `[P]` tasks touch different files and have no shared in-progress dependencies
- TDD is mandatory: test tasks (T002–T005) MUST fail before running T006–T009
- Each phase ends with a named checkpoint — stop and validate before proceeding
- The `for_sources` suffix in pytest `-k` filters isolates new tests from existing regression tests
- Phase 2 is the MVP — everything needed to eliminate N+1 queries is delivered here
