# Research: Repository-Level Filtered Lookups (054)

No `NEEDS CLARIFICATION` markers existed in the Technical Context — the stack
is fully established. Research focused on pinning behavior-parity invariants
from the current implementation and on adapter-level design decisions.

## R1 — `enabled` semantics at sites 1 and 3

**Decision**: The service calls `get_items_by_ids(ids, enabled=True)` at both
`list_related_items_for_sources` (site 1) and `_load_item_candidates`
recursive path (site 3).

**Rationale**: Both sites today call `self._repo.list_items()` — the port
signature is `list_items(self, *, enabled: bool | None = True)`, so the
current item maps contain **only enabled items**. Consequences preserved:

- Site 1: a *disabled* relation target is absent from the map → treated as
  dangling (skipped + WARNING, or raise with `skip_on_error=False`). A
  disabled *source* renders as `<unknown source item …>` in the WARNING.
- Site 3: a link to a disabled item hits the `item is None` branch → silently
  skipped.

Passing `enabled=None` would change both behaviors. This is the single most
dangerous parity trap in the feature; it gets dedicated regression tests.

**Alternatives considered**: `enabled=None` + service-side filtering —
rejected: re-implements filtering in the application layer and risks drift
from adapter semantics.

## R2 — Site 4 keeps per-link `self.get_item(...)`

**Decision**: In `list_items(category_id=...)` (site 4) only the link fetch
changes (`list_item_parent_links(category_ids=[category_id])`); item
resolution stays `[self.get_item(lnk.item_id) for lnk in links]`.

**Rationale**: `service.get_item` raises `TaxomeshItemNotFoundError` for a
dangling link — observable behavior that a silent bulk map would change.
`get_item` is also memoized (`@memoize(DEFAULT_CACHE_TTL)` family), so the
per-link calls are cheap and were never the profiled bottleneck (the full
link scan was).

**Alternatives considered**: bulk fetch + raise on missing — rejected: more
code to replicate the exact exception message/order semantics for zero
measured gain.

## R3 — Empty-collection semantics

**Decision**: `category_ids` empty collection (e.g. `()`/`[]`/`set()`) ⇒
return `[]`; `category_ids=None` ⇒ no filter. `get_items_by_ids` with empty
input ⇒ `{}` (mirrors 052). Both filters supplied ⇒ AND.

**Rationale**: `None` vs. empty must be distinguishable or a computed-but-
empty descendant set would silently degrade to a full scan — the exact bug
family this feature removes. 052 set the precedent for empty-input ⇒ empty
mapping.

**Alternatives considered**: treating empty as "no filter" (SQL `IN ()`
folklore) — rejected as dangerous; explicitly contracted in the port docstring.

## R4 — Django adapter query shape

**Decision**:
- `get_items_by_ids`: `ItemModel.objects.filter(item_id__in=ids)` +
  conditional `.filter(enabled=...)` when `enabled is not None`; build
  `dict[UUID, Item]` from rows. Same structure as 052's
  `get_items_by_external_ids` (`external_id__in`).
- `list_item_parent_links`: conditional `.filter(item_id=...)` /
  `.filter(category_id__in=[...])` chained onto the existing
  `.order_by("category_id", "sort_index", "item_id")` queryset.

**Rationale**: Django composes `QuerySet.filter` lazily — one SQL query
either way; `__in=[]` short-circuits via `EmptyResultSet` without a DB
round-trip, which already satisfies R3 for Django. No new indexes: 032 covers
`external_id`, 035 covers the link-table ordering columns; `item_id`
equality and `category_id IN` hit those existing indexes.

**Alternatives considered**: raw SQL / `.in_bulk()` — rejected;
`in_bulk()` keys by PK and bypasses the established row→domain mapping
helpers, `filter()` matches every other adapter method.

## R5 — JSON/YAML/InMemory filter implementation

**Decision**: Inline filtering in each adapter, applied **before** the
existing sort:

```python
links = self._item_parent_links
if item_id is not None:
    links = [l for l in links if l.item_id == item_id]
if category_ids is not None:
    wanted = set(category_ids)
    links = [l for l in links if l.category_id in wanted]
return sorted(links, key=...)  # existing key unchanged
```

`get_items_by_ids` is a dict-lookup loop over the adapter's existing
`self._items: dict[UUID, Item]` store (O(len(ids)), not O(N)).

**Rationale**: KISS — 4–6 lines per adapter; each adapter already implements
its ordering inline, so a shared helper module (like 052's `_external_id.py`)
would abstract less code than it adds. The file-backed adapters still load
the whole file into memory by design (their architecture); the win there is
skipping per-call sort/copy of unrelated links and, for `get_items_by_ids`,
dict access instead of full materialized list. The *primary* perf target is
`DjangoRepository` (letrastango's production backend), where filters reach
the database.

**Alternatives considered**: shared `_links.py` helper module — rejected
under YAGNI; reconsider if a third filter parameter ever appears.

## R6 — Input contract for `get_items_by_ids`

**Decision**: Mirror 052 verbatim, adapted to UUIDs: caller passes a
pre-deduplicated `Collection[UUID]` (the service naturally builds `set`s);
adapter performs no normalisation; missing IDs silently absent from the
returned `dict[UUID, Item]`; `TaxomeshRepositoryError` on storage failure.
No blank-string rule needed (UUIDs can't be blank).

**Rationale**: Symmetry with `get_items_by_external_ids` keeps the port
learnable and lets tests be adapted from 052's suite.

## R7 — Versioning

**Decision**: `0.1.0a41 → 0.1.0a42` in `pyproject.toml` + CHANGELOG entry
under a "Performance" heading referencing the four read paths and the two
port additions. Follows the repo's established alpha-increment pattern
(see 053's `0.1.0a41` bump commit).

## R8 — Adjacent contract-alignment fixes surfaced during implementation

**Decision**: Two pre-existing deviations from the port contract, surfaced by
the new contract tests, were fixed in place rather than worked around:

1. `InMemoryRepository.list_item_parent_links` (tests/service/conftest.py)
   returned **insertion order**, violating the documented
   ``(category_id ASC, sort_index ASC, item_id ASC)`` contract. It now sorts
   like the production adapters. Masked historically because every service
   call site re-sorts by ``sort_index``; the full suite confirmed no test
   depended on insertion order.
2. `DjangoRepository.list_item_parent_links` leaked raw ``DatabaseError`` on
   storage failure instead of wrapping in ``TaxomeshRepositoryError``. It now
   wraps, matching every other method in that adapter, the port docstring,
   the spec's "Storage failure" edge case, and Constitution V.

**Rationale**: Both are exactly the "adjacent, clearly broken, trivially
fixable" category; leaving them would have forced the new contract tests to
encode per-backend exceptions to the documented contract.
