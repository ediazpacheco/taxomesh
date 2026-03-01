# Data Model: External-ID Lookup & Assignable Categories (013)

## Summary

No new entities or schema changes are introduced. This feature extends the *behaviour* of
existing entities and the protocol interface. All data model changes are additive method
signatures on existing classes.

---

## Modified Protocol: TaxomeshRepositoryBase

**File**: `taxomesh/ports/repository.py`

Two new method signatures added to the structural protocol:

```
list_items_by_external_id(external_id: ExternalId) -> list[Item]
list_categories_by_external_id(external_id: ExternalId) -> list[Category]
```

**Semantics**:
- Exact-type match: `ExternalId = UUID | int | str`; type is compared as-is (no coercion).
- Returns empty list when no entity matches.
- Returns N > 1 items when multiple entities share the same `external_id`.

---

## ExternalId Type

**Definition**: `taxomesh/domain/types.py`

```
ExternalId: TypeAlias = UUID | Annotated[str, Field(max_length=MAX_EXTERNAL_ID_STR_LENGTH)] | int
```

**Type discrimination** (how backends distinguish str vs int vs UUID):
- `YAMLRepository` / `JsonRepository`: Python `==` operator (native type comparison).
- `DjangoRepository`: `external_id_type` column (`"uuid"` / `"int"` / `"str"`), paired
  with `external_id` (serialised string column).

---

## Existing Entity Fields Used

### Item (`taxomesh/domain/models/item.py`)

| Field | Type | Role in this feature |
|---|---|---|
| `item_id` | `UUID` | Internal identifier (returned in results) |
| `external_id` | `ExternalId` | Lookup key |

### Category (`taxomesh/domain/models/category.py`)

| Field | Type | Role in this feature |
|---|---|---|
| `category_id` | `UUID` | Internal identifier (returned in results) |
| `external_id` | `ExternalId` | Lookup key (default `""`) |
| `name` | `str` | Used to exclude `"__root__"` in `assignable_categories_qs()` |
| `enabled` | `bool` | Used to exclude disabled categories in `assignable_categories_qs()` |

### CategoryModel (`taxomesh/contrib/django/models.py`) — ORM only

| Column | Type | Role in this feature |
|---|---|---|
| `external_id` | `CharField` | Serialised lookup key |
| `external_id_type` | `CharField` (`"uuid"/"int"/"str"`) | Type discriminator for exact-type filter |
| `enabled` | `BooleanField` | Filter for `assignable_categories_qs()` |
| `name` | `CharField` | Exclusion of `__root__` in `assignable_categories_qs()` |

### ItemModel (`taxomesh/contrib/django/models.py`) — ORM only

| Column | Type | Role in this feature |
|---|---|---|
| `external_id` | `CharField` | Serialised lookup key |
| `external_id_type` | `CharField` (`"uuid"/"int"/"str"`) | Type discriminator for exact-type filter |

---

## No Schema Changes

All columns above exist since spec 012. No `ALTER TABLE`, no new migration file, no new
model field — FR-009 is satisfied by design.

---

## New Methods — Summary Table

| Class | Method | Protocol? | Return type |
|---|---|---|---|
| `TaxomeshRepositoryBase` | `list_items_by_external_id(external_id)` | ✅ | `list[Item]` |
| `TaxomeshRepositoryBase` | `list_categories_by_external_id(external_id)` | ✅ | `list[Category]` |
| `JsonRepository` | `list_items_by_external_id(external_id)` | ✅ | `list[Item]` |
| `JsonRepository` | `list_categories_by_external_id(external_id)` | ✅ | `list[Category]` |
| `YAMLRepository` | `list_items_by_external_id(external_id)` | ✅ | `list[Item]` |
| `YAMLRepository` | `list_categories_by_external_id(external_id)` | ✅ | `list[Category]` |
| `DjangoRepository` | `list_items_by_external_id(external_id)` | ✅ | `list[Item]` |
| `DjangoRepository` | `list_categories_by_external_id(external_id)` | ✅ | `list[Category]` |
| `DjangoRepository` | `assignable_categories_qs()` | ❌ extra | `Any` (QuerySet at runtime) |
| `TaxomeshService` | `get_items_by_external_id(external_id)` | N/A | `list[Item]` |
| `TaxomeshService` | `get_categories_by_external_id(external_id)` | N/A | `list[Category]` — root excluded |

---

## Root Exclusion Rule (D-007)

`TaxomeshService.get_categories_by_external_id` MUST exclude the root category from results:

```
results = repo.list_categories_by_external_id(external_id)
return [cat for cat in results if cat.category_id != self._root_id]
```

**Scope**: Service layer only. Repository backends are not modified — they return raw matches
including root if present. The service applies the post-filter using `self._root_id`.

**Rationale**: Root is stored with `external_id = ""` (default). Without this filter,
`get_categories_by_external_id("")` would return the internal root category to consumers.
