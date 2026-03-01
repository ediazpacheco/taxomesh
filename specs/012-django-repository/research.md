# Research: Django Repository

**Branch**: `012-django-repository` | **Date**: 2026-02-28

---

## R-001: Django Version Floor — 4.2 LTS

**Decision**: `django>=4.2` as the minimum version.

**Rationale**: Django 4.2 is the current LTS release (supported until April 2026, extended
security support until April 2027). It is the oldest version where `JSONField` works correctly
across SQLite (Python 3.11 ships SQLite ≥ 3.38, which supports JSON1), PostgreSQL, and MySQL
without extra configuration. Targeting older releases (3.x) would require patching `JSONField`
behaviour on SQLite and adds complexity with no user benefit.

**Alternatives considered**:
- `django>=3.2` — Previous LTS; EOL. `JSONField` has rough SQLite edges on older Python.
  Rejected: adds test burden for no gain.
- `django>=5.0` — Latest. Excludes users still on 4.2 LTS. Rejected: premature.

---

## R-002: Deferred Import Pattern

**Decision**: All Django symbols imported inside `__init__` and method bodies.
`# noqa: PLC0415` on every deferred import line. Pattern mirrors `service.py` lines 80
and 107–108.

**Rationale**: `import taxomesh` must succeed on any Python 3.11+ environment, including
those where Django is not installed. Module-level `import django` would cause `ImportError`
for non-Django users.

**Implementation note**: In `DjangoRepository.__init__`:
```python
def __init__(self, using: str = DJANGO_REPO_USING_DEFAULT) -> None:
    try:
        import django  # noqa: PLC0415
        from taxomesh.contrib.django.models import CategoryModel  # noqa: PLC0415
        # ... other model imports
    except ImportError as exc:
        from taxomesh.domain.exceptions import TaxomeshRepositoryError  # noqa: PLC0415
        raise TaxomeshRepositoryError(
            "Django is not installed. Run: pip install taxomesh[django]"
        ) from exc
    self._using = using
    self._models = _OrmModels(CategoryModel, ItemModel, TagModel, ...)
```

---

## R-003: ExternalId Round-Trip Strategy

**Decision**: Two ORM columns per entity: `external_id CharField(max_length=512)` +
`external_id_type CharField(max_length=8, choices=EXTERNAL_ID_TYPE_CHOICES)`.

**Rationale**: `ExternalId = UUID | int | str`. A bare `CharField` stores all three as strings,
but on read there is no way to know whether `"42"` was originally `42` (int) or `"42"` (str),
nor whether `"3fa85f64-..."` was a `UUID` object or a plain string. The type discriminator
column preserves this information with zero ambiguity.

**Serialization**:
- `UUID` → `external_id = str(value)`, `external_id_type = "uuid"`
- `int` → `external_id = str(value)`, `external_id_type = "int"`
- `str` → `external_id = value`, `external_id_type = "str"`

**Deserialization** (`_deserialize_external_id`):
- `"uuid"` → `UUID(external_id)`
- `"int"` → `int(external_id)`
- `"str"` → `external_id` (identity)

**max_length = 512 rationale**: UUID string = 36 chars; int → up to ~20 digits; str →
`ExternalId` type allows up to 256 chars (see `taxomesh/domain/types.py`). 512 is a safe
upper bound for all three cases.

---

## R-004: Transaction Strategy

**Decision**: Wrap every mutating method in `django.db.transaction.atomic(using=self._using)`.

**Rationale**: Atomicity guarantees all ORM writes within a single repository method either
fully commit or fully roll back. This matches the atomicity guarantee of `JsonRepository`
and `YAMLRepository` (both use `os.replace` for atomic file swap). Using `using=self._using`
ensures multi-database setups are supported correctly.

**Alternatives considered**:
- Per-`save()` atomicity only — insufficient for methods that write multiple related rows
  (e.g., `save_category_parent_link` that performs an upsert).
- No explicit transactions — Django's `ATOMIC_REQUESTS` middleware handles web requests but
  not library-level calls. Rejected.

---

## R-005: Idempotent assign_tag and Upsert Links

**Decision**:
- `assign_tag` → `ItemTagLinkModel.objects.get_or_create(tag_id=tag_id, item_id=item_id)`
- `save_category_parent_link` → `CategoryParentLinkModel.objects.update_or_create(
    category_id=category_id, parent_category_id=parent_category_id,
    defaults={"sort_index": link.sort_index})`
- `save_item_parent_link` → same pattern with `item_id` + `category_id` as lookup keys.

**Rationale**: These semantics are explicitly required by `TaxomeshRepositoryBase` (Protocol
docstrings). `get_or_create` and `update_or_create` are the idiomatic Django ORM patterns for
these operations; they are single-query (SELECT + INSERT or UPDATE) and atomic.

---

## R-006: DatabaseError → TaxomeshRepositoryError Translation

**Decision**: Every mutating method wraps its body in a `try/except django.db.DatabaseError`
block. All caught exceptions are re-raised as `TaxomeshRepositoryError(str(exc)) from exc`.

**Rationale**: Callers of `DjangoRepository` should not need to import `django.db.DatabaseError`
to handle storage errors. Translating to `TaxomeshRepositoryError` keeps the exception hierarchy
(Principle V) intact regardless of backend. The original exception is preserved via chaining
(`from exc`) for debuggability.

---

## R-007: get_config_summary — Safe Output

**Decision**: Return `f"django:{engine_name}/{self._using}"` where `engine_name` is extracted
by splitting `settings.DATABASES[self._using]["ENGINE"]` on `"."` and taking the last component
(e.g. `"django.db.backends.sqlite3"` → `"sqlite3"`).

**Rationale**: `get_config_summary()` is displayed to users via the CLI `--verbose` flag. It
MUST NOT leak credentials. The `ENGINE` value is safe (it is the backend driver name, not a
connection string). Alias (`using`) is safe (it is the `DATABASES` key, not a password).

**Implementation**:
```python
def get_config_summary(self) -> str:
    from django.conf import settings  # noqa: PLC0415
    engine: str = settings.DATABASES[self._using]["ENGINE"].split(".")[-1]
    return f"django:{engine}/{self._using}"
```

---

## R-008: mypy --strict — No django-stubs Required

**Decision**: Do NOT add `django-stubs` or the mypy Django plugin. Exclude
`taxomesh/contrib/django/` from mypy entirely via `pyproject.toml [tool.mypy] exclude`.

**Rationale**: `DjangoRepository` uses deferred imports — no Django symbol is visible to mypy
at module level in `django_repository.py`. The mypy Django plugin is only useful when ORM
model classes are statically visible. Since `contrib/django/` (where the models live) is
excluded from mypy, and the adapter uses no module-level Django imports, `django-stubs` adds
zero type-checking value and significant config complexity.

**mypy config addition** (pyproject.toml):
```toml
[tool.mypy]
exclude = ["taxomesh/contrib/django/"]
```

No `[tool.django-stubs]` section. No plugin entry.

**Alternatives considered**:
- `django-stubs>=5.0` + full strict — rejected in clarification session; excessive noise in
  `contrib/` ORM glue code where stubs are incomplete.
- Per-module `[[tool.mypy.overrides]]` relaxation — rejected; full exclusion is simpler.

---

## R-009: Test Database — SQLite In-Memory

**Decision**: `tests/django_settings.py` configures `DATABASES["default"]` as SQLite
`:memory:`. Each pytest-django test with the `db` fixture gets a fresh transaction.

**Rationale**: In-memory SQLite is the fastest option for unit/integration tests; no file I/O,
no cleanup required. pytest-django's `db` fixture wraps each test in a transaction that is
rolled back after the test — this works with `:memory:` databases.

**Settings file** (`tests/django_settings.py`):
```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
INSTALLED_APPS = [
    "taxomesh.contrib.django",
]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
```

**pytest.ini / pyproject.toml addition**:
```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "tests.django_settings"
```

---

## R-010: Initial Migration Generation

**Decision**: The migration `0001_initial.py` is generated by running
`python manage.py makemigrations taxomesh_contrib_django` inside a minimal Django project
that has `taxomesh.contrib.django` in `INSTALLED_APPS`. The file is committed to source
control. It is never hand-authored.

**Rationale**: Django's migration framework ensures the migration is syntactically valid and
consistent with the model definitions. Hand-authoring risks drift between the ORM models and
the migration.

**Steps to regenerate** (if models change in a future spec):
```bash
# From repo root with dev dependencies installed:
DJANGO_SETTINGS_MODULE=tests.django_settings python -m django makemigrations taxomesh_contrib_django
```

---

## R-011: App Label — `taxomesh_contrib_django`

**Decision**: `AppConfig.label = "taxomesh_contrib_django"` (not `"taxomesh_django"` or
`"django"`).

**Rationale**: The label must be unique across all installed apps. Using the full
`taxomesh_contrib_django` namespace avoids collisions with any existing `django` or
`taxomesh` apps in consumer projects. All six `Meta.app_label` entries reference this constant
via `APP_LABEL: Final[str] = "taxomesh_contrib_django"`.

---

## R-012: on_delete Strategy for FK Relationships

**Decision**: All ForeignKey fields on link models (`CategoryParentLinkModel`,
`ItemParentLinkModel`, `ItemTagLinkModel`) use `on_delete=models.CASCADE`.

**Rationale**: When a `Category`, `Item`, or `Tag` row is deleted, its associated link rows
should also be removed automatically. This matches the semantics of `delete_category`,
`delete_item`, `delete_tag` — callers do not need to manually clean up links. `PROTECT` would
require callers to delete links first, adding burden. `SET_NULL` is not applicable since FKs
are non-nullable.

---

## R-013: TaxomeshService Sort Already Implemented

**Decision**: No changes to `taxomesh/application/service.py` are needed for sort-by-`sort_index`.

**Rationale**: Inspection of `service.py` reveals sorting is already performed:
- `list_categories()` (line 206): `sorted([lnk for lnk in ... if ...], key=lambda lnk: lnk.sort_index)`
- `list_items()` (line 320): same pattern for `ItemParentLink`
- `get_graph()` (lines 524–525, 532–534): sorts both `children_by_parent` buckets and item pairs

FR-020 requires repositories to have no `ORDER BY` — the service already consumes the results
sorted in Python regardless. `DjangoRepository` simply returns `queryset.all()` unordered and
the existing service code sorts correctly.

---

## R-014: domain/constants.py — Exact Values from Codebase Inspection

**Decision**: Create `taxomesh/domain/constants.py` with the following constants, extracted
from reading the actual domain model source files:

```python
MAX_CATEGORY_NAME_LENGTH: Final[int] = 256   # category.py: Annotated[str, Field(max_length=256)]
MAX_TAG_NAME_LENGTH: Final[int] = 25          # tag.py: Annotated[str, Field(max_length=25)]
MAX_DESCRIPTION_LENGTH: Final[int] = 100_000  # category.py: Annotated[str, Field(max_length=100_000)]
MAX_EXTERNAL_ID_STR_LENGTH: Final[int] = 256  # types.py: Annotated[str, Field(max_length=256)]
MAX_EXTERNAL_ID_DB_LENGTH: Final[int] = 512   # new: DB CharField width (covers UUID 36, int ~20, str 256)
MAX_EXTERNAL_ID_TYPE_LENGTH: Final[int] = 8   # new: "uuid"/"int"/"str" discriminator field
```

**Files to update** (replace inline literals with imports):
- `taxomesh/domain/models/category.py` — `MAX_CATEGORY_NAME_LENGTH`, `MAX_DESCRIPTION_LENGTH`
- `taxomesh/domain/models/tag.py` — `MAX_TAG_NAME_LENGTH`
- `taxomesh/domain/types.py` — `MAX_EXTERNAL_ID_STR_LENGTH`
- `taxomesh/contrib/django/models.py` — all six constants

**Note**: `MAX_EXTERNAL_ID_DB_LENGTH` and `MAX_EXTERNAL_ID_TYPE_LENGTH` are new values with
no current domain model counterpart — they belong in `domain/constants.py` since they
represent domain-level storage constraints, not ORM-specific implementation choices.

---

## R-015: get_taxomesh_service_with_django() — Deferred Import Pattern

**Decision**: `taxomesh/contrib/django/__init__.py` exposes the factory function with
`DjangoRepository` imported inside the function body:

```python
def get_taxomesh_service_with_django(
    using: str = DJANGO_REPO_USING_DEFAULT,
) -> "TaxomeshService":
    from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415
    from taxomesh import TaxomeshService  # noqa: PLC0415
    return TaxomeshService(repository=DjangoRepository(using=using))
```

`DJANGO_REPO_USING_DEFAULT` is imported at module level from `taxomesh.contrib.django.models`
(safe — it is a plain `str` constant with no Django dependency).

**Rationale**: `from taxomesh.contrib.django import get_taxomesh_service_with_django` must
succeed without Django installed (SC-003). Deferred imports inside the function body achieve
this. The `TaxomeshService` import is also deferred to avoid any potential circular import
at package init time.
