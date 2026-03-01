# Tasks: Item & Category Slug Field

**Input**: Design documents from `specs/018-item-category-slug/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/service-api.md ✅

**TDD**: Test tasks are included and MUST be written/verified failing before corresponding implementation tasks.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Exact file paths are included in every task description

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core shared infrastructure that MUST be complete before ANY user story can be implemented. No user story work can begin until this phase is complete.

- [x] T001 Write tests for `TaxomeshDuplicateSlugError` hierarchy in `tests/test_exceptions.py`
- [x] T002 [P] Add `MAX_SLUG_LENGTH: Final[int] = 256` and `DEFAULT_SLUG: Final[str] = ""` constants to `taxomesh/domain/constants.py`
- [x] T003 Add `TaxomeshDuplicateSlugError(TaxomeshValidationError)` to `taxomesh/exceptions.py`
- [x] T004 Add `get_item_by_slug(self, slug: str) -> Item | None` and `get_category_by_slug(self, slug: str) -> Category | None` method stubs to `TaxomeshRepositoryBase` in `taxomesh/ports/repository.py`
- [x] T005 Add `get_item_by_slug` and `get_category_by_slug` linear-scan implementations to `InMemoryRepository` in `tests/service/conftest.py`

**Checkpoint**: Foundation ready — run `pytest tests/test_exceptions.py -v` to confirm T001 passes. User story work can now begin.

---

## Phase 3: User Story 1 — Assign a Slug to a Category (Priority: P1) 🎯 MVP

**Goal**: `Category` domain model gains a `slug` field (max 256 chars, default `""`). Non-empty slug is unique per category namespace. `TaxomeshDuplicateSlugError` raised on conflict. Slug persists across all three storage backends and is retrievable by slug lookup.

**Independent Test**: Create a category with `slug="electronics"`, retrieve it, confirm slug is stored; then attempt a second category with `slug="electronics"` and confirm `TaxomeshDuplicateSlugError` is raised.

### Tests for User Story 1 ⚠️ Write first — ensure they FAIL before implementation

- [x] T006 [US1] Write category slug field and uniqueness tests in `tests/domain/test_slug_field.py` (slug default, max-length accept/reject, `TaxomeshDuplicateSlugError` on duplicate, empty-string non-uniqueness)
- [x] T007 [US1] Write service-layer category slug tests in `tests/service/test_service_slug.py` (create with slug, duplicate raises, two empty slugs succeed, update changes slug, self-assign no-error, clear slug)
- [x] T008 [P] [US1] Add category slug round-trip and `get_category_by_slug` found/not-found tests to `tests/service/test_json_repository.py`
- [x] T009 [P] [US1] Add category slug round-trip and `get_category_by_slug` found/not-found tests to `tests/service/test_yaml_repository.py`
- [x] T010 [P] [US1] Add category slug persist/retrieve and `get_category_by_slug` found/not-found tests to `tests/contrib/django/test_django_repository.py`

### Implementation for User Story 1

- [x] T011 [US1] Add `slug: Annotated[str, Field(max_length=MAX_SLUG_LENGTH)] = ""` field to `Category` in `taxomesh/domain/models/category.py`
- [x] T012 [P] [US1] Add `get_category_by_slug` linear-scan method to `JsonRepository` in `taxomesh/adapters/repositories/json_repository.py`
- [x] T013 [P] [US1] Add `get_category_by_slug` linear-scan method to `YAMLRepository` in `taxomesh/adapters/repositories/yaml_repository.py`
- [x] T014 [US1] Update `_row_to_category` and `save_category` in `DjangoRepository` to carry `slug`; add `get_category_by_slug` DB-filter method in `taxomesh/adapters/repositories/django_repository.py`
- [x] T015 [US1] Add `slug = models.CharField(max_length=256, blank=True, default="", db_index=True)` and `UniqueConstraint(fields=["slug"], condition=~Q(slug=""), name="taxomesh_category_slug_unique_nonempty")` to `CategoryModel` in `taxomesh/contrib/django/models.py`
- [x] T016 [US1] Edit `0001_initial.py` in-place to add `slug` field and `constraints` option to the `CategoryModel` `CreateModel` operation in `taxomesh/contrib/django/migrations/0001_initial.py`
- [x] T017 [US1] Add `slug: str = ""` parameter and pre-write uniqueness check to `create_category` and `update_category` in `taxomesh/application/service.py`; import `TaxomeshDuplicateSlugError`

**Checkpoint**: Run `pytest tests/domain/test_slug_field.py tests/service/test_service_slug.py tests/service/test_json_repository.py tests/service/test_yaml_repository.py tests/contrib/django/test_django_repository.py -v -k "category"` — all category slug tests must pass.

---

## Phase 4: User Story 2 — Assign a Slug to an Item (Priority: P1)

**Goal**: `Item` domain model gains a `slug` field (max 256 chars, default `""`). Non-empty slug is unique per item namespace (separate from category namespace). `TaxomeshDuplicateSlugError` raised on conflict. Slug persists across all three storage backends.

**Independent Test**: Create an item with `slug="iphone-15"`, verify it is stored; attempt a second item with the same slug and confirm `TaxomeshDuplicateSlugError`.

### Tests for User Story 2 ⚠️ Write first — ensure they FAIL before implementation

- [x] T018 [US2] Write item slug field and uniqueness tests in `tests/domain/test_slug_field.py` (slug default, max-length, duplicate raises, empty-string non-uniqueness, item+category same slug no conflict)
- [x] T019 [US2] Write service-layer item slug tests in `tests/service/test_service_slug.py` (create with slug, duplicate raises, two empty slugs succeed, update slug, self-assign, taking other's slug raises, clearing slug)
- [x] T020 [P] [US2] Add item slug round-trip and `get_item_by_slug` found/not-found tests to `tests/service/test_json_repository.py`
- [x] T021 [P] [US2] Add item slug round-trip and `get_item_by_slug` found/not-found tests to `tests/service/test_yaml_repository.py`
- [x] T022 [P] [US2] Add item slug persist/retrieve and `get_item_by_slug` found/not-found tests to `tests/contrib/django/test_django_repository.py`

### Implementation for User Story 2

- [x] T023 [US2] Add `slug: Annotated[str, Field(max_length=MAX_SLUG_LENGTH)] = ""` field to `Item` in `taxomesh/domain/models/item.py`
- [x] T024 [P] [US2] Add `get_item_by_slug` linear-scan method to `JsonRepository` in `taxomesh/adapters/repositories/json_repository.py`
- [x] T025 [P] [US2] Add `get_item_by_slug` linear-scan method to `YAMLRepository` in `taxomesh/adapters/repositories/yaml_repository.py`
- [x] T026 [US2] Update `_row_to_item` and `save_item` in `DjangoRepository` to carry `slug`; add `get_item_by_slug` DB-filter method in `taxomesh/adapters/repositories/django_repository.py`
- [x] T027 [US2] Add `slug = models.CharField(max_length=256, blank=True, default="", db_index=True)` and `UniqueConstraint(fields=["slug"], condition=~Q(slug=""), name="taxomesh_item_slug_unique_nonempty")` to `ItemModel` in `taxomesh/contrib/django/models.py`
- [x] T028 [US2] Edit `0001_initial.py` in-place to add `slug` field and `constraints` option to the `ItemModel` `CreateModel` operation in `taxomesh/contrib/django/migrations/0001_initial.py`
- [x] T029 [US2] Add `slug: str = ""` parameter and pre-write uniqueness check to `create_item` and `update_item` in `taxomesh/application/service.py`

**Checkpoint**: Run `pytest tests/domain/test_slug_field.py tests/service/test_service_slug.py tests/service/test_json_repository.py tests/service/test_yaml_repository.py tests/contrib/django/test_django_repository.py -v` — all slug tests (item + category) must pass.

---

## Phase 5: User Story 3 — Human-Readable String Representation (Priority: P2)

**Goal**: `str(Category)` returns `"{name} (s: {slug} - id: {category_id})"` when slug is non-empty; `"{name} (id: {category_id})"` when slug is `""`. Name is always shown; `external_id` is not included (FR-006). `str(Item)` returns `"{slug} ({item_id}) -> {external_id}"` when slug is non-empty; `"({item_id}) -> {external_id}"` when slug is `""` (FR-005). Django ORM model `__str__` matches. Existing tests updated to assert new format.

**Independent Test**: Construct `Category` and `Item` with and without slugs and external IDs; assert all 8 `str()` combinations match the canonical format exactly.

### Tests for User Story 3 ⚠️ Write first — ensure they FAIL before implementation

- [x] T030 [US3] Add `__str__` format tests (all 8 combinations) to `tests/domain/test_slug_field.py`
- [x] T031 [US3] Update `test_category_model_str_*` and `test_item_model_str_*` assertions in `tests/contrib/django/test_admin.py` to match new canonical `__str__` format
- [x] T032 [US3] Update `test_cli.py` assertions that relied on `Category.__str__` including category name; replace with UUID-presence checks in `tests/test_cli.py`

### Implementation for User Story 3

- [x] T033 [US3] Add `__str__` method to `Category` in `taxomesh/domain/models/category.py`: `"{name} (s: {slug} - id: {category_id})"` when slug is non-empty; `"{name} (id: {category_id})"` when slug is `""` — name always shown, external_id never shown (FR-006)
- [x] T034 [US3] Add `__str__` method to `Item` in `taxomesh/domain/models/item.py`: `"{slug} ({item_id}) -> {external_id}"`
- [x] T035 [US3] Update `CategoryModel.__str__` and `ItemModel.__str__` in `taxomesh/contrib/django/models.py` to match canonical format; simplify `ItemParentLinkModel.__str__` to delegate to `Item.__str__`

**Checkpoint**: Run `pytest tests/domain/test_slug_field.py tests/contrib/django/test_admin.py tests/test_cli.py -v` — all string-representation tests must pass.

---

## Phase 6: User Story 4 — CLI Graph Renders Slug with UUID (Priority: P2)

**Goal**: `taxomesh graph` renders the identifier segment of each category and item row as `"slug (uuid)"` when slug is non-empty, and as bare `"uuid"` when slug is `""`. No parentheses around the UUID when no slug is present.

**Independent Test**: Build a graph with a category and item that have slugs, render it via `_add_graph_node`, confirm `"my-cat (uuid)"` appears in output; repeat with empty slug and confirm only bare UUID appears.

### Tests for User Story 4 ⚠️ Write first — ensure they FAIL before implementation

- [x] T036 [US4] Add `TestSlugRendering` class to `tests/adapters/cli/test_graph_output.py` with 4 cases: category with/without slug, item with/without slug

### Implementation for User Story 4

- [x] T037 [US4] Update `_add_graph_node` in `taxomesh/adapters/cli/main.py` to render `f"{entity.slug} ({entity_id})"` when slug is set and bare `str(entity_id)` when slug is `""`

**Checkpoint**: Run `pytest tests/adapters/cli/test_graph_output.py -v` — all graph-output tests including `TestSlugRendering` must pass.

---

## Phase 7: User Story 5 — Django Admin Shows and Persists Slug (Priority: P3)

**Goal**: Django admin category and item list views show a `slug` column. `save_model` routes slug through the service layer (`create_category(slug=...)` / `update_category(slug=...)`). Duplicate slug surfaced as a user-facing validation error.

**Independent Test**: In the Django admin (via test client), create a category with a slug, confirm it appears in the list view; attempt to save a second category with the same slug and confirm a validation error is returned.

### Tests for User Story 5 ⚠️ Write first — ensure they FAIL before implementation

- [x] T038 [US5] Add admin slug column and save_model routing tests to `tests/contrib/django/test_admin_service_routing.py` (slug present in list_display; save_model calls service with slug; duplicate slug surfaces as validation error)

### Implementation for User Story 5

- [x] T039 [US5] Add `"slug"` to `list_display` of `CategoryModelAdmin` and `ItemModelAdmin` in `taxomesh/contrib/django/admin.py`
- [x] T040 [US5] Update `CategoryModelAdmin.save_model` and `ItemModelAdmin.save_model` in `taxomesh/contrib/django/admin.py` to pass `slug=obj.slug` to `svc.create_category`/`svc.update_category` and `svc.create_item`/`svc.update_item`
- [x] T041 [US5] Add `"slug": cat.slug or None` and `"slug": item.slug or None` to the flattened dicts in `_flatten_graph` in `taxomesh/contrib/django/admin.py`

**Checkpoint**: Run `pytest tests/contrib/django/ -v` — all Django tests including admin slug tests must pass.

---

## Phase 7b: FR-016 — CLI CRUD `--slug` Arguments

**Goal**: `category add --slug`, `category update --slug`, `item add --slug`, and `item update --slug` wired through to service layer. Covers FR-016 which was absent from the original task set.

### Tests for FR-016 ⚠️ Write first — ensure they FAIL before implementation

- [x] T047 Add CLI `--slug` argument tests to `tests/test_cli.py`: `category add --slug books` stores slug; `category update --slug` changes slug; `item add --slug` stores slug; `item update --slug` changes slug (invoke via `typer.testing.CliRunner`)

### Implementation for FR-016

- [x] T048 Add `slug: str = typer.Option("", "--slug", ...)` to `category_add` and `item_add` commands in `taxomesh/adapters/cli/main.py`; pass `slug=slug` to `svc.create_category` / `svc.create_item`
- [x] T049 Add `slug: str | None = typer.Option(None, "--slug", ...)` to `category_update` and `item_update` commands in `taxomesh/adapters/cli/main.py`; pass `slug=slug` to `svc.update_category` / `svc.update_item`

**Checkpoint**: Run `pytest tests/test_cli.py -v -k slug` — all CLI slug tests must pass.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates, export surface, and final verification.

- [x] T042 [P] Export `TaxomeshDuplicateSlugError` from `taxomesh/__init__.py` alongside the rest of the exception hierarchy
- [x] T043 [P] Run `ruff check .` and fix any lint violations across all modified files
- [x] T044 [P] Run `ruff format --check .` and fix any formatting violations
- [x] T045 [P] Run `mypy --strict .` and fix any type errors
- [x] T046 Run full test suite: `pytest --cov=taxomesh --cov-fail-under=80` — must reach ≥ 80% coverage with zero failures

**Checkpoint**: All quality gates pass. Feature is complete.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — start immediately. BLOCKS all user story phases.
- **US1 (Phase 3)**: Depends on Phase 2 completion.
- **US2 (Phase 4)**: Depends on Phase 2 completion. Can run in parallel with US1 where files differ.
- **US3 (Phase 5)**: Depends on US1 (category.py) and US2 (item.py) slug fields being in place.
- **US4 (Phase 6)**: Depends on US1 and US2 slug fields (domain models must have `slug`).
- **US5 (Phase 7)**: Depends on US1, US2, US3 (admin `__str__` must be canonical; service methods must accept `slug`).
- **Polish (Phase 8)**: Depends on all user story phases completing.

### User Story Dependencies

```
Phase 2 (Foundational)
   ├── Phase 3 (US1: Category slug) ──┐
   ├── Phase 4 (US2: Item slug)    ───┤
   │                                   ├── Phase 5 (US3: __str__)
   │                                   ├── Phase 6 (US4: CLI graph)
   │                                   └── Phase 7 (US5: Django admin)
   └───────────────────────────────────────── Phase 8 (Polish)
```

### Within Each User Story

1. Test tasks MUST be written and run (expecting failures) before implementation tasks
2. `pytest [relevant test file] -v` after each implementation task to confirm progress
3. Story is complete when all its tests pass

### Parallel Opportunities

**Phase 2**: T002 can run in parallel with everything else (different file from T003–T005).

**Phase 3 vs Phase 4**: Once Phase 2 is done, US1 and US2 can run in parallel:
- T011 (`category.py`) and T023 (`item.py`) — different files ✅
- T012/T013 and T024/T025 — same files (json/yaml repos); do sequentially within each file
- T014 and T026 (DjangoRepository) — same file; do sequentially
- T015 and T028 (migration) — same file; do sequentially
- T017 and T029 (service.py) — same file; do sequentially

**Phase 5 and Phase 6**: Can run in parallel after US1+US2 complete (different files: domain models vs CLI).

---

## Parallel Example: Phase 3 (US1) — category slug

```bash
# Write tests in parallel first:
Task T008: "Add category slug round-trip tests to tests/service/test_json_repository.py"
Task T009: "Add category slug round-trip tests to tests/service/test_yaml_repository.py"
Task T010: "Add category slug tests to tests/contrib/django/test_django_repository.py"

# Then implement repos in parallel:
Task T012: "Add get_category_by_slug to json_repository.py"
Task T013: "Add get_category_by_slug to yaml_repository.py"
```

## Parallel Example: Phase 4 (US2) — item slug

```bash
# Parallel with US1's category work (different domain model file):
Task T023: "Add slug field + __str__ to item.py"   ← parallel with T011
Task T024: "Add get_item_by_slug to json_repository.py"
Task T025: "Add get_item_by_slug to yaml_repository.py"
```

---

## Implementation Strategy

### MVP First (US1 + US2 — slug storage)

1. Complete Phase 2: Foundational
2. Complete Phase 3: US1 (category slug)
3. Complete Phase 4: US2 (item slug)
4. **STOP and VALIDATE**: Run `pytest tests/ -v --cov=taxomesh` — slug storage works end-to-end
5. Continue with Phase 5 (US3: `__str__`), then Phase 6 (US4: CLI), then Phase 7 (US5: admin)

### Incremental Delivery

1. Phase 2 → Foundation ready
2. Phase 3 + Phase 4 → Slug persists and is unique across all backends (MVP)
3. Phase 5 → Human-readable string output
4. Phase 6 → CLI graph shows slugs
5. Phase 7 → Admin integration
6. Phase 8 → All quality gates green → ready for PR

---

## Notes

- [P] tasks = different files, no unresolved dependencies
- TDD is mandatory per project constitution — tests must exist and fail before implementation
- `slug=""` is the "no slug" sentinel; never passed to uniqueness checks
- Slug uniqueness is per entity type — item and category namespaces are independent
- In-place migration edit (`0001_initial.py`) is intentional — project not yet in production
- Commit after each checkpoint or logical group of tasks
- Run `mypy --strict .` incrementally; do not let type errors accumulate across tasks
