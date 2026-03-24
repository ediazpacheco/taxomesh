# Contract: Bulk Lookup by External ID

**Feature**: 052-bulk-external-id-lookup
**Layer**: Public service API (`taxomesh.application.service.TaxomeshService`)
**Type**: Python method contract

---

## `get_items_by_external_ids`

### Signature

```python
def get_items_by_external_ids(
    self,
    external_ids: Iterable[str],
    *,
    enabled: bool | None = None,
) -> dict[str, Item]:
```

### Parameters

| Parameter      | Type           | Default | Description |
|----------------|----------------|---------|-------------|
| `external_ids` | `Iterable[str]`| —       | Any iterable of external ID strings. Generators supported. |
| `enabled`      | `bool \| None` | `None`  | `True` = enabled only; `False` = disabled only; `None` = all. |

### Return Value

`dict[str, Item]` — maps each **normalised** external ID to its matching `Item`.
Only IDs that exist (and pass the enabled filter) appear as keys. Empty dict when nothing matches.

### Behaviour

| Condition | Result |
|-----------|--------|
| ID not found in repository | Silently omitted; no exception |
| ID found but item is disabled, `enabled=None` | Included in result |
| ID found but item is disabled, `enabled=True` | Excluded (silently omitted) |
| Blank / whitespace-only ID | Stripped and ignored; never in result |
| Duplicate IDs | Deduplicated; at most one entry per ID |
| Empty input | Empty dict returned immediately |
| All IDs missing | Empty dict; no exception |

### Exceptions

| Exception | Condition |
|-----------|-----------|
| `TaxomeshRepositoryError` | Storage failure in the underlying repository |

Does **not** raise `TaxomeshItemNotFoundError` for missing IDs.

### Examples

```python
# All found
result = service.get_items_by_external_ids(["author-1", "author-2"])
# → {"author-1": Item(...), "author-2": Item(...)}

# Missing IDs silently omitted
result = service.get_items_by_external_ids(["exists", "no-such-id"])
# → {"exists": Item(...)}

# Disabled items excluded when enabled=True
result = service.get_items_by_external_ids(["a", "b"], enabled=True)
# → only enabled items among a, b

# Disabled items returned when enabled=None (default)
result = service.get_items_by_external_ids(["a", "b"])  # enabled=None
# → both a and b if they exist, regardless of enabled state

# Blank IDs ignored
result = service.get_items_by_external_ids(["valid", "  ", ""])
# → {"valid": Item(...)} if "valid" exists
```

---

## `get_categories_by_external_ids`

### Signature

```python
def get_categories_by_external_ids(
    self,
    external_ids: Iterable[str],
    *,
    enabled: bool | None = None,
) -> dict[str, Category]:
```

### Parameters

| Parameter      | Type           | Default | Description |
|----------------|----------------|---------|-------------|
| `external_ids` | `Iterable[str]`| —       | Any iterable of external ID strings. Generators supported. |
| `enabled`      | `bool \| None` | `None`  | `True` = enabled only; `False` = disabled only; `None` = all. |

### Return Value

`dict[str, Category]` — maps each **normalised** external ID to its matching `Category`.
The root category is **always excluded** even if its external_id is supplied.

### Behaviour

| Condition | Result |
|-----------|--------|
| ID not found | Silently omitted; no exception |
| ID maps to root category | Excluded (root is never returned) |
| ID found but category disabled, `enabled=None` | Included in result |
| ID found but category disabled, `enabled=True` | Excluded (silently omitted) |
| Blank / whitespace-only ID | Ignored; never in result |
| Duplicate IDs | Deduplicated |
| Empty input | Empty dict returned immediately |

### Exceptions

| Exception | Condition |
|-----------|-----------|
| `TaxomeshRepositoryError` | Storage failure in the underlying repository |

Does **not** raise `TaxomeshCategoryNotFoundError` for missing IDs.

### Examples

```python
# All found
result = service.get_categories_by_external_ids(["cat-1", "cat-2"])
# → {"cat-1": Category(...), "cat-2": Category(...)}

# Root category always excluded
result = service.get_categories_by_external_ids([root_external_id, "cat-1"])
# → {"cat-1": Category(...)}  — root absent

# enabled filtering works the same as items
result = service.get_categories_by_external_ids(["cat-1", "cat-2"], enabled=True)
# → only enabled categories
```

---

## Repository Port Contracts

All repository adapters must implement both port methods:

```python
# TaxomeshRepositoryBase (taxomesh.ports.repository)

def get_items_by_external_ids(
    self,
    external_ids: Collection[str],   # pre-normalized, deduplicated
    *,
    enabled: bool | None = None,
) -> dict[str, Item]: ...

def get_categories_by_external_ids(
    self,
    external_ids: Collection[str],   # pre-normalized, deduplicated
    *,
    enabled: bool | None = None,
) -> dict[str, Category]: ...        # root category NOT excluded here; service handles it
```

Note: root category exclusion is the **service's** responsibility, not the adapter's.
Adapters return whatever the store contains for the given external IDs.
