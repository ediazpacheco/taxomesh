# Contract: Repository Port — `list_categories` / `list_items`

**Feature**: `046-repo-enabled-filter`

## Protocol Method: `list_categories`

```python
def list_categories(self, *, enabled: bool | None = True) -> list[Category]: ...
```

### Contract

- When `enabled=True` (default): returns only categories where `Category.enabled is True`.
- When `enabled=False`: returns only categories where `Category.enabled is False`.
- When `enabled=None`: returns all categories regardless of enabled state.
- The implicit root category (identified by `Category.name == ROOT_CATEGORY_NAME`) MUST
  be excluded from results regardless of the `enabled` value. This is unchanged behaviour.
- Results are ordered `(name ASC, category_id ASC)` — unchanged.
- Returns an empty list when no records match; never raises on empty results.

### Adapter implementation notes

| Adapter | Implementation approach |
|---------|------------------------|
| `JsonRepository` | Python `if` on loaded dict values before building the return list |
| `YAMLRepository` | Python `if` on loaded dict values before building the return list |
| `DjangoRepository` | `.filter(enabled=enabled)` when `enabled is not None`; no filter clause when `enabled is None` |
| `InMemoryRepository` (test fixture) | Python `if` on in-memory dict values |

---

## Protocol Method: `list_items`

```python
def list_items(self, *, enabled: bool | None = True) -> list[Item]: ...
```

### Contract

- When `enabled=True` (default): returns only items where `Item.enabled is True`.
- When `enabled=False`: returns only items where `Item.enabled is False`.
- When `enabled=None`: returns all items regardless of enabled state.
- Results are ordered `(name ASC, item_id ASC)` — unchanged.
- Returns an empty list when no records match; never raises on empty results.

### Adapter implementation notes

Same pattern as `list_categories` above.
