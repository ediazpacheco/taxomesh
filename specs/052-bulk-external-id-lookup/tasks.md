# Tasks: Bulk Lookup by External ID (Items & Categories)

**Input**: Design documents from `/specs/052-bulk-external-id-lookup/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: TDD is mandatory (project constitution). All test tasks MUST be written and
confirmed FAILING before the corresponding implementation tasks begin.

**Organization**: Organized by user story — each phase is independently testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: Maps to user stories US1/US2/US3 from spec.md
- All paths relative to repository root

---

## Phase 1: Setup

**Purpose**: Baseline verification — no new files, packages, or dependencies required.

- [X] T001 Run `pytest tests/ -x -q` to confirm a clean baseline before any changes

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Declare both new abstract methods on `TaxomeshRepositoryBase` (the Protocol).
No adapter may implement before the port contract is defined.

**⚠️ CRITICAL**: No user story work can begin until T002 and T003 are complete.

- [X] T002 Add abstract method `get_items_by_external_ids(self, external_ids: Collection[str], *, enabled: bool | None = None) -> dict[str, Item]` to `TaxomeshRepositoryBase` in `taxomesh/ports/repository.py` — include full Google-style docstring noting pre-normalised input contract and that missing IDs are absent from result (not an error)
- [X] T003 Add abstract method `get_categories_by_external_ids(self, external_ids: Collection[str], *, enabled: bool | None = None) -> dict[str, Category]` to `TaxomeshRepositoryBase` in `taxomesh/ports/repository.py` — include full Google-style docstring; note root category exclusion is the service's responsibility, not the adapter's

**Checkpoint**: `mypy --strict taxomesh/ports/repository.py` — must pass before continuing.

---

## Phase 3: User Story 1 — Item Bulk Lookup (Priority: P1) 🎯 MVP

**Goal**: `get_items_by_external_ids` resolves items in a single bulk operation across JSON
and YAML backends. Missing, blank, and duplicate IDs are handled silently.

**Independent Test**:
```bash
pytest tests/adapters/repositories/test_json_repository_bulk_external_id.py \
       tests/adapters/repositories/test_yaml_repository_bulk_external_id.py \
       tests/service/test_service_bulk_external_id.py -k "not enabled" -v
```
All tests pass. `mypy --strict taxomesh/` passes.

### Tests for User Story 1 ⚠️ Write first — confirm FAIL before T007/T008/T009

- [X] T004 [P] [US1] Write failing tests for `JsonRepository.get_items_by_external_ids` — basic scenarios: all IDs found, some missing, all missing, duplicate IDs deduplicated, blank/whitespace IDs ignored, empty input returns `{}` — in `tests/adapters/repositories/test_json_repository_bulk_external_id.py`
- [X] T005 [P] [US1] Write failing tests for `YAMLRepository.get_items_by_external_ids` — same basic scenarios as T004 — in `tests/adapters/repositories/test_yaml_repository_bulk_external_id.py`
- [X] T006 [US1] Write failing service tests for `TaxomeshService.get_items_by_external_ids` — normalisation strips whitespace, blank values skipped, duplicates deduplicated, generator input supported, missing IDs return `{}` (no exception), result values are `Item` instances — in `tests/service/test_service_bulk_external_id.py`

### Implementation for User Story 1

- [X] T007 [P] [US1] Implement `get_items_by_external_ids` in `taxomesh/adapters/repositories/json_repository.py` — single O(n) scan over `self._items.values()`: build `target = set(external_ids)`, check `item.external_id in target`, apply `if enabled is None or item.enabled == enabled`, use `assert item.external_id is not None` before key assignment, return `dict[str, Item]`
- [X] T008 [P] [US1] Implement `get_items_by_external_ids` in `taxomesh/adapters/repositories/yaml_repository.py` — identical logic to T007 (same `self._items` pattern)
- [X] T009 [US1] Add two methods to `taxomesh/application/service.py` in the `# External-ID lookup` section: (1) public `get_items_by_external_ids(self, external_ids: Iterable[str], *, enabled: bool | None = None) -> dict[str, Item]` that builds `normalised = frozenset(str(v).strip() for v in external_ids if str(v).strip())`, returns `{}` if empty, then delegates; (2) private `@memoize(DEFAULT_CACHE_TTL)` `_fetch_items_by_external_ids(self, external_ids: frozenset[str], *, enabled: bool | None = None) -> dict[str, Item]` that calls `self._repo.get_items_by_external_ids(external_ids, enabled=enabled)`

**Checkpoint**:
```bash
pytest tests/adapters/repositories/test_json_repository_bulk_external_id.py \
       tests/adapters/repositories/test_yaml_repository_bulk_external_id.py \
       tests/service/test_service_bulk_external_id.py -k "not enabled" -v
mypy --strict taxomesh/
```
Both must pass before moving to Phase 4.

---

## Phase 4: User Story 2 — Item Enabled Filter (Priority: P2)

**Goal**: `enabled=True/False/None` correctly filters item results across all adapters.
Disabled items silently omitted on `enabled=True`; included on `enabled=None` (default).
Django adapter is implemented in this phase.

**Independent Test**:
```bash
pytest tests/adapters/repositories/test_json_repository_bulk_external_id.py \
       tests/adapters/repositories/test_yaml_repository_bulk_external_id.py \
       tests/contrib/django/test_django_bulk_external_id.py \
       tests/service/test_service_bulk_external_id.py -k "item" -v
```

### Tests for User Story 2 ⚠️ Write first — confirm FAIL before T014

- [X] T010 [P] [US2] Add enabled-filter tests to `tests/adapters/repositories/test_json_repository_bulk_external_id.py`: `test_items_enabled_true` (disabled item absent), `test_items_enabled_false` (only disabled item returned), `test_items_enabled_none` (both included)
- [X] T011 [P] [US2] Add enabled-filter tests to `tests/adapters/repositories/test_yaml_repository_bulk_external_id.py` — same three cases as T010
- [X] T012 [US2] Add service enabled-filter tests to `tests/service/test_service_bulk_external_id.py`: `test_items_enabled_filter_true`, `test_items_enabled_filter_false`, `test_items_enabled_filter_none`
- [X] T013 [US2] Write failing Django item tests in `tests/contrib/django/test_django_bulk_external_id.py` with `@pytest.mark.django_db`: `test_items_bulk_lookup_found`, `test_items_bulk_lookup_missing`, `test_items_bulk_lookup_empty_input`, `test_items_enabled_true`, `test_items_enabled_false`, `test_items_enabled_none`, `test_items_database_error_raises_repository_error`

### Implementation for User Story 2

- [X] T014 [US2] Implement `get_items_by_external_ids` in `taxomesh/adapters/repositories/django_repository.py` in the `# External-ID lookup` section: single ORM query `self._ItemModel.objects.using(self._using).filter(external_id__in=external_ids)`, apply `.filter(enabled=enabled)` when `enabled is not None`, wrap in `try/except DatabaseError as exc: raise TaxomeshRepositoryError(str(exc)) from exc`, return `{row.external_id: self._row_to_item(row) for row in qs if row.external_id}` — use lazy imports (`from django.db import DatabaseError  # noqa: PLC0415`)

**Checkpoint**:
```bash
pytest tests/adapters/repositories/test_json_repository_bulk_external_id.py \
       tests/adapters/repositories/test_yaml_repository_bulk_external_id.py \
       tests/contrib/django/test_django_bulk_external_id.py \
       tests/service/test_service_bulk_external_id.py -k "item" -v
```
All item tests pass.

---

## Phase 5: User Story 3 — Category Bulk Lookup (Priority: P3)

**Goal**: `get_categories_by_external_ids` works across all backends. Root category always
excluded. Enabled filtering and silent-omission behaviour identical to item variant.

**Independent Test**:
```bash
pytest tests/adapters/repositories/test_json_repository_bulk_external_id.py \
       tests/adapters/repositories/test_yaml_repository_bulk_external_id.py \
       tests/contrib/django/test_django_bulk_external_id.py \
       tests/service/test_service_bulk_external_id.py -v
```
Full test suite (items + categories) passes.

### Tests for User Story 3 ⚠️ Write first — confirm FAIL before T019/T020/T021/T022

- [X] T015 [P] [US3] Add failing category tests to `tests/adapters/repositories/test_json_repository_bulk_external_id.py`: found/missing/duplicate/blank/empty/`enabled=True`/`enabled=False`/`enabled=None` — covering `get_categories_by_external_ids` on `JsonRepository` directly (root exclusion NOT tested here — that is a service concern)
- [X] T016 [P] [US3] Add failing category tests to `tests/adapters/repositories/test_yaml_repository_bulk_external_id.py` — same coverage as T015
- [X] T017 [US3] Add failing service category tests to `tests/service/test_service_bulk_external_id.py`: `test_categories_root_excluded` (root category external_id in input → absent from result), `test_categories_root_excluded_when_only_id` (only root ID supplied → returns `{}`), `test_categories_enabled_filter_true/false/none`, `test_categories_missing_ids_no_exception`, `test_categories_generator_input`
- [X] T018 [US3] Add failing Django category tests to `tests/contrib/django/test_django_bulk_external_id.py`: `test_categories_bulk_lookup_found`, `test_categories_bulk_lookup_missing`, `test_categories_enabled_true/false/none`, `test_categories_database_error_raises_repository_error`

### Implementation for User Story 3

- [X] T019 [P] [US3] Implement `get_categories_by_external_ids` in `taxomesh/adapters/repositories/json_repository.py` — single O(n) scan over `self._categories.values()`: `target = set(external_ids)`, check `cat.external_id in target`, apply enabled filter, `assert cat.external_id is not None`, return `dict[str, Category]`
- [X] T020 [P] [US3] Implement `get_categories_by_external_ids` in `taxomesh/adapters/repositories/yaml_repository.py` — identical logic to T019 (same `self._categories` pattern)
- [X] T021 [US3] Implement `get_categories_by_external_ids` in `taxomesh/adapters/repositories/django_repository.py` — single ORM query `self._CategoryModel.objects.using(self._using).filter(external_id__in=external_ids)`, apply enabled filter, wrap `DatabaseError → TaxomeshRepositoryError`, return `{row.external_id: self._row_to_category(row) for row in qs if row.external_id}` — use same lazy-import pattern as T014
- [X] T022 [US3] Add two methods to `taxomesh/application/service.py` in the `# External-ID lookup` section: (1) public `get_categories_by_external_ids(self, external_ids: Iterable[str], *, enabled: bool | None = None) -> dict[str, Category]` that normalises to `frozenset`, returns `{}` if empty, delegates to private method, then post-filters with `{k: v for k, v in result.items() if v.category_id != self._root_id}`; (2) private `@memoize(DEFAULT_CACHE_TTL)` `_fetch_categories_by_external_ids(self, external_ids: frozenset[str], *, enabled: bool | None = None) -> dict[str, Category]` that calls `self._repo.get_categories_by_external_ids(external_ids, enabled=enabled)`

**Checkpoint**:
```bash
pytest tests/adapters/repositories/test_json_repository_bulk_external_id.py \
       tests/adapters/repositories/test_yaml_repository_bulk_external_id.py \
       tests/contrib/django/test_django_bulk_external_id.py \
       tests/service/test_service_bulk_external_id.py -v
mypy --strict taxomesh/
```
Both must pass.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T023 Run `ruff check taxomesh/ tests/` and fix any linting issues in modified files (`ports/repository.py`, `json_repository.py`, `yaml_repository.py`, `django_repository.py`, `service.py`, all four test files)
- [X] T024 Run `ruff format --check taxomesh/ tests/` and fix any formatting issues in the same files
- [X] T025 Run `mypy --strict taxomesh/` — confirm all type annotations are correct; pay attention to `Collection[str]` import (`from collections.abc import Collection`), `frozenset[str]` annotation in service, and return types on all new methods
- [X] T026 Run `pytest --cov=taxomesh --cov-fail-under=80 -v` — full suite with coverage gate; must pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Baseline)**: No dependencies — start immediately
- **Phase 2 (Port)**: Depends on Phase 1 — **BLOCKS all user stories**
- **Phase 3 (US1)**: Depends on Phase 2 — JSON/YAML file adapters + service (no Django)
- **Phase 4 (US2)**: Depends on Phase 3 — adds Django item adapter + enabled-filter tests
- **Phase 5 (US3)**: Depends on Phase 2 only — category methods are fully independent of item methods; can run in **parallel with Phase 3/4** if staffed
- **Phase 6 (Polish)**: Depends on Phase 3, 4, and 5 completion

### User Story Dependencies

- **US1 (P1)**: Can start immediately after Phase 2
- **US2 (P2)**: Depends on US1 (enabled filter tests build on US1 adapter implementations)
- **US3 (P3)**: Depends on Phase 2 only — independent of US1/US2

### Within Each User Story

1. Write tests → run pytest → **confirm FAIL**
2. Implement adapters (JSON+YAML in parallel, then Django sequentially)
3. Implement service methods
4. Run pytest → **confirm PASS**
5. Run mypy → **confirm pass**

### Parallel Opportunities

Within Phase 3:
- **T004 + T005** — JSON and YAML test files are different; run in parallel
- **T007 + T008** — JSON and YAML adapter implementations are different files; run in parallel

Within Phase 4:
- **T010 + T011** — JSON and YAML enabled-filter tests; run in parallel

Within Phase 5:
- **T015 + T016** — JSON and YAML category tests; run in parallel
- **T019 + T020** — JSON and YAML category implementations; run in parallel

Across stories (if two developers):
- **Developer A**: Phase 3 → Phase 4 (item methods)
- **Developer B**: Phase 5 (category methods, starts after Phase 2)

---

## Parallel Example: User Story 1

```bash
# Step 1 — Write failing tests in parallel (T004 + T005):
Task T004: tests/adapters/repositories/test_json_repository_bulk_external_id.py
Task T005: tests/adapters/repositories/test_yaml_repository_bulk_external_id.py

# Verify tests FAIL:
pytest tests/adapters/repositories/test_json_repository_bulk_external_id.py \
       tests/adapters/repositories/test_yaml_repository_bulk_external_id.py -v
# Expected: FAILED (method does not exist yet)

# Step 2 — Implement adapters in parallel (T007 + T008):
Task T007: taxomesh/adapters/repositories/json_repository.py
Task T008: taxomesh/adapters/repositories/yaml_repository.py

# Step 3 — Implement service (T009, depends on T007+T008 passing):
Task T009: taxomesh/application/service.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Baseline
2. Complete Phase 2: Port abstract methods (CRITICAL — blocks everything)
3. Complete Phase 3: US1 — item bulk lookup (JSON + YAML + service)
4. **STOP and VALIDATE** — downstream consumers can use `get_items_by_external_ids` immediately against JSON/YAML backends
5. Continue to Phase 4 (Django + enabled) and Phase 5 (categories) as priorities allow

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready (5 min)
2. Phase 3 → MVP: item bulk lookup for JSON/YAML/service (**LetrasTango fix unlocked**)
3. Phase 4 → Full item support: Django adapter + enabled filter
4. Phase 5 → Full feature: category bulk lookup across all backends
5. Phase 6 → Polish: quality gates pass, PR ready

---

## Notes

- `Collection[str]` import: `from collections.abc import Collection` — verify it is present in `ports/repository.py` (it likely isn't yet; add it)
- `frozenset[str]` in service: no import needed in Python 3.11+
- The `@memoize(DEFAULT_CACHE_TTL)` decorator automatically registers the cache in `_cache_registry` — `clear_all_caches()` will invalidate both new private methods without any additional wiring
- Adapter `assert item.external_id is not None` before dict key assignment satisfies mypy strict (since `external_id: str | None` on the model, but we just confirmed it's in the target set which contains only `str`)
- Django lazy imports: follow existing pattern `from django.db import DatabaseError  # noqa: PLC0415` inside the method body
- Root category exclusion happens in the **service** (`get_categories_by_external_ids`), not in adapters — adapters return the raw result including root if its external_id matches
