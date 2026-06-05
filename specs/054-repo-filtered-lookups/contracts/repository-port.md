# Contract Delta: `TaxomeshRepositoryBase` (054)

The repository port (`taxomesh/ports/repository.py`, a `typing.Protocol`)
gains one method and two keyword filters. All four implementations
(`JsonRepository`, `YAMLRepository`, `DjangoRepository`,
`InMemoryRepository` test fixture) must satisfy both, verified structurally
by mypy --strict and behaviorally by the 4-backend contract tests.

## New method

```python
def get_items_by_ids(
    self,
    item_ids: Collection[UUID],
    *,
    enabled: bool | None = None,
) -> dict[UUID, Item]:
    """Return items whose item_id matches any value in item_ids.

    The input is pre-normalised: duplicates have already been removed by
    the caller (e.g. ``TaxomeshService``). The adapter MUST NOT perform
    any further normalisation.

    Args:
        item_ids: A collection of internal item UUIDs to look up.
            Guaranteed to contain no duplicates. An empty collection
            returns an empty dict.
        enabled: ``True`` returns only enabled items; ``False`` only
            disabled; ``None`` (default) returns all matching items
            regardless of enabled state.

    Returns:
        A dict mapping each found item_id to its Item. Missing IDs are
        silently absent from the result — no error is raised.

    Raises:
        TaxomeshRepositoryError: On storage failure.
    """
    ...
```

**Placement**: beside `get_items_by_external_ids` (the 052 bulk-lookup
section) — it is its internal-ID twin.

## Extended method

```python
def list_item_parent_links(
    self,
    *,
    item_id: UUID | None = None,
    category_ids: Collection[UUID] | None = None,
) -> list[ItemParentLink]:
    """Return item→category placements, optionally filtered.

    Filters:
        - ``item_id``: when given, only links whose ``item_id`` equals it.
        - ``category_ids``: when given, only links whose ``category_id``
          is a member. An EMPTY collection returns ``[]`` — it is NOT
          treated as "no filter".
        - Both given: AND semantics.
        - Both ``None`` (default): all links — identical to the previous
          unfiltered behavior.

    Ordering (unchanged, holds under every filter combination):
        ``(category_id ASC, sort_index ASC, item_id ASC)``.

    Raises:
        TaxomeshRepositoryError: On storage failure.
    """
    ...
```

**Backward compatibility**: both parameters are keyword-only with `None`
defaults — every existing call site (`repo.list_item_parent_links()`)
compiles and behaves identically.

## Adapter obligations

| Adapter | `get_items_by_ids` | `list_item_parent_links` filters |
|---|---|---|
| `JsonRepository` | dict-lookup loop over `self._items` | in-memory comprehension before existing sort |
| `YAMLRepository` | dict-lookup loop over `self._items` | in-memory comprehension before existing sort |
| `DjangoRepository` | `filter(item_id__in=…)` (+ `enabled=…` when not `None`) — **DB-side** | `filter(item_id=…)` / `filter(category_id__in=…)` chained onto existing `order_by` — **DB-side** |
| `InMemoryRepository` (tests/service/conftest.py) | dict/list lookup | in-memory comprehension + contract sort (the fixture previously returned insertion order, violating the documented ordering contract — aligned as part of this feature; see research.md R8) |

## Service consumer contract (call-site rewiring)

| Site | Method | Replaces | With |
|---|---|---|---|
| 1 | `list_related_items_for_sources` | `list_items()` full map | `get_items_by_ids(source_ids ∪ target_ids, enabled=True)` |
| 2 | `list_categories_by_item` | full link scan + Python filter | `list_item_parent_links(item_id=item_id)` |
| 3 | `_load_item_candidates` (recursive) | full item map + full link scan | `list_item_parent_links(category_ids=all_category_ids)` + `get_items_by_ids(matched_item_ids, enabled=True)` |
| 4 | `list_items(category_id=…)` | full link scan + Python filter | `list_item_parent_links(category_ids=[category_id])`; item resolution via `self.get_item` per link **unchanged** |

Invariants each rewiring must preserve: see plan.md “Behavior-Parity
Pin-downs” and research.md R1–R2.
