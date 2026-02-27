# Data Model: Graph Category UUID Display

**Feature**: 009-graph-category-uuid
**Date**: 2026-02-26

## Entities

No new entities, fields, or relationships are introduced by this feature.

### Existing Entities (read-only access)

| Entity | Field Used | Type | Source |
|--------|-----------|------|--------|
| Category | `category_id` | `UUID` | `taxomesh/domain/models.py` |
| CategoryNode | `category` | `Category` | `taxomesh/domain/graph.py` |

The `category_id` field already exists on the `Category` model and is
accessible via `CategoryNode.category.category_id` in the graph rendering
function. No model changes required.
