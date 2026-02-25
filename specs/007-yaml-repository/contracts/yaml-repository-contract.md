# Contract: YAMLRepository

**Type**: Repository adapter (implements `TaxomeshRepositoryBase`)
**File**: `taxomesh/adapters/repositories/yaml_repository.py`
**Date**: 2026-02-24

---

## Constructor

```python
YAMLRepository(path: Path | str = Path("taxomesh.yaml")) -> None
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `Path \| str` | `Path("taxomesh.yaml")` | Path to the YAML storage file |

**Behaviour on init**:
- If `path` is an existing directory → raise `TaxomeshRepositoryError`
- If `path` does not exist → create parent dirs (if needed) + write empty YAML file
- If `path` exists and is valid YAML → load all collections into memory
- If `path` exists and is invalid YAML → raise `TaxomeshRepositoryError`

---

## Implemented Methods (full TaxomeshRepositoryBase protocol)

All methods below mirror `JsonRepository` semantics exactly:

### Category

| Method | Signature | Returns | Raises |
|--------|-----------|---------|--------|
| `save_category` | `(category: Category) -> None` | — | `TaxomeshRepositoryError` on write failure |
| `get_category` | `(category_id: UUID) -> Category \| None` | `Category` or `None` | — |
| `list_categories` | `() -> list[Category]` | All stored categories | — |
| `delete_category` | `(category_id: UUID) -> bool` | `True` if deleted | — |

### Item

| Method | Signature | Returns | Raises |
|--------|-----------|---------|--------|
| `save_item` | `(item: Item) -> None` | — | `TaxomeshRepositoryError` on write failure |
| `get_item` | `(item_id: UUID) -> Item \| None` | `Item` or `None` | — |
| `list_items` | `() -> list[Item]` | All stored items | — |
| `delete_item` | `(item_id: UUID) -> bool` | `True` if deleted | — |

### Tag

| Method | Signature | Returns | Raises |
|--------|-----------|---------|--------|
| `save_tag` | `(tag: Tag) -> None` | — | `TaxomeshRepositoryError` on write failure |
| `get_tag` | `(tag_id: UUID) -> Tag \| None` | `Tag` or `None` | — |
| `list_tags` | `() -> list[Tag]` | All stored tags | — |
| `delete_tag` | `(tag_id: UUID) -> bool` | `True` if deleted | — |

### Associations

| Method | Signature | Returns | Raises |
|--------|-----------|---------|--------|
| `assign_tag` | `(tag_id: UUID, item_id: UUID) -> None` | — | — |
| `remove_tag` | `(tag_id: UUID, item_id: UUID) -> bool` | `True` if removed | — |
| `save_category_parent_link` | `(link: CategoryParentLink) -> None` | — | — |
| `list_category_parent_links` | `() -> list[CategoryParentLink]` | All links | — |
| `save_item_parent_link` | `(link: ItemParentLink) -> None` | — | — |
| `list_item_parent_links` | `() -> list[ItemParentLink]` | All links | — |

### Configuration

| Method | Signature | Returns | Contract |
|--------|-----------|---------|---------|
| `get_config_summary` | `() -> str` | Non-empty string | Always returns the configured file path string; never raises; never empty |

---

## Invariants

1. Every mutating method (`save_*`, `delete_*`, `assign_*`, `remove_*`) calls `_flush()` after modifying in-memory state.
2. `_flush()` writes atomically: `tempfile.mkstemp` → `os.fsync` → `os.replace`.
3. `save_item_parent_link` is an upsert: if a link with the same `(item_id, category_id)` exists, its `sort_index` is updated in-place. No duplicate is created.
4. `assign_tag` is idempotent: if `(tag_id, item_id)` already linked, no-op.
5. The YAML file always contains all six top-level keys, even when empty.
