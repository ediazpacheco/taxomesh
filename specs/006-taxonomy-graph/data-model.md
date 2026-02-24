# Data Model: Taxonomy Graph (006-taxonomy-graph)

**Date**: 2026-02-24 | **Branch**: `006-taxonomy-graph`

---

## New Domain Aggregates

These types are **read-model aggregates** (not mutable domain entities). They live in
`taxomesh/domain/graph.py`. They use `@dataclass` — see research.md R-003.

---

### `CategoryNode`

A single node in the taxonomy tree snapshot. Represents one category together with the
items assigned to it and its child categories.

```python
@dataclass
class CategoryNode:
    category: Category               # the Category domain entity
    items: list[Item]                # items placed in this category, sorted by sort_index ASC
    children: list[CategoryNode]     # child categories, sorted by sort_index ASC (on explicit link)
```

| Field | Type | Notes |
|---|---|---|
| `category` | `Category` | Full domain entity; `category_id`, `name`, `description`, `metadata` available |
| `items` | `list[Item]` | Empty list if no items assigned; sorted by `ItemParentLink.sort_index` |
| `children` | `list[CategoryNode]` | Empty list for leaf nodes; sorted by `CategoryParentLink.sort_index` on the explicit link |

**Constraints**:
- `__root__` category never appears as a `CategoryNode`.
- A category with multiple explicit parents appears as a separate `CategoryNode` under each parent (repeated, not deduplicated).

---

### `TaxomeshGraph`

The top-level read-only snapshot of the full taxonomy.

```python
@dataclass
class TaxomeshGraph:
    roots: list[CategoryNode]   # top-level categories (root-only parents), sorted by sort_index ASC
```

| Field | Type | Notes |
|---|---|---|
| `roots` | `list[CategoryNode]` | Empty list for an empty taxonomy; never contains `__root__` |

**Construction**: Produced exclusively by `TaxomeshService.get_graph()`. Never constructed directly by callers.

---

## Modified Entities

None. All existing domain entities (`Category`, `Item`, `Tag`, `CategoryParentLink`,
`ItemParentLink`, `ItemTagLink`) remain unchanged.

---

## Relationships

```
TaxomeshGraph
└── roots: list[CategoryNode]
    └── CategoryNode
        ├── category: Category          (existing entity)
        ├── items: list[Item]           (existing entity)
        └── children: list[CategoryNode]  (recursive)
```

---

## Not in Scope

- Tag data — not included in `TaxomeshGraph` or `CategoryNode`
- `__root__` visibility — hidden from graph entirely
- Mutable graph operations — `TaxomeshGraph` is a snapshot; reads only
