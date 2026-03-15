# Data Model: External-ID Database Indexes

**Feature**: 032-external-id-index
**Date**: 2026-03-14

## Entities Affected

This feature adds no new entities and removes no entities. Two existing Django ORM model
fields gain a database index.

---

### CategoryModel.external_id

**Current state**:

```
CharField(max_length=MAX_EXTERNAL_ID_STR_LENGTH, blank=True, default=DEFAULT_CATEGORY_EXTERNAL_ID)
```

**After this feature**:

```
CharField(max_length=MAX_EXTERNAL_ID_STR_LENGTH, blank=True, default=DEFAULT_CATEGORY_EXTERNAL_ID, db_index=True)
```

**Constraints**:
- Non-unique — duplicate values are valid and expected
- Blank-allowed — `""` is a valid `external_id`
- Max length: `MAX_EXTERNAL_ID_STR_LENGTH` (unchanged)

---

### ItemModel.external_id

**Current state**:

```
CharField(max_length=MAX_EXTERNAL_ID_STR_LENGTH, blank=True, default=DEFAULT_ITEM_EXTERNAL_ID)
```

**After this feature**:

```
CharField(max_length=MAX_EXTERNAL_ID_STR_LENGTH, blank=True, default=DEFAULT_ITEM_EXTERNAL_ID, db_index=True)
```

**Constraints**:
- Non-unique — duplicate values are valid and expected
- Blank-allowed — `""` is a valid `external_id`
- Max length: `MAX_EXTERNAL_ID_STR_LENGTH` (unchanged)

---

## Migration

**File**: `taxomesh/contrib/django/migrations/0004_external_id_indexes.py`

**Type**: Additive schema migration (index creation only)

**Dependencies**: `("taxomesh_contrib_django", "0003_item_relation_link")`

**Operations**:

1. `AlterField` — `CategoryModel.external_id` with `db_index=True`
2. `AlterField` — `ItemModel.external_id` with `db_index=True`

**Data changes**: None. No rows are modified. No uniqueness constraint is added. Existing
duplicate or blank `external_id` values remain valid.

**Backward compatibility**: The index can be dropped without data loss if the migration is
reversed. No application code depends on the index being present at the Python level.
