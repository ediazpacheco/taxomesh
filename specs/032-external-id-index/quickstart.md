# Quickstart: External-ID Lookups

**Feature**: 032-external-id-index
**Audience**: Developers integrating taxomesh into applications that use `external_id` as
a bridge between their own entity identifiers and taxomesh internals.

---

## Use the dedicated lookup methods

Resolve items or categories by `external_id` using the service methods:

```python
from taxomesh import TaxomeshService

service = TaxomeshService()

# Look up items by external_id
items = service.get_items_by_external_id("catalog:42")

# Look up categories by external_id
categories = service.get_categories_by_external_id("ext-dept-7")
```

Both methods return a `list`. Interpret the result by length:

```python
if len(items) == 0:
    # No item registered with this external_id (orphan)
elif len(items) == 1:
    item = items[0]  # Unique match — normal case
else:
    # Duplicates exist — handle per your application policy
```

---

## What NOT to do

```python
# ❌ Do NOT use list_items() and filter in Python
item = next((i for i in service.list_items() if i.external_id == "catalog:42"), None)
```

`list_items()` and `list_categories()` load the entire table into memory. When using the
Django backend, `external_id` is indexed — the dedicated lookup methods use a filtered ORM
query that hits only matching rows. Always prefer the dedicated methods for point lookups.

---

## external_id semantics

- `external_id` is **indexed** in the Django backend (as of migration `0004`).
- `external_id` is **not unique** — multiple items/categories may share the same value.
- `external_id` may be **blank** (`""`). A blank `external_id` is a valid filter value.
- Integers and UUIDs passed as `external_id` are coerced to their string representation
  at storage time (`42` → `"42"`, `UUID("…")` → `"…"`).
