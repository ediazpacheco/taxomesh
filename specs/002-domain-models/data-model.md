# Data Model: Core Domain Models (002-domain-models)

**Date**: 2026-02-22
**Source**: `specs/002-domain-models/spec.md` (FR-001 – FR-010)

---

## Type Aliases (`taxomesh/domain/types.py`)

| Alias | Definition | Module |
|---|---|---|
| `ExternalId` | `UUID \| Annotated[str, Field(max_length=256)] \| int` | `taxomesh.domain.types` |

`ExternalId` is the canonical type for any value that identifies an external entity in a
consumer system. It accepts a UUID, an integer, or a string of at most 256 characters.
The `str` branch carries its `max_length` constraint inside the `Annotated` wrapper so
the constraint composes correctly inside a union without affecting the other branches.

Import: `from taxomesh.domain.types import ExternalId`

---

## Entity Overview

```
ModelBase
├── Item
├── Category
├── Tag
├── CategoryParentLink
├── ItemParentLink
└── ItemTagLink
```

All entities inherit from `ModelBase`. There is no runtime relationship between
entities — relationships are expressed through shared UUID field values and are
enforced by the repository layer, not the model layer.

---

## ModelBase

**Role**: Shared Pydantic configuration base. No fields of its own.

| Config key | Value | Effect |
|---|---|---|
| `populate_by_name` | `True` | Field names always work as keyword arguments |
| `validate_assignment` | `True` | Constraints re-run on field mutation |

---

## Item

**Role**: A reference to any external entity managed by the consumer. taxomesh does
not store or know the entity's data — only its identifier, enabled state, and metadata.

| Field | Type | Default | Constraints | Notes |
|---|---|---|---|---|
| `item_id` | `UUID` | `uuid4()` | — | Auto-generated internal PK; never supplied by caller |
| `external_id` | `ExternalId` (`UUID \| str \| int`) | required | str branch: max 256 chars | Polymorphic; `UUID` branch tried first by Pydantic |
| `enabled` | `bool` | `True` | — | Soft activation flag; no behavioural semantics at model layer |
| `metadata` | `dict[str, Any]` | `{}` (factory) | — | Arbitrary consumer key-value pairs; value type is intentionally open |

**Validation rules**:
- `external_id` as `str`: length ≤ 256 characters (inclusive boundary).
- `external_id` as `UUID` or `int`: no additional constraint.
- All constraints enforced both at construction and on field mutation.

**Identity**: `item_id` is the canonical internal identifier. `external_id` is
the consumer's own identifier — uniqueness across items is NOT enforced here.

---

## Category

**Role**: A named node in the taxonomy DAG. Categories may have multiple parents
(expressed via `CategoryParentLink` records). Categories carry an optional description
and arbitrary metadata.

| Field | Type | Default | Constraints |
|---|---|---|---|
| `category_id` | `UUID` | required | — |
| `name` | `str` | required | max 256 chars |
| `description` | `str \| None` | `None` | max 100 000 chars when present |
| `metadata` | `dict[str, Any]` | `{}` (factory) | — |

**Validation rules**:
- `name`: 1–256 characters (inclusive boundary). Empty string is technically valid at
  the model layer; the application service may impose further restrictions.
- `description`: `None` or a string of at most 100 000 characters.

**Relationships**:
- Zero or more `CategoryParentLink` records reference this category as child or parent.

---

## Tag

**Role**: A short free-form label that can be attached to items. Tag names are intentionally
short to encourage concise, reusable labels.

| Field | Type | Default | Constraints |
|---|---|---|---|
| `tag_id` | `UUID` | required | — |
| `name` | `str` | required | max 25 chars |
| `metadata` | `dict[str, Any]` | `{}` (factory) | — |

**Validation rules**:
- `name`: 1–25 characters (inclusive boundary).

**Relationships**:
- Zero or more `ItemTagLink` records reference this tag.

---

## CategoryParentLink

**Role**: A directed edge in the category DAG. Encodes the relationship
`category_id → parent_category_id` with an independent sort index controlling
the child's position within that parent's listing.

| Field | Type | Default | Constraints |
|---|---|---|---|
| `category_id` | `UUID` | required | — |
| `parent_category_id` | `UUID` | required | — |
| `sort_index` | `int` | `0` | — |

**Semantic constraints** (enforced by application layer, not this model):
- `category_id ≠ parent_category_id` (no self-loops).
- Adding this record must not create a cycle in the DAG — enforced by `domain/dag.py`
  per constitution Principle VI.

**Cardinality**: One record per `(category_id, parent_category_id)` pair. A category
may have multiple parent records (multi-parent DAG). The same logical edge MUST NOT
appear twice (unique constraint at the repository layer).

---

## ItemParentLink

**Role**: Places an item under a category. Encodes the relationship
`item_id → category_id` with an independent sort index.

| Field | Type | Default | Constraints |
|---|---|---|---|
| `item_id` | `UUID` | required | References `Item.item_id` |
| `category_id` | `UUID` | required | References `Category.category_id` |
| `sort_index` | `int` | `0` | — |

**Cardinality**: One record per `(item_id, category_id)` pair. An item may appear
under multiple categories (multiple records with the same `item_id`).

**Note**: `item_id` here is the *internal* UUID primary key of `Item`, not `external_id`.

---

## ItemTagLink

**Role**: Associates a tag with an item. Carries no sort index — tags are unordered.

| Field | Type | Default | Constraints |
|---|---|---|---|
| `tag_id` | `UUID` | required | References `Tag.tag_id` |
| `item_id` | `UUID` | required | References `Item.item_id` |

**Cardinality**: One record per `(tag_id, item_id)` pair. An item may have multiple
tags; a tag may be applied to multiple items.

**Note**: `item_id` here is the *internal* UUID primary key of `Item`.

---

## Relationship Map

```
Category ─────────────────────────────────────┐
    │                                          │
    │ (child)  CategoryParentLink  (parent)    │
    └──────────────────────────────────────────┘
           category_id   parent_category_id

Item ──────────────────── ItemParentLink ──── Category
  item_id                   item_id            category_id

Item ──────────────────── ItemTagLink ──────── Tag
  item_id                   item_id             tag_id
```

All links are UUID-to-UUID. The library enforces no referential integrity at the
model layer — that is the repository's responsibility.

---

## Mutable Default Safety

All `metadata` fields use `Field(default_factory=dict)`. This guarantees each model
instance receives a fresh, independent dictionary at construction time. Instances never
share a `metadata` dict object.

---

## mypy Notes

- `dict[str, Any]`: permitted by mypy strict. `Any` in value position is intentional
  and documented with an inline comment on every field.
- `ExternalId` alias (`UUID | Annotated[str, Field(max_length=256)] | int`): valid Pydantic v2
  union; mypy resolves it as `UUID | str | int` for type-checking purposes. Defined in
  `taxomesh.domain.types`.
- `Annotated[str, Field(max_length=100_000)] | None`: equivalent to `str | None`
  in mypy's view; Pydantic enforces the `max_length` constraint at runtime.
