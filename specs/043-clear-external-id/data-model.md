# Data Model: External ID Clear Support (043)

**Branch**: `043-clear-external-id` | **Date**: 2026-03-21

---

## Existing Entities (unchanged)

### Item
**File**: `taxomesh/domain/models/item.py`

| Field | Type | Constraint | Notes |
|-------|------|------------|-------|
| `item_id` | `UUID` | required | library-assigned |
| `name` | `str` | max 256 chars | |
| `external_id` | `str \| None` | max 256 chars, unique | `None` = no external link |
| `slug` | `str` | max 256 chars | `""` = no slug |
| `enabled` | `bool` | | |
| `metadata` | `dict[str, Any]` | | |

**No changes to this model.**

### Category
**File**: `taxomesh/domain/models/category.py`

| Field | Type | Constraint | Notes |
|-------|------|------------|-------|
| `category_id` | `UUID` | required | library-assigned |
| `name` | `str` | max 256 chars | required |
| `description` | `str` | max 100 000 chars | |
| `enabled` | `bool` | | |
| `external_id` | `str \| None` | max 256 chars, unique | `None` = no external link |
| `slug` | `str` | max 256 chars | `""` = no slug |
| `metadata` | `dict[str, Any]` | | |

**No changes to this model.**

---

## New Application-Layer Construct

### `_UnsetType` sentinel class
**File**: `taxomesh/application/service.py` (private, module-level)

A private singleton class used exclusively as a typed sentinel for the `external_id` parameter in `update_item` and `update_category`. It represents "caller did not supply a value — do not modify the field."

**Not a domain entity.** It lives entirely in the application layer and is never stored, serialised, or passed to any repository.

| Attribute | Value |
|-----------|-------|
| Scope | Private to `service.py` (`_UnsetType`, `_UNSET`) |
| Exported | No |
| Stored | No |
| Type annotation | `_UnsetType` |
| Instance | `_UNSET: Final[_UnsetType] = _UnsetType()` |

---

## State Transitions for `external_id`

```
  external_id = None          external_id = "some-string"
        │                               │
        │   update(..., external_id="x")│   update(..., external_id=None)
        └───────────────────────────────┘
                      │
        ┌─────────────┼──────────────────────┐
        │             │                      │
  external_id     external_id          no change
  = "x"           = None             (omit arg)
  (assign)        (clear)            (no-op)
```

**Uniqueness rule**: At most one record (item or category) may hold any given non-`None` external_id string at a time. Multiple records may simultaneously hold `external_id = None`.

---

## Persistence Compatibility

| Backend | `None` serialised as | Unique null handling |
|---------|---------------------|----------------------|
| JsonRepository | JSON `null` | Multiple nulls allowed (in-process check skips None) |
| YAMLRepository | YAML `null` | Multiple nulls allowed (same check) |
| DjangoRepository | SQL `NULL` | Multiple nulls allowed (SQL standard for UNIQUE) |

No schema changes required.
