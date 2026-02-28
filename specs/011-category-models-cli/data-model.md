# Data Model: Category Fields, Models Refactor, CLI Output & Service Cache

**Feature**: 011-category-models-cli
**Date**: 2026-02-27

## Entity Changes

### Category (modified)

| Field | Type | Default | Change |
|-------|------|---------|--------|
| category_id | UUID | (required) | Unchanged |
| name | Annotated[str, Field(max_length=256)] | (required) | Unchanged |
| description | Annotated[str, Field(max_length=100_000)] | `""` | Unchanged |
| metadata | dict[str, Any] | `{}` | Unchanged |
| **enabled** | **bool** | **True** | **NEW** |
| **external_id** | **ExternalId** | **""** | **NEW** |

**Notes**:
- `enabled` mirrors `Item.enabled` — same type, same default.
- `external_id` uses the existing `ExternalId` type alias (`UUID | Annotated[str, Field(max_length=256)] | int`). Defaults to `""` (empty string), unlike `Item.external_id` which is required.
- Backward compatibility: Pydantic's defaults handle deserialization of stores that lack these fields.

### Item (unchanged)

No changes. Already has `enabled` and `external_id`.

### ModelBase, Tag, CategoryParentLink, ItemParentLink, ItemTagLink (unchanged)

No field changes. Each moves to its own module under `models/`.

## Package Structure Change

**Before**: `taxomesh/domain/models.py` (single file, 51 lines)

**After**: `taxomesh/domain/models/` (package)

| Module | Contains | Imports from |
|--------|----------|-------------|
| `__init__.py` | Re-exports all public names | All sibling modules |
| `base.py` | `ModelBase` | `pydantic` |
| `item.py` | `Item` | `base.py`, `types.py` |
| `category.py` | `Category` | `base.py`, `types.py` |
| `tag.py` | `Tag` | `base.py` |
| `category_parent_link.py` | `CategoryParentLink` | `base.py` |
| `item_parent_link.py` | `ItemParentLink` | `base.py` |
| `item_tag_link.py` | `ItemTagLink` | `base.py` |

## New Package: `taxomesh/utils/`

| Module | Contains | Description |
|--------|----------|-------------|
| `__init__.py` | (empty or re-exports) | Package marker |
| `memoize.py` | `memoize(ttl)`, `clear_all_caches()` | Closure-based decorator with TTL cache + global cache registry |

### `memoize` Decorator Signature

```python
def memoize(ttl: float) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Cache function results for `ttl` seconds.

    Args:
        ttl: Time-to-live in seconds for cached entries.

    Returns:
        A decorator that wraps the target function with TTL-based caching.
    """
```

### `clear_all_caches` Signature

```python
def clear_all_caches() -> None:
    """Clear every cache registered by @memoize decorators."""
```

**Cache storage**: `dict[tuple[Any, ...], tuple[T, float]]` — maps `(args_key)` → `(result, timestamp)`.

**Cache key construction**: `(args, tuple(sorted(kwargs.items())))`. If `TypeError` (unhashable), skip caching.

**Clock**: `time.monotonic()` — immune to system clock adjustments.

**Cache registry**: Module-level `_cache_registry: list[Callable[[], None]]` — each `@memoize`-decorated function registers its `clear_cache` callable. `clear_all_caches()` iterates and calls each.

**Per-function clear**: Each wrapped function gets a `clear_cache` attribute for targeted clearing (used internally; `clear_all_caches()` is the public API for service invalidation).

## Service Constants

| Constant | Type | Value | Location |
|----------|------|-------|----------|
| `DEFAULT_CACHE_TTL` | `Final[int]` | `5` | `taxomesh/application/service.py` |

## Service Cache Invalidation

Write methods that call `clear_all_caches()` after successful write (13 total):

| Method | Entity |
|--------|--------|
| `create_category` | Category |
| `update_category` | Category |
| `delete_category` | Category |
| `create_item` | Item |
| `update_item` | Item |
| `delete_item` | Item |
| `create_tag` | Tag |
| `update_tag` | Tag |
| `delete_tag` | Tag |
| `assign_tag` | Tag-Item link |
| `remove_tag` | Tag-Item link |
| `add_category_parent` | Category-Parent link |
| `place_item_in_category` | Item-Category link |

## Serialization Impact

Both `JsonRepository` and `YAMLRepository` serialize Category objects using Pydantic's `model_dump()` / `model_validate()`. The new fields with defaults will:
- **Write**: Include `enabled` and `external_id` in serialized output.
- **Read (new data)**: Parse both fields.
- **Read (legacy data)**: Missing fields default to `True` and `""` respectively via Pydantic model defaults.

No migration or schema versioning needed.
