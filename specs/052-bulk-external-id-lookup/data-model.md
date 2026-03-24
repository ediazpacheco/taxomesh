# Data Model: Bulk Lookup by External ID — Items & Categories (052)

**Branch**: `052-bulk-external-id-lookup`
**Date**: 2026-03-23

No new domain entities or storage schema changes are introduced. This feature adds new
methods to the existing call stack: port → adapters → service. Both item and category
variants follow an identical pattern.

---

## Existing Entities (unchanged)

### `Item` (`taxomesh.domain.models.item.Item`)

Relevant fields:
- `item_id: UUID` — primary key
- `external_id: str | None` — 1:1 unique identifier; `None` when not set
- `enabled: bool` — whether the item is active

### `Category` (`taxomesh.domain.models.category.Category`)

Relevant fields:
- `category_id: UUID` — primary key
- `external_id: str | None` — 1:1 unique identifier; `None` when not set
- `enabled: bool` — whether the category is active
- Root category (`name == ROOT_CATEGORY_NAME`) is always excluded from bulk results.

---

## New Methods: Repository Port

```python
# taxomesh/ports/repository.py — TaxomeshRepositoryBase Protocol

def get_items_by_external_ids(
    self,
    external_ids: Collection[str],
    *,
    enabled: bool | None = None,
) -> dict[str, Item]:
    """Return items whose external_id is in external_ids.

    Input contract (enforced by TaxomeshService before calling):
      - All values are non-empty strings (blanks already removed).
      - No duplicates.

    Args:
        external_ids: Pre-normalized, deduplicated collection of external ID strings.
        enabled: ``True`` returns only enabled items; ``False`` only disabled;
            ``None`` (default) returns all regardless of enabled state.

    Returns:
        A dict mapping each found external_id to its Item. Missing IDs absent.

    Raises:
        TaxomeshRepositoryError: On storage failure.
    """
    ...

def get_categories_by_external_ids(
    self,
    external_ids: Collection[str],
    *,
    enabled: bool | None = None,
) -> dict[str, Category]:
    """Return categories whose external_id is in external_ids.

    Root category filtering is the service layer's responsibility.

    Args:
        external_ids: Pre-normalized, deduplicated collection of external ID strings.
        enabled: ``True`` returns only enabled categories; ``False`` only disabled;
            ``None`` (default) returns all regardless of enabled state.

    Returns:
        A dict mapping each found external_id to its Category. Missing IDs absent.

    Raises:
        TaxomeshRepositoryError: On storage failure.
    """
    ...
```

---

## New Methods: Service Layer

Two methods per entity type are needed: a public normalizer and a private memoized
implementation. `frozenset[str]` is hashable → valid cache key for `@memoize`.

```python
# taxomesh/application/service.py — TaxomeshService

# ---- Items ----

def get_items_by_external_ids(
    self,
    external_ids: Iterable[str],
    *,
    enabled: bool | None = None,
) -> dict[str, Item]:
    """Resolve multiple items by their external_id in a single bulk operation.

    Normalises each input with ``str(value).strip()``, ignores blank values,
    deduplicates into a ``frozenset``, then delegates to the memoized
    implementation. Returns only found items; missing or disabled IDs are
    silently omitted.

    Args:
        external_ids: An iterable of external ID strings. Generators supported.
        enabled: ``True`` returns only enabled items; ``False`` only disabled;
            ``None`` (default) returns all matching items regardless of enabled state.

    Returns:
        A dict mapping each found external_id (after normalisation) to its Item.

    Raises:
        TaxomeshRepositoryError: If the underlying repository raises it.
    """
    normalised = frozenset(str(v).strip() for v in external_ids if str(v).strip())
    if not normalised:
        return {}
    return self._fetch_items_by_external_ids(normalised, enabled=enabled)

@memoize(DEFAULT_CACHE_TTL)
def _fetch_items_by_external_ids(
    self,
    external_ids: frozenset[str],
    *,
    enabled: bool | None = None,
) -> dict[str, Item]:
    """Memoized bulk repository call. frozenset arg → hashable cache key."""
    return self._repo.get_items_by_external_ids(external_ids, enabled=enabled)

# ---- Categories ----

def get_categories_by_external_ids(
    self,
    external_ids: Iterable[str],
    *,
    enabled: bool | None = None,
) -> dict[str, Category]:
    """Resolve multiple categories by their external_id in a single bulk operation.

    Normalises input, deduplicates, delegates to the memoized implementation.
    The root category is always excluded from results, even if its external_id
    is supplied. Missing or disabled IDs are silently omitted.

    Args:
        external_ids: An iterable of external ID strings. Generators supported.
        enabled: ``True`` returns only enabled categories; ``False`` only disabled;
            ``None`` (default) returns all matching categories regardless of enabled state.

    Returns:
        A dict mapping each found external_id (after normalisation) to its Category.

    Raises:
        TaxomeshRepositoryError: If the underlying repository raises it.
    """
    normalised = frozenset(str(v).strip() for v in external_ids if str(v).strip())
    if not normalised:
        return {}
    result = self._fetch_categories_by_external_ids(normalised, enabled=enabled)
    # Exclude root category (mirrors get_category_by_external_id behaviour)
    return {k: v for k, v in result.items() if v.category_id != self._root_id}

@memoize(DEFAULT_CACHE_TTL)
def _fetch_categories_by_external_ids(
    self,
    external_ids: frozenset[str],
    *,
    enabled: bool | None = None,
) -> dict[str, Category]:
    """Memoized bulk repository call. frozenset arg → hashable cache key."""
    return self._repo.get_categories_by_external_ids(external_ids, enabled=enabled)
```

---

## Adapter Implementations (no new storage)

### `JsonRepository` / `YAMLRepository`

Single O(n) scan over the in-memory store:

```python
def get_items_by_external_ids(
    self,
    external_ids: Collection[str],
    *,
    enabled: bool | None = None,
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
    self,
    external_ids: Collection[str],
    *,
    enabled: bool | None = None,
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

### `DjangoRepository`

Single ORM query per entity type:

```python
def get_items_by_external_ids(
    self,
    external_ids: Collection[str],
    *,
    enabled: bool | None = None,
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
    self,
    external_ids: Collection[str],
    *,
    enabled: bool | None = None,
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

---

## Call Flow

```
TaxomeshService.get_items_by_external_ids(external_ids, *, enabled)
  │  normalise → frozenset[str]
  └─ _fetch_items_by_external_ids(frozenset, enabled=enabled)  [@memoize]
       └─ self._repo.get_items_by_external_ids(frozenset, enabled=enabled)
            ├─ JsonRepository  → O(n) scan, set-membership test
            ├─ YAMLRepository  → O(n) scan, set-membership test
            └─ DjangoRepository → single SQL WHERE external_id IN (...) [+ enabled]

TaxomeshService.get_categories_by_external_ids(external_ids, *, enabled)
  │  normalise → frozenset[str]
  ├─ _fetch_categories_by_external_ids(frozenset, enabled=enabled)  [@memoize]
  │    └─ self._repo.get_categories_by_external_ids(frozenset, enabled=enabled)
  │         ├─ JsonRepository  → O(n) scan, set-membership test
  │         ├─ YAMLRepository  → O(n) scan, set-membership test
  │         └─ DjangoRepository → single SQL WHERE external_id IN (...) [+ enabled]
  └─ post-filter: exclude root category (category_id == self._root_id)
```

---

## Index Coverage

No new migration required. Both `taxomesh_item.external_id` and
`taxomesh_category.external_id` already have database indexes (migration 0004,
spec 032-external-id-index).
