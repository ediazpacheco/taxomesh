# Implementation Plan: Item & Category Slug Field

**Branch**: `018-item-category-slug` | **Date**: 2026-03-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/018-item-category-slug/spec.md`

---

## Summary

Add `slug` as a first-class optional field (default `""`) to both the `Item` and `Category`
domain models. A slug is a short, human-friendly stable identifier separate from UUID and
`external_id`. The implementation spans domain models, the repository protocol and all three
backend adapters (JSON, YAML, Django ORM), the service layer, CLI graph rendering, and Django
admin integration. Uniqueness is enforced at two levels: a DB partial unique constraint (where
`slug != ""`) and a pre-write check in `TaxomeshService` that raises `TaxomeshDuplicateSlugError`
on conflict. The in-place migration edit strategy is used because the project has not shipped to
production.

---

## Technical Context

**Language/Version**: Python 3.11 (targets 3.11–3.13)
**Primary Dependencies**: Pydantic v2 (domain models), Typer ≥ 0.12 + Rich ≥ 13.0 (CLI), Django ≥ 4.2 (optional contrib), pyyaml ≥ 6.0
**Storage**: JSON file (`JsonRepository`), YAML file (`YAMLRepository`), Django ORM (`DjangoRepository`)
**Testing**: pytest with pytest-cov (≥ 80% coverage gate)
**Target Platform**: Python library; no specific OS target
**Project Type**: library + CLI tool + optional Django integration
**Performance Goals**: No latency targets; file-based slug lookups use O(n) linear scan (acceptable per spec Assumptions)
**Constraints**: Slug max 256 chars; empty string never subject to uniqueness; partial unique DB constraint; in-place migration edit
**Scale/Scope**: Local taxonomy tool; small data volumes expected

---

## Constitution Check

| Principle | Status | Notes |
|---|---|---|
| I. Hexagonal Architecture | ✅ Pass | Slug field added to domain layer. Service layer does uniqueness checks. Repository protocol extended. No domain→adapter imports introduced. |
| II. TaxomeshService is single facade | ✅ Pass | `create_category`, `update_category`, `create_item`, `update_item` extended with `slug` param on `TaxomeshService`. |
| III. Repository as Protocol | ✅ Pass | Two new methods added to `TaxomeshRepositoryBase` (Protocol). No inheritance required. |
| IV. Pydantic domain models + mypy strict | ✅ Pass | `slug` field uses `Annotated[str, Field(max_length=MAX_SLUG_LENGTH)]`; no unbounded strings. |
| V. Custom exception hierarchy | ✅ Pass | `TaxomeshDuplicateSlugError(TaxomeshValidationError)` added per FR-004. No silent failures. |
| VI. DAG integrity | ✅ Pass | No changes to DAG logic. |
| VII. Spec-driven development | ✅ Pass | This plan derives from `018-item-category-slug/spec.md`. |
| VIII. Quality gates | ✅ Pass | All gates verified: ruff ✓, mypy --strict ✓, pytest 539 tests 92.25% coverage. |
| IX. Pluggable REST views | ✅ N/A | No REST view changes in this feature. |
| X. Named constants | ✅ Pass | `MAX_SLUG_LENGTH = 256` and `DEFAULT_SLUG = ""` defined in `taxomesh.domain.constants`. No magic literals. |
| XI. Object-oriented by default | ✅ Pass | No new module-level functions; all logic lives in existing classes. |

**Complexity Tracking**: No violations to justify.

---

## Project Structure

### Documentation (this feature)

```text
specs/018-item-category-slug/
├── plan.md              ← This file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── contracts/
│   └── service-api.md   ← Phase 1 output
├── checklists/
│   └── requirements.md  ← Created by /speckit.specify
└── tasks.md             ← Phase 2 output (/speckit.tasks — not yet created)
```

### Source Code (affected files, in dependency order)

```text
taxomesh/
├── domain/
│   ├── constants.py                            # MAX_SLUG_LENGTH, DEFAULT_SLUG (NEW)
│   ├── models/
│   │   ├── category.py                         # slug field + __str__ (NEW)
│   │   └── item.py                             # slug field + __str__ (NEW)
├── exceptions.py                               # TaxomeshDuplicateSlugError (NEW)
├── ports/
│   └── repository.py                           # get_item_by_slug, get_category_by_slug (NEW)
├── adapters/
│   └── repositories/
│       ├── json_repository.py                  # slug lookup methods (NEW)
│       ├── yaml_repository.py                  # slug lookup methods (NEW)
│       └── django_repository.py                # slug in row conversion + lookups (NEW)
├── application/
│   └── service.py                              # slug param + uniqueness checks (NEW)
├── adapters/
│   └── cli/
│       └── main.py                             # slug (uuid) rendering in graph (NEW)
└── contrib/
    └── django/
        ├── models.py                           # slug field + constraint + __str__ (NEW)
        ├── migrations/
        │   └── 0001_initial.py                 # slug column + partial unique (EDITED IN-PLACE)
        └── admin.py                            # slug in list_display + save_model (NEW)

tests/
├── domain/
│   └── test_slug_field.py                      # NEW test file
├── service/
│   ├── conftest.py                             # InMemoryRepository slug lookups (NEW)
│   ├── test_service_slug.py                    # NEW test file
│   ├── test_json_repository.py                 # slug round-trip + lookup cases (NEW)
│   └── test_yaml_repository.py                 # slug round-trip + lookup cases (NEW)
├── contrib/django/
│   ├── test_django_repository.py               # slug save/retrieve + lookup (NEW)
│   └── test_admin.py                           # updated __str__ assertions (UPDATED)
├── adapters/cli/
│   └── test_graph_output.py                    # slug rendering cases (NEW)
└── test_cli.py                                 # updated Category.__str__ assertions (UPDATED)
```

---

## Implementation Phases

### Phase 0 (Completed): Research

See [research.md](research.md). All design decisions resolved:

1. Partial unique constraint with `slug=""` sentinel (not nullable).
2. Service-layer uniqueness check before DB write + DB constraint as safety net.
3. O(n) linear scan for file-based repos (acceptable per spec Assumptions).
4. In-place migration edit (project not in production).
5. No slug format validation (explicitly out of scope).
6. `TaxomeshDuplicateSlugError(TaxomeshValidationError)` per FR-004.
7. `__str__` format: Category always shows `name` and `category_id`; slug is shown as `s: {slug} - ` prefix when non-empty; `external_id` is NOT included (per FR-006). Item shows slug prefix + `({item_id}) -> {external_id}`; no name field.

---

### Phase 1 (Complete): File-by-File Changes

Changes are ordered by dependency: domain first, then ports, then adapters, then service, then CLI/admin.

#### Step 1: `taxomesh/domain/constants.py`

Add two constants at end of file:

```python
MAX_SLUG_LENGTH: Final[int] = 256
DEFAULT_SLUG: Final[str] = ""
```

#### Step 2: `taxomesh/exceptions.py`

Add after `TaxomeshCyclicDependencyError`:

```python
class TaxomeshDuplicateSlugError(TaxomeshValidationError):
    """Raised when a non-empty slug is already used by another entity of the same type."""
```

#### Step 3: `taxomesh/domain/models/item.py`

- Import `MAX_SLUG_LENGTH` from `taxomesh.domain.constants`.
- Add field after `external_id`:
  ```python
  slug: Annotated[str, Field(max_length=MAX_SLUG_LENGTH)] = ""
  ```
- Add `__str__`:
  ```python
  def __str__(self) -> str:
      prefix = f"{self.slug} " if self.slug else ""
      return f"{prefix}({self.item_id}) -> {self.external_id}"
  ```

#### Step 4: `taxomesh/domain/models/category.py`

- Import `MAX_SLUG_LENGTH` from `taxomesh.domain.constants`.
- Add field after `external_id`:
  ```python
  slug: Annotated[str, Field(max_length=MAX_SLUG_LENGTH)] = ""
  ```
- Add `__str__`:
  ```python
  def __str__(self) -> str:
      slug_part = f"s: {self.slug} - " if self.slug else ""
      return f"{self.name} ({slug_part}id: {self.category_id})"
  ```

#### Step 5: `taxomesh/ports/repository.py`

Add two methods to `TaxomeshRepositoryBase` (after `list_categories_by_external_id`):

```python
def get_item_by_slug(self, slug: str) -> Item | None: ...
def get_category_by_slug(self, slug: str) -> Category | None: ...
```

#### Step 6: `taxomesh/adapters/repositories/json_repository.py`

Add two methods (Pydantic model_dump/model_validate auto-handles `slug`):

```python
def get_item_by_slug(self, slug: str) -> Item | None:
    return next((i for i in self._items.values() if i.slug == slug), None)

def get_category_by_slug(self, slug: str) -> Category | None:
    return next((c for c in self._categories.values() if c.slug == slug), None)
```

#### Step 7: `taxomesh/adapters/repositories/yaml_repository.py`

Identical two methods (same Pydantic round-trip pattern as JSON).

#### Step 8: `taxomesh/adapters/repositories/django_repository.py`

- In `_row_to_category`: add `slug=row.slug` to `Category(...)` constructor call.
- In `_row_to_item`: add `slug=row.slug` to `Item(...)` constructor call.
- In `save_category` defaults dict: add `"slug": category.slug`.
- In `save_item` defaults dict: add `"slug": item.slug`.
- Add slug lookup methods:
  ```python
  def get_item_by_slug(self, slug: str) -> Item | None:
      row = self._ItemModel.objects.using(self._using).filter(slug=slug).first()
      return self._row_to_item(row) if row is not None else None

  def get_category_by_slug(self, slug: str) -> Category | None:
      row = self._CategoryModel.objects.using(self._using).filter(slug=slug).first()
      return self._row_to_category(row) if row is not None else None
  ```

#### Step 9: `taxomesh/contrib/django/models.py`

- Import `MAX_SLUG_LENGTH` from `taxomesh.domain.constants`.
- **`CategoryModel`**: add slug field + partial unique constraint + update `__str__`:
  ```python
  slug = models.CharField(max_length=MAX_SLUG_LENGTH, blank=True, default="", db_index=True)

  class Meta:
      constraints = [
          models.UniqueConstraint(
              fields=["slug"],
              condition=~models.Q(slug=""),
              name="taxomesh_category_slug_unique_nonempty",
          )
      ]

  def __str__(self) -> str:
      slug_part = f"s: {self.slug} - " if self.slug else ""
      return f"{self.name} ({slug_part}id: {self.category_id})"
  ```
- **`ItemModel`**: symmetric; constraint name `"taxomesh_item_slug_unique_nonempty"`.
- **`ItemParentLinkModel.__str__`**: simplify to `f"{self.item} → {self.category.name}"`.

#### Step 10: `taxomesh/contrib/django/migrations/0001_initial.py`

Edit in-place:
- Add `("slug", models.CharField(blank=True, default="", max_length=256, db_index=True))` to `CategoryModel` and `ItemModel` `CreateModel` fields lists.
- Add `"constraints": [models.UniqueConstraint(fields=["slug"], condition=~models.Q(slug=""), name="taxomesh_category_slug_unique_nonempty")]` to `CategoryModel` options.
- Symmetric for `ItemModel` with name `"taxomesh_item_slug_unique_nonempty"`.

#### Step 11: `taxomesh/application/service.py`

- Import `TaxomeshDuplicateSlugError`.
- `create_category(name, description="", metadata=None, slug="")`:
  - If `slug`: call `self._repo.get_category_by_slug(slug)`; raise `TaxomeshDuplicateSlugError` if result is not `None`.
  - Pass `slug=slug` to `Category(...)`.
- `update_category(category_id, name=None, description=None, slug=None)`:
  - If `slug is not None and slug`: check `get_category_by_slug(slug)` ≠ `None` and `existing.category_id != category_id` → raise.
  - If `slug is not None`: set `category.slug = slug`.
- `create_item(external_id, metadata=None, slug="")`:
  - Symmetric with `create_category`.
- `update_item(item_id, enabled=None, slug=None)`:
  - Symmetric with `update_category`.

#### Step 12: `taxomesh/adapters/cli/main.py`

Add `--slug` option to the four CRUD commands (FR-016):

```python
# category_add / item_add: optional slug, default ""
slug: str = typer.Option("", "--slug", help="Optional URL-friendly slug")
svc.create_category(name=name, slug=slug)  # or create_item(...)

# category_update / item_update: optional slug, default None (no change)
slug: str | None = typer.Option(None, "--slug", help="New slug (pass empty string to clear)")
svc.update_category(category_id=cat_id, slug=slug)  # or update_item(...)
```

Also update `_add_graph_node()` UUID display segments:

```python
# Category identifier
cat_uuid_label = f"{cat.slug} ({cat.category_id})" if cat.slug else str(cat.category_id)

# Item identifier
item_uuid_label = f"{item.slug} ({item.item_id})" if item.slug else str(item.item_id)
```

#### Step 13: `taxomesh/contrib/django/admin.py`

- `CategoryModelAdmin.list_display`: add `"slug"` after `"name"`.
- `ItemModelAdmin.list_display`: add `"slug"` after `"external_id"`.
- `_flatten_graph()`: add `"slug": cat.slug or None` / `"slug": item.slug or None`.
- `CategoryModelAdmin.save_model` and `ItemModelAdmin.save_model`: pass `slug=obj.slug` to service `create_*` / `update_*` calls.

---

### Phase 2: Test Files

> **TDD rule**: tests must exist before implementation is marked complete.
> All test files below are written (or extended) as part of this feature.

#### New: `tests/domain/test_slug_field.py`

- `test_item_slug_defaults_to_empty_string`
- `test_category_slug_defaults_to_empty_string`
- `test_item_str_with_slug_and_external_id`
- `test_item_str_without_slug_with_external_id`
- `test_category_str_with_name_and_slug`
- `test_category_str_with_name_no_slug`
- `test_item_slug_max_length_accepted` (255 chars)
- `test_item_slug_too_long_rejected` (257 chars → Pydantic ValidationError)
- `test_category_slug_max_length_accepted`
- `test_category_slug_too_long_rejected`

#### New: `tests/service/test_service_slug.py`

- `test_create_category_with_slug_stores_it`
- `test_create_item_with_slug_stores_it`
- `test_create_category_duplicate_slug_raises`
- `test_create_item_duplicate_slug_raises`
- `test_two_categories_with_empty_slug_no_conflict`
- `test_two_items_with_empty_slug_no_conflict`
- `test_item_and_category_same_slug_no_conflict` (namespaces independent)
- `test_update_category_slug_changes_it`
- `test_update_item_slug_changes_it`
- `test_update_category_own_slug_no_error`
- `test_update_item_own_slug_no_error`
- `test_update_category_taking_other_slug_raises`
- `test_update_item_taking_other_slug_raises`
- `test_update_category_clearing_slug_succeeds`
- `test_update_item_clearing_slug_succeeds`

#### Extended: `tests/service/test_json_repository.py`

- `test_item_slug_round_trips_in_json`
- `test_category_slug_round_trips_in_json`
- `test_get_item_by_slug_found`
- `test_get_item_by_slug_not_found`
- `test_get_category_by_slug_found`
- `test_get_category_by_slug_not_found`

#### Extended: `tests/service/test_yaml_repository.py`

Same 6 cases as JSON above (YAML backend).

#### Extended: `tests/contrib/django/test_django_repository.py`

- `test_item_slug_persisted_and_retrieved`
- `test_category_slug_persisted_and_retrieved`
- `test_get_item_by_slug_found`
- `test_get_item_by_slug_not_found`
- `test_get_category_by_slug_found`
- `test_get_category_by_slug_not_found`

#### Extended: `tests/adapters/cli/test_graph_output.py` — `TestSlugRendering` class

- `test_category_with_slug_renders_slug_and_uuid`
- `test_category_without_slug_renders_uuid_only`
- `test_item_with_slug_renders_slug_and_uuid`
- `test_item_without_slug_renders_uuid_only`

#### Updated: `tests/contrib/django/test_admin.py`

Tests updated to match the canonical `__str__` formats (FR-005, FR-006):
- Category: `"{name} (s: {slug} - id: {category_id})"` / `"{name} (id: {category_id})"`
- Item: `"{slug} ({item_id}) -> {external_id}"` / `"({item_id}) -> {external_id}"`
- Item and link `__str__` assertions updated to match new format

#### Updated: `tests/test_cli.py`

Five tests updated whose assertions used category name strings from `Category.__str__`;
assertions updated to check for `"{name} (id: {category_id})"` format (name still present, slug segment absent when empty).

#### Updated: `tests/service/conftest.py` — `InMemoryRepository`

Add slug lookup methods to satisfy the extended Protocol:

```python
def get_item_by_slug(self, slug: str) -> Item | None:
    return next((i for i in self._items.values() if i.slug == slug), None)

def get_category_by_slug(self, slug: str) -> Category | None:
    return next((c for c in self._categories.values() if c.slug == slug), None)
```

---

## Verification

Run after all changes are in place:

```bash
# Static analysis
ruff check .
ruff format --check .
mypy --strict .

# Incremental test runs (recommended order)
pytest tests/domain/test_slug_field.py -v
pytest tests/service/test_service_slug.py -v
pytest tests/service/test_json_repository.py tests/service/test_yaml_repository.py -v
pytest tests/contrib/django/ -v
pytest tests/adapters/cli/ -v

# Final gate
pytest --cov=taxomesh --cov-fail-under=80
```

Expected: ≥ 539 tests, ≥ 92% coverage, zero lint/type errors.

---

## Dependencies and Order Summary

```
constants.py
    ↓
exceptions.py
    ↓
domain/models/item.py, domain/models/category.py
    ↓
ports/repository.py
    ↓
json_repository.py, yaml_repository.py, django_repository.py
    ↓
contrib/django/models.py + 0001_initial.py
    ↓
application/service.py
    ↓
adapters/cli/main.py
    ↓
contrib/django/admin.py
    ↓
tests/ (all files above, TDD — tests written with/before implementation)
```
