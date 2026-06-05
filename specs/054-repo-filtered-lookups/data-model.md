# Data Model: Repository-Level Filtered Lookups (054)

**No domain model changes.** `Item`, `Category`, `ItemParentLink`, and all
other Pydantic models are untouched; no migrations; no new fields. This
feature only changes *how* existing records are queried.

## Entities involved (read-only)

### Item (unchanged)
- `item_id: UUID` — internal identity; **new bulk lookup key** for
  `get_items_by_ids`.
- `enabled: bool` — tri-state filterable at the repository (`True`/`False`/`None`).
- All other fields irrelevant to this feature.

### ItemParentLink (unchanged)
- `item_id: UUID` — **new repository-level filter** (single value).
- `category_id: UUID` — **new repository-level filter** (membership in a collection).
- `sort_index: int` — ordering within a category; ordering contract unchanged.

## Query contracts (deltas only)

### `get_items_by_ids(item_ids, *, enabled=None) -> dict[UUID, Item]`  *(new)*

| Aspect | Rule |
|---|---|
| Input | `Collection[UUID]`, pre-deduplicated by caller; adapter does no normalisation |
| Empty input | `{}` |
| Missing IDs | Silently absent from result — never an error |
| `enabled=True/False` | Only items with matching enabled state appear |
| `enabled=None` (default) | No enabled filtering |
| Result keying | `item_id → Item`, found entries only |
| Failure | `TaxomeshRepositoryError` on storage failure |
| Complexity | O(len(item_ids)) for dict-backed adapters; single `IN` query for Django |

### `list_item_parent_links(*, item_id=None, category_ids=None)`  *(extended)*

| `item_id` | `category_ids` | Result |
|---|---|---|
| `None` | `None` | All links — byte-identical to current behavior |
| `U` | `None` | Only links with `link.item_id == U` |
| `None` | collection `C` | Only links with `link.category_id ∈ C`; **empty `C` ⇒ `[]`** |
| `U` | collection `C` | AND of both conditions |

Ordering under every combination: `(category_id ASC, sort_index ASC,
item_id ASC)` — the existing contract, unchanged.

## State transitions

None — strictly read paths.
