# Implementation Plan: Bulk Lookup by External ID (Items & Categories)

**Branch**: `052-bulk-external-id-lookup` | **Date**: 2026-03-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/052-bulk-external-id-lookup/spec.md`

## Summary

Add `get_items_by_external_ids` and `get_categories_by_external_ids` to the service layer
and all repository adapters. Both methods accept an `Iterable[str]`, normalise and
deduplicate input, then delegate to a single bulk query in each adapter. Eliminates the
N+1 pattern caused by per-entity `get_item_by_external_id` / `get_category_by_external_id`
loops in downstream consumers. Both methods use a two-method pattern (public normalizer +
private `@memoize`d implementation) for TTL caching with hashable `frozenset[str]` keys.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Pydantic v2 (domain models), stdlib `collections.abc`
**Storage**: JSON file (`JsonRepository`), YAML file (`YAMLRepository`), Django ORM (`DjangoRepository`)
**Testing**: pytest, pytest-cov, pytest-django (Django tests)
**Target Platform**: Library — consumed by web applications and CLI tools
**Project Type**: Python library
**Performance Goals**: Single data-store query per bulk call regardless of input size
**Constraints**: mypy `--strict` compliance; ruff linting + formatting; ≥ 80% test coverage
**Scale/Scope**: Designed for O(100s) of IDs per call; no pagination required

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Hexagonal Architecture | ✅ PASS | Port → adapters → service; no layer violations |
| II. TaxomeshService is single facade | ✅ PASS | All new methods on `TaxomeshService` only |
| III. Repository as Protocol | ✅ PASS | New methods added to `TaxomeshRepositoryBase` Protocol |
| IV. Pydantic + mypy strict | ✅ PASS | Returns typed dicts; no `Any`; all annotations explicit |
| V. Custom exception hierarchy | ✅ PASS | No new exceptions; `TaxomeshRepositoryError` re-raised from Django adapter |
| VI. DAG integrity | ✅ N/A | Read-only feature; no writes |
| VII. Spec-driven development | ✅ PASS | Spec 052 exists |
| VIII. Quality gates | ✅ PASS | Will be verified before PR |
| IX. Framework-agnostic handlers | ✅ N/A | No `contrib.api` handler in scope |
| X. Named constants | ✅ PASS | No new magic literals introduced |
| XI. Object-oriented by default | ✅ PASS | Methods added to existing class hierarchy; private helpers are instance methods |

No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/052-bulk-external-id-lookup/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   └── service-api.md   ← Phase 1 output
└── tasks.md             ← Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code Changes

```text
taxomesh/
├── ports/
│   └── repository.py               ← add get_items_by_external_ids + get_categories_by_external_ids
├── adapters/repositories/
│   ├── json_repository.py          ← implement both bulk methods
│   ├── yaml_repository.py          ← implement both bulk methods
│   └── django_repository.py        ← implement both bulk methods
└── application/
    └── service.py                  ← add 4 methods: 2 public + 2 private memoized

tests/
├── adapters/repositories/
│   ├── test_json_repository_bulk_external_id.py   ← new (items + categories)
│   └── test_yaml_repository_bulk_external_id.py   ← new (items + categories)
├── contrib/django/
│   └── test_django_bulk_external_id.py            ← new (items + categories)
└── service/
    └── test_service_bulk_external_id.py           ← new (items + categories)
```

**Structure Decision**: Standard single-library layout. All changes are additions to
existing modules. No new modules or packages required.

## Phase 0: Research

Research is complete. See [research.md](research.md) for all decisions.

Key findings:
- No open unknowns; all decisions derived from existing codebase patterns.
- `enabled` filtering delegated to adapters (consistent with `list_items()` pattern).
- Port accepts `Collection[str]` (pre-normalised by service); service accepts `Iterable[str]`.
- Two-method pattern per entity: public normalizer delegates to `@memoize`d private method
  receiving `frozenset[str]` (hashable → valid cache key).
- Root category exclusion for `get_categories_by_external_ids` handled in the service
  (post-filter on `category_id == self._root_id`), not in adapters.
- No new migration (external_id already indexed via migration 0004).
- No `contrib.api` handler in scope.

## Phase 1: Design

### Method Signatures

**Repository port** (`taxomesh/ports/repository.py`) — two new methods:
```python
def get_items_by_external_ids(
    self,
    external_ids: Collection[str],
    *,
    enabled: bool | None = None,
) -> dict[str, Item]: ...

def get_categories_by_external_ids(
    self,
    external_ids: Collection[str],
    *,
    enabled: bool | None = None,
) -> dict[str, Category]: ...
```

**Service** (`taxomesh/application/service.py`) — four methods (2 public + 2 private):
```python
# --- Items ---
def get_items_by_external_ids(
    self, external_ids: Iterable[str], *, enabled: bool | None = None,
) -> dict[str, Item]:
    normalised = frozenset(str(v).strip() for v in external_ids if str(v).strip())
    if not normalised:
        return {}
    return self._fetch_items_by_external_ids(normalised, enabled=enabled)

@memoize(DEFAULT_CACHE_TTL)
def _fetch_items_by_external_ids(
    self, external_ids: frozenset[str], *, enabled: bool | None = None,
) -> dict[str, Item]:
    return self._repo.get_items_by_external_ids(external_ids, enabled=enabled)

# --- Categories ---
def get_categories_by_external_ids(
    self, external_ids: Iterable[str], *, enabled: bool | None = None,
) -> dict[str, Category]:
    normalised = frozenset(str(v).strip() for v in external_ids if str(v).strip())
    if not normalised:
        return {}
    result = self._fetch_categories_by_external_ids(normalised, enabled=enabled)
    return {k: v for k, v in result.items() if v.category_id != self._root_id}

@memoize(DEFAULT_CACHE_TTL)
def _fetch_categories_by_external_ids(
    self, external_ids: frozenset[str], *, enabled: bool | None = None,
) -> dict[str, Category]:
    return self._repo.get_categories_by_external_ids(external_ids, enabled=enabled)
```

**JsonRepository / YAMLRepository** (identical implementation per entity):
```python
def get_items_by_external_ids(
    self, external_ids: Collection[str], *, enabled: bool | None = None,
) -> dict[str, Item]:
    target = set(external_ids)
    result: dict[str, Item] = {}
    for item in self._items.values():
        if item.external_id in target:
            if enabled is None or item.enabled == enabled:
                assert item.external_id is not None
                result[item.external_id] = item
    return result

def get_categories_by_external_ids(
    self, external_ids: Collection[str], *, enabled: bool | None = None,
) -> dict[str, Category]:
    target = set(external_ids)
    result: dict[str, Category] = {}
    for cat in self._categories.values():
        if cat.external_id in target:
            if enabled is None or cat.enabled == enabled:
                assert cat.external_id is not None
                result[cat.external_id] = cat
    return result
```

**DjangoRepository**:
```python
def get_items_by_external_ids(
    self, external_ids: Collection[str], *, enabled: bool | None = None,
) -> dict[str, Item]:
    from django.db import DatabaseError  # noqa: PLC0415
    from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415
    try:
        qs = self._ItemModel.objects.using(self._using).filter(external_id__in=external_ids)
        if enabled is not None:
            qs = qs.filter(enabled=enabled)
        return {row.external_id: self._row_to_item(row) for row in qs if row.external_id}
    except DatabaseError as exc:
        raise TaxomeshRepositoryError(str(exc)) from exc

def get_categories_by_external_ids(
    self, external_ids: Collection[str], *, enabled: bool | None = None,
) -> dict[str, Category]:
    from django.db import DatabaseError  # noqa: PLC0415
    from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415
    try:
        qs = self._CategoryModel.objects.using(self._using).filter(external_id__in=external_ids)
        if enabled is not None:
            qs = qs.filter(enabled=enabled)
        return {row.external_id: self._row_to_category(row) for row in qs if row.external_id}
    except DatabaseError as exc:
        raise TaxomeshRepositoryError(str(exc)) from exc
```

### Test Plan (TDD — tests written before implementation)

**`test_json_repository_bulk_external_id.py`** and **`test_yaml_repository_bulk_external_id.py`**
(mirrored for both adapters; each file covers both item and category variants):
- `test_items_all_ids_found` / `test_categories_all_ids_found`
- `test_items_some_ids_missing` / `test_categories_some_ids_missing`
- `test_items_all_ids_missing` / `test_categories_all_ids_missing`
- `test_items_duplicate_ids` / `test_categories_duplicate_ids`
- `test_items_blank_ids_ignored` / `test_categories_blank_ids_ignored`
- `test_items_enabled_true` / `test_categories_enabled_true`
- `test_items_enabled_false` / `test_categories_enabled_false`
- `test_items_enabled_none` / `test_categories_enabled_none`

**`test_service_bulk_external_id.py`** (items and categories):
- `test_items_normalisation_strips_whitespace`
- `test_items_normalisation_skips_blank`
- `test_items_deduplication`
- `test_items_enabled_filter_true` / `_false` / `_none`
- `test_items_missing_ids_no_exception`
- `test_items_generator_input`
- `test_categories_root_excluded`
- `test_categories_root_excluded_when_only_id`
- `test_categories_enabled_filter`
- `test_categories_missing_ids_no_exception`

**`test_django_bulk_external_id.py`** (`@pytest.mark.django_db`, items and categories):
- `test_items_bulk_lookup_found`
- `test_items_bulk_lookup_missing`
- `test_items_bulk_lookup_enabled_filter`
- `test_items_bulk_lookup_empty_input`
- `test_items_database_error_raises_repository_error`
- `test_categories_bulk_lookup_found`
- `test_categories_bulk_lookup_missing`
- `test_categories_bulk_lookup_enabled_filter`
- `test_categories_database_error_raises_repository_error`
