# Tasks: Django Repository

**Input**: Design documents from `/specs/012-django-repository/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**TDD**: Test tasks are REQUIRED by project constitution (CLAUDE.md §Testing Rules).
Every test task MUST run and fail before its paired implementation task.

**Format**: `[ID] [P?] [Story?] Description`
- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to

---

## Phase 1: Setup

**Purpose**: Add optional dependency, dev deps, pytest settings, mypy exclude, and package markers.

- [X] T001 Update `pyproject.toml`:
  - Add `django = ["django>=4.2"]` to `[project.optional-dependencies]`
  - Add `pytest-django>=4.8` to dev dependencies (no `django-stubs` — excluded by design; see research.md R-008)
  - Add `DJANGO_SETTINGS_MODULE = "tests.django_settings"` under `[tool.pytest.ini_options]`
  - Add `exclude = ["taxomesh/contrib/django/"]` under `[tool.mypy]` (R-008)

- [X] T002 [P] Create package markers and test directory structure:
  - `taxomesh/contrib/__init__.py` (empty package marker)
  - `taxomesh/contrib/django/__init__.py` (placeholder — factory function added in T013)
  - `taxomesh/contrib/django/migrations/__init__.py` (empty)
  - `tests/contrib/__init__.py` (empty)
  - `tests/contrib/django/__init__.py` (empty)

- [X] T003 [P] Create `tests/django_settings.py`:
  ```python
  """Minimal Django settings for the taxomesh test suite."""
  DATABASES = {
      "default": {
          "ENGINE": "django.db.backends.sqlite3",
          "NAME": ":memory:",
      }
  }
  INSTALLED_APPS = ["taxomesh.contrib.django"]
  DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
  ```

- [X] T004 Add optional and dev dependencies to `pyproject.toml`:
  - `django>=4.2` under `[project.optional-dependencies] django`
  - `pytest-django>=4.8` under dev dependencies
  - Note: `uv.lock` updated as a result; `python -c "import django"` confirms installation

**Checkpoint**: `python -c "import django"` succeeds; `uv run pytest --collect-only` picks up
`tests/contrib/django/` without import errors.

---

## Phase 2a: Domain Constants (Foundational — blocks ORM models)

**Purpose**: Extract `max_length` literals from domain models into `taxomesh/domain/constants.py`
so the Django ORM models can import the same values. In scope for spec 012 (FR-023).

**⚠️ CRITICAL**: `taxomesh/contrib/django/models.py` imports from `domain/constants.py` —
this phase must complete before Phase 2b begins.

- [X] T005 Write failing tests for domain constants in `tests/domain/test_constants.py`:
  - `test_max_category_name_length_is_256` — import constant, assert value
  - `test_max_tag_name_length_is_25` — critical: tag uses 25, not 256
  - `test_max_description_length_is_100_000`
  - `test_max_external_id_str_length_is_256`
  - `test_max_external_id_db_length_is_512`
  - `test_max_external_id_type_length_is_8`
  - `test_category_name_field_uses_constant` — introspect `Category.model_fields["name"]`
    max_length matches `MAX_CATEGORY_NAME_LENGTH`
  - `test_tag_name_field_uses_constant` — same for `Tag.model_fields["name"]`

- [X] T006 Create `taxomesh/domain/constants.py` and update consumers:
  - Create `taxomesh/domain/constants.py` with 6 `Final[int]` constants:
    `MAX_CATEGORY_NAME_LENGTH = 256`, `MAX_TAG_NAME_LENGTH = 25`,
    `MAX_DESCRIPTION_LENGTH = 100_000`, `MAX_EXTERNAL_ID_STR_LENGTH = 256`,
    `MAX_EXTERNAL_ID_DB_LENGTH = 512`, `MAX_EXTERNAL_ID_TYPE_LENGTH = 8`
  - Update `taxomesh/domain/models/category.py` — replace inline `max_length=256` /
    `max_length=100_000` literals with `MAX_CATEGORY_NAME_LENGTH` / `MAX_DESCRIPTION_LENGTH`
  - Update `taxomesh/domain/models/tag.py` — replace `max_length=25` with `MAX_TAG_NAME_LENGTH`
  - Update `taxomesh/domain/types.py` — replace inline `max_length=256` in `ExternalId`
    annotation with `MAX_EXTERNAL_ID_STR_LENGTH`

**Checkpoint**: `pytest tests/domain/test_constants.py -v` → all pass;
`mypy --strict taxomesh/domain/` → clean.

---

## Phase 2b: ORM Models, AppConfig, Admin (Foundational — blocks all user stories)

**Purpose**: Define the 6 ORM models, AppConfig, admin registrations, and generate the
initial migration. No DjangoRepository code yet.

**⚠️ CRITICAL**: No user story work can begin until this phase and Phase 2a are complete.

- [X] T007 Create `taxomesh/contrib/django/apps.py`:
  ```python
  from django.apps import AppConfig

  class TaxomeshContribDjangoConfig(AppConfig):
      name = "taxomesh.contrib.django"
      label = "taxomesh_contrib_django"
      verbose_name = "Taxomesh"
  ```

- [X] T008 Create `taxomesh/contrib/django/models.py` with:
  - Imports: `from taxomesh.domain.constants import MAX_CATEGORY_NAME_LENGTH, MAX_TAG_NAME_LENGTH,
    MAX_DESCRIPTION_LENGTH, MAX_EXTERNAL_ID_DB_LENGTH, MAX_EXTERNAL_ID_TYPE_LENGTH`
  - ORM-specific `Final` constants: `APP_LABEL`, `CATEGORY_TABLE`, `ITEM_TABLE`, `TAG_TABLE`,
    `CATEGORY_PARENT_LINK_TABLE`, `ITEM_PARENT_LINK_TABLE`, `ITEM_TAG_LINK_TABLE`,
    `EXTERNAL_ID_TYPE_UUID = "uuid"`, `EXTERNAL_ID_TYPE_INT = "int"`,
    `EXTERNAL_ID_TYPE_STR = "str"`, `EXTERNAL_ID_TYPE_CHOICES`, `DJANGO_REPO_USING_DEFAULT = "default"`
  - `CategoryModel` — 7 fields: `category_id UUIDField(primary_key=True)`, `name CharField(max_length=MAX_CATEGORY_NAME_LENGTH)`,
    `description CharField(max_length=MAX_DESCRIPTION_LENGTH, default="")`, `enabled BooleanField(default=True)`,
    `external_id CharField(max_length=MAX_EXTERNAL_ID_DB_LENGTH, default="")`,
    `external_id_type CharField(max_length=MAX_EXTERNAL_ID_TYPE_LENGTH, choices=EXTERNAL_ID_TYPE_CHOICES, default=EXTERNAL_ID_TYPE_STR)`,
    `metadata JSONField(default=dict)`; `Meta.app_label = APP_LABEL`, `Meta.db_table = CATEGORY_TABLE`
  - `ItemModel` — 5 fields: `item_id`, `external_id`, `external_id_type`, `enabled`, `metadata`;
    `Meta.app_label`, `Meta.db_table`
  - `TagModel` — 3 fields: `tag_id`, `name CharField(max_length=MAX_TAG_NAME_LENGTH)`, `metadata`;
    `Meta.app_label`, `Meta.db_table`
  - `CategoryParentLinkModel` — `category FK(CategoryModel, CASCADE)`, `parent_category FK(CategoryModel, CASCADE)`,
    `sort_index IntegerField(default=0)`; `unique_together=[("category","parent_category")]`
  - `ItemParentLinkModel` — `item FK(ItemModel, CASCADE)`, `category FK(CategoryModel, CASCADE)`,
    `sort_index`; `unique_together=[("item","category")]`
  - `ItemTagLinkModel` — `tag FK(TagModel, CASCADE)`, `item FK(ItemModel, CASCADE)`;
    `unique_together=[("tag","item")]`

- [X] T009 [P] Create `taxomesh/contrib/django/admin.py` with 6 `ModelAdmin` subclasses
  registered via `admin.site.register(Model, ModelAdmin)`. Each class has `list_display`
  including at minimum the primary key field and `__str__`.

- [X] T010 Generate the initial migration (NOT hand-authored — FR-018):
  ```bash
  DJANGO_SETTINGS_MODULE=tests.django_settings python -m django makemigrations taxomesh_contrib_django
  ```
  Commit the generated `taxomesh/contrib/django/migrations/0001_initial.py`.

**Checkpoint**: `DJANGO_SETTINGS_MODULE=tests.django_settings python -m django migrate --run-syncdb`
exits 0; `python -m django makemigrations --check taxomesh_contrib_django` exits 0.

---

## Phase 3: User Story 1 — Install & Migrate (Priority: P1) 🎯 MVP Start

**Goal**: `migrate` creates 6 tables; `DjangoRepository.__init__` raises `TaxomeshRepositoryError`
when Django is absent; `get_taxomesh_service_with_django()` import succeeds without Django.

**Independent Test**: `pytest tests/contrib/django/test_django_repository.py -k "us1 or migrate or guard" -v`

### Tests for User Story 1

> **Write these tests FIRST. All MUST fail before T012 is started.**

- [X] T011 [US1] Write failing tests in `tests/contrib/django/test_django_repository.py`:
  - `test_migrate_creates_six_tables` — use `django.db.connection.introspection.table_names()`;
    assert all 6 `taxomesh_*` table names present
  - `test_no_pending_migrations` — `call_command("migrate", "--check")` exits without error
  - `test_init_raises_repository_error_when_django_missing` — mock import to raise `ImportError`
    for `django`; assert `TaxomeshRepositoryError` raised with `"pip install taxomesh[django]"`
    in message
  - `test_get_config_summary_format` — assert result matches `r"^django:\w+/\w+$"` and does not
    contain `"PASSWORD"`, `"HOST"`, or `"PORT"` (case-insensitive)
  - `test_import_taxomesh_without_django_succeeds` — verify SC-003: `import taxomesh` in a
    subprocess with Django removed from sys.modules must not raise
  - `test_import_factory_without_django_succeeds` — verify SC-003: importing
    `get_taxomesh_service_with_django` in subprocess without Django installed must not raise

### Implementation for User Story 1

- [X] T012 [US1] Create `taxomesh/adapters/repositories/django_repository.py`:
  - Module-level helpers (no Django imports):
    - `_serialize_external_id(value: ExternalId) -> tuple[str, str]`
    - `_deserialize_external_id(serialized: str, type_code: str) -> ExternalId`
  - `DjangoRepository` class:
    - `__init__(self, using: str = DJANGO_REPO_USING_DEFAULT) -> None` — deferred Django import
      block with `# noqa: PLC0415`; catch `ImportError` → raise `TaxomeshRepositoryError`
      with `"pip install taxomesh[django]"` hint
    - `get_config_summary(self) -> str` — deferred `from django.conf import settings`; return
      `f"django:{engine}/{self._using}"`
    - All remaining 16 protocol method stubs raising `NotImplementedError` (filled in later tasks)

- [X] T013 [US1] Implement `get_taxomesh_service_with_django()` in `taxomesh/contrib/django/__init__.py`:
  ```python
  from taxomesh.contrib.django.models import DJANGO_REPO_USING_DEFAULT  # safe — no Django dep

  def get_taxomesh_service_with_django(
      using: str = DJANGO_REPO_USING_DEFAULT,
  ) -> "TaxomeshService":
      from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415
      from taxomesh import TaxomeshService  # noqa: PLC0415
      return TaxomeshService(repository=DjangoRepository(using=using))
  ```
  Note: both imports are deferred inside the function body — `from taxomesh.contrib.django import
  get_taxomesh_service_with_django` must succeed without Django installed (SC-003).

**Checkpoint**: `pytest tests/contrib/django/test_django_repository.py -k "migrate or guard or config_summary or factory" -v`
→ all pass.

---

## Phase 4: User Story 2 — Category CRUD (Priority: P1)

**Goal**: `save_category`, `get_category`, `list_categories`, `delete_category` round-trip
correctly, including `ExternalId` type preservation for all three variants (UUID, int, str).

**Independent Test**: `pytest tests/contrib/django/test_django_repository.py -k "category" -v`

### Tests for User Story 2

> **Write these tests FIRST. All MUST fail before T015 is started.**

- [X] T014 [US2] Append failing tests to `tests/contrib/django/test_django_repository.py`:
  - `test_save_and_get_category` — save a category, retrieve by `category_id`, assert all fields equal
  - `test_get_category_missing_returns_none` — get non-existent UUID → `None`
  - `test_list_categories_returns_all` — save 2 categories, `list_categories()` returns both
  - `test_list_categories_empty` — fresh repo, `list_categories()` returns `[]`
  - `test_delete_category_returns_true` — delete existing → `True`; row gone from DB
  - `test_delete_category_missing_returns_false` — delete non-existent UUID → `False`
  - `test_save_category_upserts_on_repeat_call` — save same `category_id` twice with different
    name; `list_categories()` returns one entry with updated name
  - `test_external_id_uuid_round_trip` — save with `external_id=UUID(...)`, retrieve, assert
    `isinstance(retrieved.external_id, UUID)` and value equals original
  - `test_external_id_int_round_trip` — save with `external_id=42`, assert retrieved is `int`
  - `test_external_id_str_round_trip` — save with `external_id="slug"`, assert retrieved is `str`

### Implementation for User Story 2

- [X] T015 [US2] Implement Category CRUD methods in `taxomesh/adapters/repositories/django_repository.py`:
  - `save_category(self, category: Category) -> None`
    — `CategoryModel.objects.using(self._using).update_or_create(category_id=..., defaults={...})`
    — wrap in `with transaction.atomic(using=self._using):`
    — `try/except DatabaseError` → re-raise as `TaxomeshRepositoryError`
    — all Django imports deferred inside method body with `# noqa: PLC0415`
  - `get_category(self, category_id: UUID) -> Category | None`
    — `CategoryModel.objects.using(self._using).filter(category_id=...).first()`
    — map ORM row to domain `Category` via private `_row_to_category` helper
  - `list_categories(self) -> list[Category]`
    — `list(CategoryModel.objects.using(self._using).all())`; no ORDER BY (FR-020)
  - `delete_category(self, category_id: UUID) -> bool`
    — `CategoryModel.objects.using(self._using).filter(category_id=...).delete()` → check count > 0

**Checkpoint**: `pytest tests/contrib/django/test_django_repository.py -k "category" -v` → all pass.

---

## Phase 5: User Story 3 — Item & Tag CRUD (Priority: P1)

**Goal**: `save_item`, `get_item`, `list_items`, `delete_item`, `save_tag`, `get_tag`,
`list_tags`, `delete_tag`, `assign_tag`, `remove_tag` all work; `assign_tag` is idempotent.

**Independent Test**: `pytest tests/contrib/django/test_django_repository.py -k "item or tag" -v`

### Tests for User Story 3

> **Write these tests FIRST. All MUST fail before T017 is started.**

- [X] T016 [US3] Append failing tests to `tests/contrib/django/test_django_repository.py`:
  - `test_save_and_get_item`
  - `test_get_item_missing_returns_none`
  - `test_list_items_returns_all`
  - `test_delete_item_returns_true`
  - `test_delete_item_missing_returns_false`
  - `test_item_external_id_uuid_round_trip`
  - `test_item_external_id_int_round_trip`
  - `test_save_and_get_tag`
  - `test_get_tag_missing_returns_none`
  - `test_list_tags_returns_all`
  - `test_delete_tag_returns_true`
  - `test_delete_tag_missing_returns_false`
  - `test_assign_tag_links_tag_to_item`
  - `test_assign_tag_is_idempotent` — assign same `(tag_id, item_id)` twice; assert exactly one
    row in `taxomesh_item_tag_link` (SC-006)
  - `test_remove_tag_returns_true`
  - `test_remove_tag_missing_returns_false`

### Implementation for User Story 3

- [X] T017 [US3] Implement Item, Tag, and Tag↔Item methods in `django_repository.py`:
  - `save_item`, `get_item`, `list_items`, `delete_item` (same pattern as category)
  - `save_tag`, `get_tag`, `list_tags`, `delete_tag`
  - `assign_tag(self, tag_id: UUID, item_id: UUID) -> None`
    — `ItemTagLinkModel.objects.using(self._using).get_or_create(tag_id=tag_id, item_id=item_id)`
  - `remove_tag(self, tag_id: UUID, item_id: UUID) -> bool`
    — `.filter(...).delete()` → return `deleted_count > 0`

**Checkpoint**: `pytest tests/contrib/django/test_django_repository.py -k "item or tag" -v` → all pass.

---

## Phase 6: User Story 4 — Parent Links (Priority: P1)

**Goal**: `save_category_parent_link`, `list_category_parent_links`, `save_item_parent_link`,
`list_item_parent_links` work with upsert semantics (duplicate `(category, parent)` → single row,
`sort_index` updated).

**Independent Test**: `pytest tests/contrib/django/test_django_repository.py -k "parent_link" -v`

### Tests for User Story 4

> **Write these tests FIRST. All MUST fail before T019 is started.**

- [X] T018 [US4] Append failing tests to `tests/contrib/django/test_django_repository.py`:
  - `test_save_category_parent_link_and_list`
  - `test_save_category_parent_link_upserts_sort_index` — save same `(cat, parent)` pair twice
    with different `sort_index`; `list_category_parent_links()` returns exactly one link with
    updated `sort_index`
  - `test_list_category_parent_links_empty`
  - `test_delete_category_cascades_parent_link` — save category with parent link; delete category;
    assert `list_category_parent_links()` returns `[]` (on_delete=CASCADE FR-019)
  - `test_save_item_parent_link_and_list`
  - `test_save_item_parent_link_upserts_sort_index`
  - `test_list_item_parent_links_empty`

### Implementation for User Story 4

- [X] T019 [US4] Implement parent link methods in `django_repository.py`:
  - `save_category_parent_link(self, link: CategoryParentLink) -> None`
    — `CategoryParentLinkModel.objects.using(self._using).update_or_create(
         category_id=link.category_id, parent_category_id=link.parent_category_id,
         defaults={"sort_index": link.sort_index})`
    — wrap in `transaction.atomic(using=self._using)`
  - `list_category_parent_links(self) -> list[CategoryParentLink]`
    — `CategoryParentLinkModel.objects.using(self._using).all()`; no ORDER BY (FR-020)
  - `save_item_parent_link(self, link: ItemParentLink) -> None`
    — `ItemParentLinkModel.objects.using(self._using).update_or_create(
         item_id=link.item_id, category_id=link.category_id,
         defaults={"sort_index": link.sort_index})`
  - `list_item_parent_links(self) -> list[ItemParentLink]`

**Checkpoint**: `pytest tests/contrib/django/test_django_repository.py -k "parent_link" -v` → all pass.

---

## Phase 7: User Story 5 — Full Graph (Priority: P2)

**Goal**: `TaxomeshService.get_graph()` works end-to-end with `DjangoRepository`; all
P1 stories integrate correctly.

**Independent Test**: `pytest tests/contrib/django/test_django_repository.py -k "graph" -v`

### Tests for User Story 5

> **Write these tests FIRST. All MUST fail before T021 is started.**

- [X] T020 [US5] Append failing tests:
  - `test_get_graph_returns_correct_structure` — build a 3-level hierarchy via `TaxomeshService`
    with `DjangoRepository`; call `service.get_graph()`; assert roots and child categories are
    correct; assert items appear in correct categories; assert sort order is correct (service sorts)
  - `test_get_graph_empty_repository` — `get_graph()` on empty DB returns valid empty structure

### Implementation for User Story 5

- [X] T021 [US5] No new DjangoRepository code needed — verify `get_graph()` uses already-implemented
  CRUD methods. Fix any integration issues discovered during T020 test run (e.g., `using=` kwarg
  propagation, serialization edge cases).

**Checkpoint**: `pytest tests/contrib/django/test_django_repository.py -v` → all tests pass.

---

## Phase 8: User Story 6 — TOML Config `type = "django"` (Priority: P3)

**Goal**: `TaxomeshService._build_repo_from_config()` supports `type = "django"` with optional
`using` key; error message lists `'django'` as supported type.

**Independent Test**: `pytest tests/ -k "django_type or config" -v`

### Tests for User Story 6

> **Write these tests FIRST. All MUST fail before T023 is started.**

- [X] T022 [US6] Add failing tests to `tests/service/test_service_config.py` (or create new file):
  - `test_build_repo_from_config_django_type` — config `{"repository": {"type": "django"}}` →
    returns `DjangoRepository` instance
  - `test_build_repo_from_config_django_type_with_using` — config includes `"using": "default"` →
    `repo._using == "default"`
  - `test_build_repo_from_config_unsupported_type_lists_django_in_error` — unsupported type →
    error message contains `"'django'"` (FR-014)

### Implementation for User Story 6

- [X] T023 [US6] Modify `taxomesh/application/service.py` `_build_repo_from_config()`:
  - Add `"django"` branch after `"json"` branch:
    ```python
    if repo_type == "django":
        from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415
        from taxomesh.contrib.django.models import DJANGO_REPO_USING_DEFAULT  # noqa: PLC0415
        using: str = section.get("using", DJANGO_REPO_USING_DEFAULT)
        return DjangoRepository(using=using)
    ```
  - Update unsupported-type error message to: `"Supported: 'yaml', 'json', 'django'."`

**Checkpoint**: `pytest tests/service/test_service_config.py -v` → new tests pass; existing tests unaffected.

---

## Phase 9: User Story 7 — Django Admin (Priority: P4)

**Goal**: All 6 taxomesh models are visible and registered in Django admin.

**Independent Test**: `pytest tests/contrib/django/test_admin.py -v`

### Tests for User Story 7

- [X] T024 [US7] Create `tests/contrib/django/test_admin.py`:
  - `test_all_six_models_registered_in_admin` — import `django.contrib.admin.site`;
    assert all 6 model classes (`CategoryModel`, `ItemModel`, `TagModel`,
    `CategoryParentLinkModel`, `ItemParentLinkModel`, `ItemTagLinkModel`) are keys in
    `admin.site._registry`

### Implementation for User Story 7

- [X] T025 [US7] Verify `taxomesh/contrib/django/admin.py` is complete (T009 should have covered
  this). Fix any missing model registrations discovered by T024.

**Checkpoint**: `pytest tests/contrib/django/test_admin.py -v` → passes.

---

## Phase 10: User Story 8 — README (Priority: P2)

**Goal**: README documents Django as the first-class storage backend option.

- [X] T026 [US8] Update `README.md`:
  - Removed legacy "YAML backend" section
  - Inserted **"Repositories"** section explaining pluggable `TaxomeshRepositoryBase` interface;
    all user-facing interfaces (CLI, Django admin, Python API) are repository-agnostic
  - **YAML** subsection (first — service default)
  - **Django ORM** subsection:
    - `pip install taxomesh[django]`
    - `INSTALLED_APPS` snippet + `python manage.py migrate`
    - `DjangoRepository()` direct-use code example
    - `get_taxomesh_service_with_django()` factory example
    - `taxomesh.toml` example with `type = "django"`
  - **JSON** subsection: condensed existing content
  - Features checklist updated; architecture diagram updated

---

## Phase 11: Polish & Quality Gates

- [X] T027 [P] Sweep `taxomesh/adapters/repositories/django_repository.py` and
  `taxomesh/contrib/django/models.py` for any `# type: ignore` comments — each must have
  a one-line justification comment on the same or preceding line (FR-017).

- [X] T028 Run full quality gates and confirm all pass:
  ```bash
  ruff check .
  ruff format --check .
  mypy --strict .
  pytest --cov=taxomesh --cov-fail-under=80
  ```
  Also verify:
  - `python -c "import taxomesh"` — succeeds without Django installed (SC-003)
  - `python -c "from taxomesh.contrib.django import get_taxomesh_service_with_django"` —
    succeeds without Django installed (SC-003)
  - `DJANGO_SETTINGS_MODULE=tests.django_settings python -m django makemigrations --check taxomesh_contrib_django`
    exits 0 (SC-002)

**Checkpoint**: All quality gates green → PR is ready.

---

## Dependencies & Execution Order

```
T001 → T002 → T003 → T004                     (Phase 1: Setup)
  └── T005 → T006                              (Phase 2a: domain/constants.py — BLOCKS 2b)
        └── T007 → T008 → T009 → T010         (Phase 2b: ORM models + migration)
              └── T011 → T012 → T013           (US1: init guard + factory)
                    └── T014 → T015            (US2: category CRUD)
                          └── T016 → T017      (US3: item/tag CRUD)
                                └── T018 → T019  (US4: parent links)
                                      └── T020 → T021      (US5: full graph)
                                            ├── T022 → T023  (US6: TOML config)
                                            ├── T024 → T025  (US7: admin)
                                            └── T026          (US8: README)
                                                  └── T027 → T028  (Polish + quality gates)
```

### Parallel Opportunities

- T002 and T003 can run in parallel (different files, no dependencies).
- T009 (admin.py) can be written in parallel with T008 (models.py) if admin imports are not needed immediately.
- After T021 passes: T022, T024, and T026 can all start in parallel.
- T027 (type: ignore sweep) can run in parallel with T026 (README).

---

## Implementation Strategy

### MVP (P1 User Stories 1–4 Only)

1. T001–T004 (setup)
2. T005–T006 (domain/constants.py — foundational)
3. T007–T010 (ORM models + migration)
4. T011–T013 (US1: init guard + factory)
5. T014–T015 (US2: category CRUD)
6. T016–T017 (US3: item/tag CRUD)
7. T018–T019 (US4: parent links)
8. **STOP and VALIDATE**: `pytest tests/contrib/django/ -v` → all green
9. `DjangoRepository` is fully functional; consumers can use it directly

### Full Delivery

10. T020–T021 (US5: full graph)
11. T022–T023 (US6: TOML config)
12. T024–T025 (US7: admin)
13. T026 (US8: README)
14. T027–T028 (polish + quality gates)
15. Open PR

---

## Notes

- `[US1]`–`[US8]` = traceability to spec user stories
- TDD is mandatory — every test task MUST produce failing tests before implementation starts
- `pytest.mark.django_db` required on all tests that touch the database
- `tests/django_settings.py` uses `:memory:` SQLite — no file cleanup needed
- `DJANGO_REPO_USING_DEFAULT` lives in `models.py` (adapter defaults stay in adapters — Principle I)
  and is imported everywhere else from there
- `# noqa: PLC0415` is required on every deferred import in `django_repository.py` and
  `contrib/django/__init__.py`
- Each `# type: ignore` in `django_repository.py` must have a one-line justification comment
- `taxomesh/contrib/django/` is excluded from mypy — no `django-stubs` needed (R-008)
- `0001_initial.py` MUST be generated via `makemigrations`, never hand-authored (FR-018)
- `list_*()` methods return unordered querysets — service.py already sorts by `sort_index` (R-013)
