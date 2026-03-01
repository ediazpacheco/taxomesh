# Feature Specification: Django Repository

**Feature Branch**: `012-django-repository`
**Created**: 2026-02-28
**Status**: Implemented
**Input**: "taxomesh already has pluggable storage via a typing.Protocol but only ships with YAML
and JSON file-based adapters. Django application developers who install taxomesh as a dependency
need a first-class ORM-backed repository so they can store their taxonomy in the same database as
their application without managing a separate JSON/YAML file."

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Install & Migrate (Priority: P1)

A Django developer adds `taxomesh[django]` to their project's dependencies, adds
`'taxomesh.contrib.django'` to `INSTALLED_APPS`, and runs `python manage.py migrate`. Six new
tables (`taxomesh_category`, `taxomesh_item`, `taxomesh_tag`, `taxomesh_category_parent_link`,
`taxomesh_item_parent_link`, `taxomesh_item_tag_link`) are created. The developer can then
construct `DjangoRepository()` and pass it to `TaxomeshService`.

**Why this priority**: Foundation — all other ORM-backed stories depend on the tables existing.

**Independent Test**: In a pytest-django test environment with `DATABASES = {"default": {...}}`,
run `call_command("migrate")` and verify that all six table names exist in the database.

**Acceptance Scenarios**:

1. **Given** `'taxomesh.contrib.django'` in `INSTALLED_APPS`, **When** `migrate` is run,
   **Then** six tables prefixed with `taxomesh_` are created in the database.
2. **Given** the six tables exist, **When** `python manage.py makemigrations --check taxomesh_contrib_django`
   is run, **Then** it exits zero (no pending migrations).
3. **Given** Django is not installed, **When** `DjangoRepository()` is constructed, **Then**
   `TaxomeshRepositoryError` is raised with a message containing `pip install taxomesh[django]`.

---

### User Story 2 — Category CRUD (Priority: P1)

A developer using `DjangoRepository` can create, retrieve, list, and delete categories. All
operations round-trip correctly — a category saved and retrieved has the same field values.

**Why this priority**: Core CRUD is the minimum viable backend.

**Independent Test**: Use `DjangoRepository` in a `pytest-django` test with `db` fixture.
Save a category, retrieve it by ID, list all categories, delete it, verify deletion.

**Acceptance Scenarios**:

1. **Given** a `DjangoRepository`, **When** `save_category(cat)` is called, **Then** a row is
   inserted in `taxomesh_category`.
2. **Given** a saved category, **When** `get_category(category_id)` is called, **Then** the
   returned object equals the original (field-for-field).
3. **Given** two saved categories, **When** `list_categories()` is called, **Then** both are
   returned.
4. **Given** a saved category, **When** `delete_category(category_id)` is called, **Then** it
   returns `True` and the row no longer exists.
5. **Given** a non-existent `category_id`, **When** `delete_category(category_id)` is called,
   **Then** it returns `False`.
6. **Given** a non-existent `category_id`, **When** `get_category(category_id)` is called,
   **Then** it returns `None`.
7. **Given** a category with `ExternalId` of each type (`UUID`, `int`, `str`), **When** it is
   saved and retrieved, **Then** the `external_id` field preserves the original Python type.

---

### User Story 3 — Item & Tag CRUD (Priority: P1)

A developer can save, retrieve, list, and delete items and tags. Tag-to-item associations can
be created (`assign_tag`) and removed (`remove_tag`). `assign_tag` is idempotent.

**Why this priority**: Items and tags are core domain entities alongside categories.

**Independent Test**: Save item + tag, assign tag to item, remove tag, verify all states.

**Acceptance Scenarios**:

1. **Given** a `DjangoRepository`, **When** `save_item(item)` / `save_tag(tag)` is called,
   **Then** the row is inserted.
2. **Given** a saved item and tag, **When** `assign_tag(tag_id, item_id)` is called twice,
   **Then** only one `taxomesh_item_tag_link` row exists (idempotent).
3. **Given** an assigned tag, **When** `remove_tag(tag_id, item_id)` is called, **Then** it
   returns `True` and the link row is deleted.
4. **Given** no existing link, **When** `remove_tag(tag_id, item_id)` is called, **Then** it
   returns `False`.
5. **Given** a saved tag, **When** `delete_tag(tag_id)` is called, **Then** it returns `True`.
6. **Given** a non-existent `tag_id`, **When** `delete_tag(tag_id)` is called, **Then** it
   returns `False`.

---

### User Story 4 — Parent Links (Priority: P1)

Category parent links (DAG edges) and item parent links (item placements) can be saved and
listed. Both support upsert semantics: saving the same `(category_id, parent_category_id)` or
`(item_id, category_id)` pair a second time updates `sort_index` in-place rather than creating
a duplicate.

**Why this priority**: Parent links are required for `get_graph()` to produce correct output.

**Acceptance Scenarios**:

1. **Given** a `DjangoRepository`, **When** `save_category_parent_link(link)` is called,
   **Then** a row is inserted in `taxomesh_category_parent_link`.
2. **Given** an existing link, **When** `save_category_parent_link` is called again with the
   same `(category_id, parent_category_id)` but a different `sort_index`, **Then** only one row
   exists with the updated `sort_index`.
3. **Given** saved links, **When** `list_category_parent_links()` is called, **Then** all links
   are returned.
4. **Given** a `DjangoRepository`, **When** `save_item_parent_link(link)` is called, **Then**
   a row is inserted.
5. **Given** an existing item link, **When** `save_item_parent_link` is called again with a
   different `sort_index`, **Then** only one row exists with the updated value.
6. **Given** saved item links, **When** `list_item_parent_links()` is called, **Then** all are
   returned.

---

### User Story 5 — Full Graph (Priority: P2)

`TaxomeshService.get_graph()` works end-to-end with `DjangoRepository` as the backend — the
graph structure (roots, children, items, tags) is identical to what `JsonRepository` or
`YAMLRepository` would return for the same data set.

**Why this priority**: Validates the adapter end-to-end, not just individual CRUD operations.

**Acceptance Scenarios**:

1. **Given** categories, items, tags, and links saved via `DjangoRepository`, **When**
   `service.get_graph()` is called, **Then** the returned `TaxomeshGraph` contains the correct
   root categories and child hierarchy.
2. **Given** the same taxonomy data loaded into both `DjangoRepository` and `JsonRepository`,
   **When** `get_graph()` is called on each, **Then** the graph structure is equivalent
   (categories and links match by ID and sort_index).

---

### User Story 6 — TOML `type = "django"` (Priority: P3)

A developer can configure `taxomesh.toml` with `[repository] type = "django"` and optionally
`using = "default"`. `TaxomeshService` constructs a `DjangoRepository` automatically via
`_build_repo_from_config()`.

**Why this priority**: Config-based auto-construction is a convenience feature, not a
correctness requirement.

**Acceptance Scenarios**:

1. **Given** `taxomesh.toml` with `[repository] type = "django"`, **When** `TaxomeshService()`
   is instantiated, **Then** `service.repository` is a `DjangoRepository`.
2. **Given** `taxomesh.toml` with `[repository] type = "django" using = "secondary"`, **When**
   `TaxomeshService()` is instantiated, **Then** `DjangoRepository` uses the `secondary` DB alias.
3. **Given** `taxomesh.toml` with unsupported type, **When** `TaxomeshService()` is
   instantiated, **Then** `TaxomeshConfigError` is raised with message listing `'yaml'`, `'json'`,
   and `'django'` as supported values.

---

### User Story 7 — Django Admin (Priority: P4)

All six ORM models appear in the Django admin interface with basic list and detail views.
No custom actions required — default `ModelAdmin` is sufficient.

**Acceptance Scenarios**:

1. **Given** `taxomesh.contrib.django` in `INSTALLED_APPS` and admin enabled, **When** the
   admin site is loaded, **Then** all six model classes appear in the `taxomesh_contrib_django`
   app section.

---

### User Story 8 — README Repositories Section (Priority: P2)

The README has a "Repositories" section above "Configuration" with subsections for YAML (default),
Django ORM, and JSON, plus a note on the pluggable `TaxomeshRepositoryBase` interface.

**Acceptance Scenarios**:

1. **Given** the README, **When** read, **Then** a "Repositories" section exists, YAML subsection
   is first (marked as service default), Django subsection shows `pip install taxomesh[django]`
   and a code example demonstrating `DjangoRepository`.
2. **Given** the README, **When** read, **Then** the feature checklist contains
   `[x] Django ORM backend (taxomesh[django])`.

---

### Edge Cases

- What if Django is installed but not configured (no `django.setup()`)? → `DjangoRepository.__init__`
  does not call `django.setup()`; the caller is responsible for app setup. The error from Django
  itself propagates as `TaxomeshRepositoryError`.
- What if a write inside a transaction fails? → `transaction.atomic()` rolls back the write.
  `DatabaseError` is caught and re-raised as `TaxomeshRepositoryError`.
- What if an `ExternalId` of type `UUID` is saved and then retrieved with `external_id_type = "uuid"`?
  → The `_deserialize_external_id` helper reconstructs the `UUID` object from the stored string.
- What if `get_config_summary()` is called? → Returns `"django:<engine>/<alias>"`, e.g.
  `"django:sqlite3/default"` — never NAME/USER/PASSWORD/HOST/PORT.
- What if `delete_category` is called for a category that has parent links or item placements?
  → **DjangoRepository contract**: `on_delete=CASCADE` on all link model FKs silently removes
  all associated `CategoryParentLinkModel` rows (DAG edges) and `ItemParentLinkModel` rows
  (item placements) when the category is deleted. This is intentional and differs from
  file-based repos (which leave link records in place). Callers MUST NOT assume orphaned
  link records are preserved after `delete_category`.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a `DjangoRepository` class at
  `taxomesh/adapters/repositories/django_repository.py` that fully satisfies
  `TaxomeshRepositoryBase` — all 18 protocol methods implemented with correct signatures.
- **FR-002**: Neither `DjangoRepository` nor `taxomesh/contrib/django/__init__.py` MUST import
  any Django symbol at module level. All Django imports MUST occur inside function/method bodies
  (`# noqa: PLC0415`). This ensures `import taxomesh` and
  `from taxomesh.contrib.django import get_taxomesh_service_with_django` both succeed without
  Django installed.
- **FR-003**: `DjangoRepository.__init__` MUST raise `TaxomeshRepositoryError` (not `ImportError`)
  with a message containing `pip install taxomesh[django]` if Django is not installed.
- **FR-004**: The system MUST provide a Django app at `taxomesh/contrib/django/` with
  `AppConfig` label `taxomesh_contrib_django`, 6 ORM models, migrations, and admin registration.
- **FR-005**: All 6 ORM models MUST define `Meta.app_label = 'taxomesh_contrib_django'`.
- **FR-006**: `ExternalId` round-trip MUST be preserved via two fields per entity:
  `external_id CharField(max_length=512)` + `external_id_type CharField(max_length=8,
  choices=EXTERNAL_ID_TYPE_CHOICES)`.
- **FR-007**: All writes MUST be wrapped in `django.db.transaction.atomic(using=self._using)`.
- **FR-008**: All `django.db.DatabaseError` exceptions MUST be caught at the adapter boundary and
  re-raised as `TaxomeshRepositoryError` with the original error chained.
- **FR-009**: `get_config_summary()` MUST return `"django:<engine>/<alias>"` and MUST NOT include
  NAME, USER, PASSWORD, HOST, or PORT from the Django database settings.
- **FR-010**: `assign_tag` MUST be idempotent via `get_or_create`.
- **FR-011**: `save_category_parent_link` and `save_item_parent_link` MUST upsert via
  `update_or_create`.
- **FR-012**: `django>=4.2` MUST be added to `[project.optional-dependencies] django` in
  `pyproject.toml`. `pytest-django>=4.8` MUST be added to dev deps. `django-stubs` MUST NOT
  be added — it is unnecessary given deferred imports in `django_repository.py` and the
  `contrib/django/` mypy exclusion.
- **FR-013**: `TaxomeshService._build_repo_from_config()` MUST be extended with a `"django"`
  branch that lazy-imports `DjangoRepository` and supports an optional `using` key.
- **FR-014**: The error message in `_build_repo_from_config` MUST be updated to list
  `'yaml'`, `'json'`, and `'django'` as supported types.
- **FR-015**: The README MUST be updated with a "Repositories" section containing YAML (first,
  service default), Django ORM, and JSON subsections. The section MUST explain the pluggable
  `TaxomeshRepositoryBase` interface and note that all interfaces (CLI, Django admin, Python API)
  are repository-agnostic.
- **FR-016**: All named constants listed in the data model (`CATEGORY_TABLE`, `ITEM_TABLE`,
  `TAG_TABLE`, `CATEGORY_PARENT_LINK_TABLE`, `ITEM_PARENT_LINK_TABLE`, `ITEM_TAG_LINK_TABLE`,
  `APP_LABEL`, `EXTERNAL_ID_TYPE_CHOICES`, `EXTERNAL_ID_TYPE_UUID`, `EXTERNAL_ID_TYPE_INT`,
  `EXTERNAL_ID_TYPE_STR`, `DJANGO_REPO_USING_DEFAULT`) MUST be defined as `Final` constants.
- **FR-017**: `mypy --strict` MUST pass for all taxomesh source **except** `taxomesh/contrib/django/`,
  which MUST be excluded via an `exclude` glob in `pyproject.toml [tool.mypy]`. Rationale:
  `contrib/django/` is ORM/framework glue; excluding it avoids framework-stub noise.
  `taxomesh/adapters/repositories/django_repository.py` (the hexagonal adapter) is NOT excluded
  and MUST pass `--strict`. No `django-stubs` or mypy Django plugin is required — deferred
  imports mean no Django symbol is visible to mypy at module level. Any `# type: ignore` in
  `django_repository.py` MUST have a one-line justification comment.
- **FR-018**: The initial migration (`0001_initial.py`) MUST ultimately be generated via
  `manage.py makemigrations` and committed. The hand-authored version checked in during this
  spec cycle is a temporary placeholder; regenerate with `manage.py makemigrations` once Django
  is available in the development environment.
  <!-- TODO(FR-018): regenerate 0001_initial.py via makemigrations when Django is in dev env -->
- **FR-019**: `DjangoRepository.delete_category()` MUST rely on ORM `on_delete=CASCADE` to
  automatically remove all associated `CategoryParentLinkModel` and `ItemParentLinkModel` rows.
  This cascade behaviour MUST be documented as the explicit `DjangoRepository` contract.
  `delete_tag()` MUST similarly cascade-delete all associated `ItemTagLinkModel` rows.
  `delete_item()` MUST cascade-delete associated `ItemParentLinkModel` and `ItemTagLinkModel` rows.
- **FR-020**: All repository `list_*()` methods MUST return records without any ordering
  guarantee — no `ORDER BY` in `DjangoRepository`, no insertion-order dependency in
  `JsonRepository` / `YAMLRepository`. `TaxomeshService` owns ordering exclusively:
  wherever `list_category_parent_links()` or `list_item_parent_links()` results are consumed
  (e.g. `get_graph()`), the service MUST sort them with
  `sorted(links, key=lambda l: l.sort_index)` before use. Tests for repository `list_*()` methods
  MUST use set comparison or sort both sides before asserting equality.
  *(Cross-cutting: the sort logic in `service.py` applies uniformly to all backends.)*
- **FR-021**: taxomesh core MUST remain fully agnostic about Django. No Django detection or
  import MUST ever appear in `taxomesh/application/` or `taxomesh/domain/`. `DjangoRepository`
  is always constructed explicitly by the caller — never as an automatic fallback.
- **FR-022**: `taxomesh/contrib/django/__init__.py` MUST expose a convenience factory function
  `get_taxomesh_service_with_django(using: str = DJANGO_REPO_USING_DEFAULT) -> TaxomeshService`
  that constructs `TaxomeshService(repository=DjangoRepository(using=using))`. `DjangoRepository`
  MUST be imported inside the function body (`# noqa: PLC0415`) — no module-level Django import.
  Consumer import: `from taxomesh.contrib.django import get_taxomesh_service_with_django`.
  This import MUST succeed without Django installed; the `TaxomeshRepositoryError` surfaces
  only when the function is called. This is the recommended entry point for Django application
  developers; taxomesh core is unaware of it.
- **FR-023**: A new module `taxomesh/domain/constants.py` MUST be created with all shared field
  constraint `Final` constants: `MAX_CATEGORY_NAME_LENGTH`, `MAX_TAG_NAME_LENGTH`,
  `MAX_DESCRIPTION_LENGTH`, `MAX_EXTERNAL_ID_STR_LENGTH`, `MAX_EXTERNAL_ID_DB_LENGTH`,
  `MAX_EXTERNAL_ID_TYPE_LENGTH`. The existing domain model files
  `taxomesh/domain/models/category.py`, `item.py`, and `tag.py` MUST be updated to import
  from `taxomesh/domain/constants.py` and replace all inline `max_length` literals. The Django
  ORM models in `taxomesh/contrib/django/models.py` MUST also import from
  `taxomesh/domain/constants.py`. Magic literal duplication across these layers is forbidden
  (Constitution Principle X). This refactor is in scope for spec 012.

### Key Entities

- **DjangoRepository**: Storage adapter implementing `TaxomeshRepositoryBase` using Django ORM.
  Stores data in a Django-managed database. Accepts an optional `using` kwarg to specify the
  database alias. Deferred-imports all Django symbols.
- **TaxomeshContribDjangoConfig**: `AppConfig` subclass at `taxomesh/contrib/django/apps.py`.
  Label: `taxomesh_contrib_django`. Consumer adds `'taxomesh.contrib.django'` to `INSTALLED_APPS`.
- **6 ORM models**: See data-model.md for field specifications.
- **tests/django_settings.py**: Minimal Django settings module used by the test suite
  (`pytest-django` reads it via `django_settings` fixture or `pytest.ini`).
- **`get_taxomesh_service_with_django(using)`**: Convenience factory defined in
  `taxomesh/contrib/django/__init__.py`. Constructs
  `TaxomeshService(repository=DjangoRepository(using=using))`. Consumer import:
  `from taxomesh.contrib.django import get_taxomesh_service_with_django`. Recommended entry
  point for Django application developers; keeps taxomesh core Django-agnostic.
- **`taxomesh/domain/constants.py`**: New module defining all shared field constraint `Final`
  constants (e.g. `MAX_NAME_LENGTH`, `MAX_DESCRIPTION_LENGTH`, `MAX_EXTERNAL_ID_LENGTH`).
  Imported by both Pydantic domain models and Django ORM models. Single source of truth.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Running `pytest tests/contrib/django/test_django_repository.py -v` passes all
  tests against an in-process SQLite database.
- **SC-002**: `python manage.py makemigrations --check taxomesh_contrib_django` exits zero after
  the initial migration is committed.
- **SC-003**: Both `import taxomesh` and
  `from taxomesh.contrib.django import get_taxomesh_service_with_django` succeed without Django
  installed (deferred imports enforced in both `DjangoRepository` and `contrib/django/__init__.py`).
- **SC-004**: All four quality gates pass: `ruff check .`, `ruff format --check .`,
  `mypy --strict .`, `pytest --cov=taxomesh --cov-fail-under=80`.
  Note: `taxomesh/contrib/django/` is excluded from `mypy --strict` via `pyproject.toml`
  `[tool.mypy] exclude` glob; `taxomesh/adapters/repositories/django_repository.py` is NOT excluded.
- **SC-005**: `get_config_summary()` output contains neither `PASSWORD` nor `HOST` nor `PORT`.
- **SC-006**: `assign_tag` called twice for the same `(tag_id, item_id)` pair results in
  exactly one row in `taxomesh_item_tag_link`.

---

## Clarifications

### Session 2026-02-28

- Q: When `delete_category(id)` is called, should the ORM CASCADE silently remove associated parent links and item placements, or should the adapter guard against active links? → A: Accept silent CASCADE — deleting a category automatically removes its `CategoryParentLinkModel` and `ItemParentLinkModel` rows. This is the explicit `DjangoRepository` contract; callers must not assume orphaned link records are preserved (unlike file-based repos).
- Q: What ordering guarantee should `list_categories()`, `list_items()`, `list_tags()`, `list_category_parent_links()`, and `list_item_parent_links()` provide? → A: **No ordering guarantee from any repository** (DjangoRepository and all others). `list_*` methods return records in unspecified order. **`TaxomeshService`** owns ordering: it sorts `list_category_parent_links()` and `list_item_parent_links()` results by `sort_index` in Python before use in graph construction. `list_categories/items/tags()` have no sort_index so callers sort if needed. This is a cross-cutting concern — a follow-up task should verify/apply consistent no-ordering-guarantee behaviour across `JsonRepository` and `YAMLRepository` too.
- Q: Should `mypy --strict` apply to `taxomesh/contrib/django/` or should it be excluded? → A: Exclude `taxomesh/contrib/django/` entirely from mypy via an `exclude` glob in `pyproject.toml`. It is framework glue code (ORM model definitions, AppConfig, admin) where django-stubs gaps would require excessive `# type: ignore` noise. `taxomesh/adapters/repositories/django_repository.py` (the hexagonal adapter) remains under full `--strict`.
- Q: Should the CI test suite run `DjangoRepository` tests against PostgreSQL in addition to SQLite? → A: SQLite only for this spec. PostgreSQL CI adds Docker service complexity and is deferred to a future spec once the adapter is stable. `tests/django_settings.py` uses SQLite `:memory:` exclusively.
- Q: Should `DjangoRepository` ever be the automatic fallback when Django is detected, or always require explicit opt-in? → A: Always explicit — taxomesh core is fully agnostic about Django and must never auto-detect it. `taxomesh/contrib/django/` provides a convenience factory `get_taxomesh_service_with_django()` that constructs `TaxomeshService(repository=DjangoRepository(...))` so Django developers have a one-call entry point without taxomesh core knowing about Django. Additionally, all `max_length` and similar field constraint values shared between Pydantic domain models and Django ORM models MUST be defined as `Final` constants in `taxomesh/domain/constants.py` (new file) and imported from there in both locations — never duplicated.
- Q: Should the `taxomesh/domain/constants.py` refactor (updating existing domain model files to import shared constants) be in scope for spec 012, or extracted to a separate prerequisite spec? → A: In scope for 012 — create `domain/constants.py` and update all existing domain model files (`category.py`, `item.py`, `tag.py`) in the same PR. This eliminates the TODO-comment workaround and keeps the codebase consistent from day one.
- Q: Where should `get_taxomesh_service_with_django()` live — `service.py` or `__init__.py`? → A: `taxomesh/contrib/django/__init__.py`. Consumer import path: `from taxomesh.contrib.django import get_taxomesh_service_with_django`.
- Q: Does `TaxomeshService` currently sort `list_category_parent_links()` / `list_item_parent_links()` by `sort_index`, or is that sorting absent? → A: Currently absent — adding it is new code in `service.py`. Use `sorted(links, key=lambda l: l.sort_index)` (Python built-in, O(n log n), no dependencies). This applies to both `CategoryParentLink` and `ItemParentLink` lists wherever the service consumes them (e.g. in `get_graph()`).
- Q: Should `django-stubs` and the mypy Django plugin be kept as dev dependencies, or dropped given the deferred-import architecture and `contrib/django/` mypy exclusion? → A: Drop both entirely — no `django-stubs`, no `plugins = ["mypy_django_plugin.main"]` in `[tool.mypy]`. Contributors use their IDE tooling of choice for `contrib/django/`.
- Q: Should `taxomesh/contrib/django/__init__.py` use deferred imports inside `get_taxomesh_service_with_django()`, or may it import `DjangoRepository` at module level? → A: Deferred — no module-level Django imports in `__init__.py`. `DjangoRepository` is imported inside the function body (`# noqa: PLC0415`). `from taxomesh.contrib.django import get_taxomesh_service_with_django` MUST succeed without Django installed; the error surfaces only when the function is called.

---

## Assumptions

- The minimum Django version is 4.2 (LTS). `JSONField` works with SQLite (Python 3.11 ships
  SQLite ≥ 3.38), PostgreSQL, and MySQL under this version.
- `DjangoRepository` does not call `django.setup()`. The consuming application is responsible
  for Django initialisation. This follows the standard library-as-dependency pattern.
- The `ExternalId` serialisation uses `"uuid"`, `"int"`, `"str"` as type discriminator values.
  Maximum serialized length of `external_id` is 512 characters (UUID string is 36 chars, ints
  up to ~20 digits, strings up to 256 chars per `ExternalId` type constraint — 512 is safe).
- `on_delete=CASCADE` is used for `CategoryParentLinkModel` FKs (deleting a category removes
  its parent links). `ItemParentLinkModel` and `ItemTagLinkModel` also use `CASCADE`.
- The migration is generated with SQLite as the test DB. It is compatible with PostgreSQL and
  MySQL since no DB-specific field types are used beyond `UUIDField`, `CharField`, `JSONField`,
  and `IntegerField`.
- The `tests/django_settings.py` file configures `DATABASES["default"]` as SQLite in-memory
  (`:memory:`) for fast isolated tests. PostgreSQL CI coverage is out of scope for this spec
  and deferred to a future iteration once the adapter is stable.
