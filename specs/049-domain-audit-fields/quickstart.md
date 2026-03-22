# Quickstart: Domain Audit Fields (049)

## What changes

After this feature, every `Category` and `Item` carries three new read-only audit fields:

- `created_at` — UTC datetime of first creation
- `updated_at` — UTC datetime of most recent field update
- `version` — integer counter, starts at `0`, incremented on each update

These fields are set automatically by `TaxomeshService`. No caller changes are required.

---

## Reading audit fields

```python
from taxomesh import TaxomeshService

service = TaxomeshService()

# Create
category = service.create_category("Electronics")
print(category.created_at)   # e.g. 2026-03-22 10:00:00+00:00
print(category.updated_at)   # same as created_at
print(category.version)      # 0

# Update
category = service.update_category(category.category_id, name="Consumer Electronics")
print(category.updated_at)   # now later than created_at
print(category.version)      # 1

# created_at never changes
category = service.update_category(category.category_id, description="All consumer electronics")
print(category.version)      # 2
# category.created_at is still the original creation timestamp
```

---

## Detecting changes between reads

```python
v1 = service.get_category(cat_id)
# ... time passes, some other process may update the category ...
v2 = service.get_category(cat_id)

if v2.version != v1.version:
    print("Category has been modified since last read")
```

---

## Legacy data

Existing storage files (JSON/YAML) and Django database rows that pre-date this feature
load without error. Missing audit fields are filled with safe defaults:

- `created_at` = `1970-01-01T00:00:00+00:00` (Unix epoch — detectable as "legacy")
- `updated_at` = `1970-01-01T00:00:00+00:00`
- `version` = `0`

---

## Structural operations do not bump version

Operations that change structure only (adding parent categories, assigning tags, placing
items in categories) do **not** change `version` or `updated_at`:

```python
item = service.create_item("Laptop")
print(item.version)    # 0

service.assign_category(item.item_id, cat_id)   # structural — no audit bump
item = service.get_item(item.item_id)
print(item.version)    # still 0

item = service.update_item(item.item_id, name="Laptop Pro")  # field update — bumps
print(item.version)    # 1
```
