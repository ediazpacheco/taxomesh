# Tasks: Admin & Service Improvements — Category External ID, Debug, and UX

**Input**: Design documents from `/specs/026-admin-service-debug/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: TDD is mandatory per project constitution. Test tasks appear **before** their implementation tasks within each phase. Tests must be written and confirmed failing before implementation begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on sibling tasks)
- **[Story]**: Which user story this task belongs to (US1–US7)
- Exact file paths are included in every task description

---

## Phase 1: Setup

**Purpose**: Confirm branch and quality baseline before any changes.

- [x] T001 Verify branch is `026-admin-service-debug` and `pytest --cov=taxomesh --cov-fail-under=80` passes on HEAD in all test files

---

## Phase 2: Foundational — Repository Protocol + Adapters (`get_debug_info`)

**Purpose**: `get_debug_info()` must be added to the Protocol and all adapters before `TaxomeshService.get_debug()` (US6) or the admin debug page (US7) can be implemented. All user story phases depend on T001 completing; US6 and US7 additionally depend on this phase.

**⚠️ CRITICAL**: US6 and US7 cannot begin until this phase is complete.

- [x] T002 Write failing tests for `get_debug_info()` on `JsonRepository`, `YamlRepository`, and `DjangoRepository` — assert each returns a dict with the correct keys (`path` or `database_alias`) — in `tests/service/test_service_config.py` and `tests/contrib/django/test_django_repository.py`
- [x] T003 Add `get_debug_info(self) -> dict[str, Any]` abstract method to `TaxomeshRepositoryBase` Protocol in `taxomesh/ports/repository.py`
- [x] T004 [P] Implement `JsonRepository.get_debug_info()` returning `{"path": str(self._path)}` in `taxomesh/adapters/repositories/json_repository.py`
- [x] T005 [P] Implement `YamlRepository.get_debug_info()` returning `{"path": str(self._path)}` in `taxomesh/adapters/repositories/yaml_repository.py`
- [x] T006 [P] Implement `DjangoRepository.get_debug_info()` returning `{"database_alias": self._using}` in `taxomesh/adapters/repositories/django_repository.py`

**Checkpoint**: `pytest tests/service/test_service_config.py tests/contrib/django/test_django_repository.py` passes. `mypy --strict taxomesh/ports/repository.py taxomesh/adapters/repositories/` passes.

---

## Phase 3: User Story 1 — Category Linked-Object Resolution in Admin (Priority: P1) 🎯 MVP

**Goal**: `CategoryModelAdmin.linked_object_url` resolves the linked external object using a new `TAXOMESH_CATEGORY_LINKED_MODEL` Django setting, independent of `TAXOMESH_LINKED_MODEL` used for Item.

**Independent Test**: Set `TAXOMESH_CATEGORY_LINKED_MODEL = "myapp.Genre"`, create a category with `external_id` matching a `Genre` PK, open the Category admin list — the `↗` icon is present and navigates correctly.

### Tests for US1

- [x] T007 [US1] Write failing test: with `TAXOMESH_CATEGORY_LINKED_MODEL` set and a category with non-empty `external_id`, the Category changelist response contains a `↗` link — in `tests/contrib/django/test_admin.py`
- [x] T008 [US1] Write failing test: without `TAXOMESH_CATEGORY_LINKED_MODEL`, Category changelist renders `external_id` as plain text with no broken icon and no 500 error — in `tests/contrib/django/test_admin.py`

### Implementation for US1

- [x] T009 [US1] Add `TAXOMESH_CATEGORY_LINKED_MODEL_SETTING: Final[str] = "TAXOMESH_CATEGORY_LINKED_MODEL"` constant near `TAXOMESH_LINKED_MODEL_SETTING` in `taxomesh/contrib/django/admin.py`
- [x] T010 [US1] Add `_resolve_category_linked_url(external_id: str) -> str | None` function that reads `settings.TAXOMESH_CATEGORY_LINKED_MODEL` (same resolution logic as `_resolve_linked_url`) in `taxomesh/contrib/django/admin.py`
- [x] T011 [US1] Update `CategoryModelAdmin.linked_object_url` to call `_resolve_category_linked_url` instead of the item-linked helper in `taxomesh/contrib/django/admin.py`

**Checkpoint**: `pytest tests/contrib/django/test_admin.py -k "linked"` passes. Category `↗` icon works for category-linked models; Item `↗` icon continues to work unchanged.

---

## Phase 4: User Story 5 — TaxomeshService Category Methods Support external_id (Priority: P2)

**Goal**: `create_category`, `update_category`, and `list_categories` all accept `external_id` as a parameter, enabling full programmatic CRUD on `Category.external_id` via the service facade.

**Independent Test**: `service.create_category(name="X", external_id="abc")` returns a category with `external_id == "abc"`; `service.update_category(id, external_id="xyz")` updates it; `service.list_categories(external_id="xyz")` returns only matching categories.

### Tests for US5

- [x] T012 [US5] Write failing tests for `create_category(external_id=...)` — cover non-empty value, empty-string default, and omitted param — in `tests/service/test_service_categories.py`
- [x] T013 [US5] Write failing tests for `update_category(external_id=...)` — cover `None` (no-op), `""` (clear), and non-empty value — in `tests/service/test_service_categories.py`
- [x] T014 [US5] Write failing tests for `list_categories(external_id=...)` — cover exact match, `external_id=""`, and `external_id=None` (all results) — in `tests/service/test_service_categories.py`

### Implementation for US5

- [x] T015 [US5] Add `external_id: str = ""` parameter to `TaxomeshService.create_category()` and pass it to `Category(external_id=external_id)` in `taxomesh/application/service.py`
- [x] T016 [US5] Add `external_id: str | None = None` parameter to `TaxomeshService.update_category()` and apply `if external_id is not None: category.external_id = external_id` in the update block in `taxomesh/application/service.py`
- [x] T017 [US5] Add `external_id: str | None = None` keyword parameter to `TaxomeshService.list_categories()`; when non-None, delegate to `self._repo.list_categories_by_external_id(external_id)`, filter out root, and intersect with `parent_id` filter if also provided in `taxomesh/application/service.py`

**Checkpoint**: `pytest tests/service/test_service_categories.py` passes. `mypy --strict taxomesh/application/service.py` passes.

---

## Phase 5: User Story 2 — Partial UUID Search in Admin List Views (Priority: P2)

**Goal**: UUID fields (`category_id`, `item_id`) are included in `search_fields` so that pasting any UUID substring into the admin search box returns matching records.

**Independent Test**: Search `2b0bf7ef6646` in the Category admin list — the category whose UUID contains that substring appears in results with no error.

### Tests for US2

- [x] T018 [US2] Write failing test: admin Category changelist search for a known UUID substring returns the matching category — in `tests/contrib/django/test_admin.py`
- [x] T019 [US2] Write failing test: admin Item changelist search for a known UUID substring returns the matching item — in `tests/contrib/django/test_admin.py`

### Implementation for US2

- [x] T020 [US2] Add `"category_id"` to `CategoryModelAdmin.search_fields` tuple in `taxomesh/contrib/django/admin.py`
- [x] T021 [US2] Add `"item_id"` to `ItemModelAdmin.search_fields` tuple in `taxomesh/contrib/django/admin.py`

**Checkpoint**: `pytest tests/contrib/django/test_admin.py -k "uuid or search"` passes.

---

## Phase 6: User Story 3 — Better Item/Category–Content Integration Filters (Priority: P2)

**Goal**: `HasLinkedObjectListFilter` on Category admin lets staff filter by whether `external_id` is set. `TaxomeshCategoryListFilter` is auto-included in `ItemCategoryAssignmentMixin` so external model admins get a category sidebar filter with no extra configuration.

**Independent Test**: Category admin list shows "has linked object" / "no linked object" filter choices. A `Content` admin using the mixin shows a taxomesh-category filter automatically.

### Tests for US3

- [x] T022 [US3] Write failing tests for `HasLinkedObjectListFilter`: "yes" returns only categories with non-empty `external_id`; "no" returns only categories with empty `external_id`; unfiltered returns all — in `tests/contrib/django/test_admin.py`
- [x] T023 [US3] Write failing test: an admin class using `ItemCategoryAssignmentMixin` has `TaxomeshCategoryListFilter` in its effective `list_filter` without explicit declaration — in `tests/contrib/django/test_admin.py`

### Implementation for US3

- [x] T024 [US3] Implement `HasLinkedObjectListFilter(SimpleListFilter)` with `title="linked object"`, `parameter_name="has_linked_object"`, choices "yes"/"no", queryset filtering on `external_id != ""`/`external_id == ""` in `taxomesh/contrib/django/admin.py`
- [x] T025 [US3] Add `HasLinkedObjectListFilter` to `CategoryModelAdmin.list_filter` in `taxomesh/contrib/django/admin.py`
- [x] T026 [US3] Implement `TaxomeshCategoryListFilter(SimpleListFilter)` with `title="taxomesh category"`, `parameter_name="taxomesh_category"`, lookups from `DjangoRepository().assignable_categories_qs()`, queryset filtering items whose external_id matches a taxomesh item in the selected category in `taxomesh/contrib/django/admin.py`
- [x] T027 [US3] Add `TaxomeshCategoryListFilter` to `ItemCategoryAssignmentMixin.list_filter` class attribute (or append it in `get_list_filter` override) in `taxomesh/contrib/django/admin.py`

**Checkpoint**: `pytest tests/contrib/django/test_admin.py -k "filter"` passes.

---

## Phase 7: User Story 4 — show-relations Defaults to True (Priority: P3)

**Goal**: CLI `graph` command and admin graph both display item relations by default, with an opt-out flag available.

**Independent Test**: `taxomesh graph` with no flags shows relations. Admin graph page with no query params shows relations.

### Tests for US4

- [x] T028 [US4] Write failing test: invoke CLI `graph` command with no arguments on a taxonomy that has relations — assert relations appear in output — in `tests/adapters/cli/test_graph_output.py`
- [x] T029 [US4] Write failing test: GET the admin graph URL with no `show_relations` param — assert relations are present in the response — in `tests/contrib/django/test_admin_graph.py`

### Implementation for US4

- [x] T030 [US4] Change `show_relations` Typer Option default from `False` to `True` in `graph_cmd` in `taxomesh/adapters/cli/main.py`
- [x] T031 [US4] Locate the admin graph view's `show_relations` default and change it from `False` to `True` in `taxomesh/contrib/django/admin.py`

**Checkpoint**: `pytest tests/adapters/cli/test_graph_output.py tests/contrib/django/test_admin_graph.py` passes.

---

## Phase 8: User Story 6 — TaxomeshService.get_debug() Diagnostic Method (Priority: P3)

**Goal**: `TaxomeshService.get_debug()` returns a dict with `version`, `config_name`, `repository_type`, `working_path`, and `repository_info` — accurate across all three repository backends.

**Independent Test**: `service.get_debug()` returns a dict with all four required keys populated with correct values for the active backend.

### Tests for US6

- [x] T032 [P] [US6] Write failing tests for `get_debug()` return structure: all required keys present, `repository_type` matches adapter class name, `working_path` is a string for file repos and `None` for Django repo — in `tests/service/test_service_config.py`
- [x] T033 [P] [US6] Write failing test: `get_debug()` on a service constructed from `taxomesh.toml` returns `config_name` populated from the TOML `[taxomesh] name` key — in `tests/service/test_service_config.py`

### Implementation for US6

- [x] T034 [US6] Add `self._config_name: str | None = None` to `TaxomeshService.__init__` and populate it from the TOML `[taxomesh]` `name` key when reading `taxomesh.toml` in `taxomesh/application/service.py`
- [x] T035 [US6] Implement `TaxomeshService.get_debug(self) -> dict[str, Any]`: read version via `importlib.metadata.version("taxomesh")`, call `self._repo.get_debug_info()`, extract `working_path` from repo info, return the five-key dict in `taxomesh/application/service.py`

**Checkpoint**: `pytest tests/service/test_service_config.py` passes. `mypy --strict taxomesh/application/service.py` passes.

---

## Phase 9: User Story 7 — Debug Info in TAXOMESH Admin Submenu (Priority: P3)

**Goal**: A read-only "Debug" entry appears under the TAXOMESH section on the Django admin home. Clicking it shows version, config name, repository type, and working path, fetched live via `TaxomeshService().get_debug()`.

**Independent Test**: Staff user GETs the debug admin page — HTTP 200, all four debug field labels are present in the response.

### Tests for US7

- [x] T036 [US7] Write failing tests for `TaxomeshDebugProxyAdmin`: admin home lists "Debug" under TAXOMESH group; GET to `/admin/taxomesh_contrib_django/taxomeshdebugproxy/` returns HTTP 200 for staff user and HTTP 302 for anonymous user; response contains all four debug field labels — in `tests/contrib/django/test_admin_debug.py` (new file)

### Implementation for US7

- [x] T037 [US7] Define `TaxomeshDebugProxy` proxy model (subclass of `CategoryModel`, `proxy=True`, `verbose_name="Debug"`, `app_label=APP_LABEL`, no migration needed) in `taxomesh/contrib/django/admin.py` (or `models.py` if preferred for separation)
- [x] T038 [US7] Implement `TaxomeshDebugProxyAdmin(admin.ModelAdmin)` registered with `@admin.register(TaxomeshDebugProxy)`: deny add/change/delete permissions, allow staff view, override `changelist_view` to call `TaxomeshService().get_debug()` and return a `TemplateResponse` rendering the four debug fields as read-only key/value pairs — in `taxomesh/contrib/django/admin.py`

**Checkpoint**: `pytest tests/contrib/django/test_admin_debug.py` passes. "Debug" entry is visible on the admin home under TAXOMESH, not under Visualization.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates and consistency check across all changes.

- [x] T039 Update `specs/026-admin-service-debug/plan.md` Phase E note to reflect the clarification decision: `TaxomeshCategoryListFilter` is auto-included in the mixin (not opt-in)
- [x] T040 [P] Run `ruff check .` — fix any linting errors introduced by new code
- [x] T041 [P] Run `ruff format --check .` — fix any formatting violations
- [x] T042 Run `mypy --strict .` — fix any type errors across all changed files
- [x] T043 Run `pytest --cov=taxomesh --cov-fail-under=80` — confirm ≥ 80% coverage and all tests pass

**Checkpoint**: All four quality gates pass. PR is ready for `/speckit.analyze`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — blocks US6 (T032–T035) and US7 (T036–T038)
- **Phase 3 (US1)**: Depends on Phase 1 only — independent of all other user stories
- **Phase 4 (US5)**: Depends on Phase 1 only — independent of all other user stories
- **Phase 5 (US2)**: Depends on Phase 1 only — independent of all other user stories
- **Phase 6 (US3)**: Depends on Phase 1 only — independent of all other user stories
- **Phase 7 (US4)**: Depends on Phase 1 only — independent of all other user stories
- **Phase 8 (US6)**: Depends on Phase 2 (needs `get_debug_info()` in adapters)
- **Phase 9 (US7)**: Depends on Phase 2 + Phase 8 (needs `TaxomeshService.get_debug()`)
- **Phase 10 (Polish)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: No story dependencies — start after Phase 1
- **US5 (P2)**: No story dependencies — start after Phase 1; can run in parallel with US1
- **US2 (P2)**: No story dependencies — start after Phase 1; can run in parallel with US1, US5
- **US3 (P2)**: No story dependencies — start after Phase 1; can run in parallel with US1, US2, US5
- **US4 (P3)**: No story dependencies — start after Phase 1; independent
- **US6 (P3)**: Depends on Phase 2 (foundational adapters)
- **US7 (P3)**: Depends on Phase 2 + US6 (`get_debug()` must exist)

### Within Each User Story

- Test tasks MUST be written and confirmed **failing** before implementation begins
- `mypy --strict` on changed files after each implementation task
- Story complete only when all its tasks pass and pytest is green

---

## Parallel Example: US1 + US5 + US2 (all P1/P2, no blockers)

```bash
# After Phase 2 foundational is complete, these stories run in parallel:

# Story US1 — Category linked object
Task T007: Write failing test: linked_object_url with TAXOMESH_CATEGORY_LINKED_MODEL
Task T008: Write failing test: graceful fallback when setting not configured
→ T009: Add TAXOMESH_CATEGORY_LINKED_MODEL_SETTING constant
→ T010: Add _resolve_category_linked_url() function
→ T011: Update CategoryModelAdmin.linked_object_url

# Story US5 — Service external_id (in parallel with US1)
Task T012: Write failing tests for create_category external_id
Task T013: Write failing tests for update_category external_id
Task T014: Write failing tests for list_categories external_id
→ T015: Implement create_category external_id param
→ T016: Implement update_category external_id param
→ T017: Implement list_categories external_id param

# Story US2 — UUID search (in parallel with US1, US5)
Task T018: Write failing test: Category UUID substring search
Task T019: Write failing test: Item UUID substring search
→ T020: Add category_id to CategoryModelAdmin.search_fields
→ T021: Add item_id to ItemModelAdmin.search_fields
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 3: US1 — Category Linked Object (T007–T011)
3. **STOP and VALIDATE**: `pytest tests/contrib/django/test_admin.py -k "linked"` passes
4. Category admin `↗` icon works for external categories

### Incremental Delivery

1. Phase 1 → Phase 2 (Foundational) → Foundation ready
2. Phase 3 (US1) — Category linked object: **MVP**
3. Phase 4 (US5) + Phase 5 (US2) + Phase 6 (US3) in parallel — P2 stories
4. Phase 7 (US4) — show-relations default
5. Phase 8 (US6) + Phase 9 (US7) — diagnostic features
6. Phase 10 — Polish and PR

### Solo Developer Sequence (recommended order)

```
T001 → T002–T006 → T007–T011 → T012–T017 → T018–T021 → T022–T027 → T028–T031 → T032–T035 → T036–T038 → T039–T043
```

---

## Notes

- `[P]` tasks = different files, no intra-phase dependencies — safe to implement in any order within that group
- TDD is mandatory: every implementation task must be preceded by a failing test
- Run `mypy --strict` on changed files after each implementation task, not just at the end
- Commit after each logical group (e.g., after each user story phase)
- `TaxomeshDebugProxy` requires no Django migration (`proxy=True`)
- The plan.md Phase E note about `TaxomeshCategoryListFilter` being opt-in is superseded by the clarification (Q2 → A: auto-included); T039 corrects this in the plan
