# Research: Batch Item Relation Lookup

**Feature**: 038-batch-item-relations
**Phase**: 0 — Unknowns resolved before design

---

## Decision 1: Target Item Resolution Strategy

**Question**: How should the service resolve `Item` objects for all target item IDs found across the batch links, without calling `get_item()` N times?

**Options evaluated**:

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A | Add `get_items_by_ids(ids)` to `TaxomeshRepositoryBase` + all adapters | Most efficient (WHERE id IN) | New protocol method = wider scope; not requested by spec |
| B | Call `list_items()` once, build `dict[UUID, Item]`, filter in-memory | Single storage call; no new protocol method; simple | Loads all items for every batch call (full table scan) |
| C | Call `get_item(id)` per unique target UUID | Minimal code change | Still N queries for Django; violates spec intent |

**Decision**: **Option B** — use `list_items()` once per batch call to build a lookup dict, then index into it.

**Rationale**:
- Satisfies the spec constraint ("resolve Item once per target, not one-by-one per link").
- No new protocol method needed; scope stays minimal.
- For JSON/YAML adapters, `list_items()` is already an in-memory filter pass — same cost as a targeted scan.
- For DjangoRepository, `list_items()` issues a single `SELECT * FROM taxomesh_item` — one query vs. N. Acceptable at current scale. A `get_items_by_ids` optimization can be added in a future feature if profiling reveals it as a hotspot.

**Alternatives rejected**: Option A is correct design long-term but adds protocol scope beyond what the spec requests. Option C is explicitly prohibited by the spec.

---

## Decision 2: Protocol Extension — New Repository Method

**Question**: Should `list_item_relation_links_for_sources` be added to `TaxomeshRepositoryBase` (the `Protocol` in `ports/repository.py`)?

**Decision**: **Yes** — the method must be declared in `TaxomeshRepositoryBase` and implemented in all three adapters.

**Rationale**:
- Constitution Principle III: `TaxomeshRepositoryBase` is the structural contract. Any method the service calls on `self._repo` must be declared in the Protocol so mypy validates all adapters in `--strict` mode.
- The spec explicitly names all three adapters as implementors.

---

## Decision 3: Caching of the Batch Service Method

**Question**: Should `list_related_items_for_sources` be decorated with `@memoize(DEFAULT_CACHE_TTL)`?

**Context**: Existing `list_related_items()` and `list_item_relations()` are memoized. The `@memoize` decorator uses positional arguments as cache keys. `Collection[UUID]` (e.g., a `list`) is not hashable — the decorator would fail or require special handling.

**Options**:

| Option | Description |
|--------|-------------|
| A | No memoize — batch method is not cached |
| B | Convert `source_item_ids` to `frozenset` internally, cache on `(frozenset, frozenset-or-None)` |

**Decision**: **Option A** — no memoize on the batch method.

**Rationale**:
- The primary performance gain from the batch API is N→1 repository queries, not caching. Callers building indexes will often supply different sets on every call anyway.
- Adding `frozenset` conversion to make the cache key hashable introduces complexity for uncertain benefit.
- This matches YAGNI — add caching only when measured as a bottleneck.

---

## Decision 4: Handling of Empty and Duplicate `source_item_ids`

**Question**: What normalization should happen before any repository call?

**Decision**:
- **Empty collection**: short-circuit immediately, return `{}`. No storage access.
- **Duplicate IDs**: deduplicate via `set()` before passing to the repository. Repository implementations need not handle duplicates internally.

**Rationale**: Both behaviors are explicitly specified. Deduplication at the service layer avoids adapter-specific branching.

---

## Decision 5: Handling of Empty `relation_types`

**Question**: `relation_types=[]` (empty list) vs. `relation_types=None` — should they behave identically?

**Decision**: **Yes** — both mean "no filter; return all relation types."

**Rationale**: Spec contract: "Si `relation_types` está vacío o None, no filtrar por tipo." Repository implementations check `if relation_types` (falsy for both `None` and `[]`) before filtering.

---

## Decision 6: Ordering Contract

**Question**: What is the deterministic ordering for the batch method's return value?

**Decision**: `ORDER BY source_item_id ASC, relation_type ASC, sort_index ASC, target_item_id ASC`

**Rationale**:
- Primary sort by `source_item_id` groups results for efficient dict-building at the service layer.
- Secondary sort by `relation_type` ensures consistent grouping key order.
- `sort_index` controls display order within each group, matching existing single-item convention.
- `target_item_id` provides stable tie-breaking for identical sort indexes.

This matches the spec contract verbatim.

---

## Decision 7: Relation Type Normalization in Batch Filter

**Question**: Should `relation_types` filter values be normalized (lowercased/stripped) by the service before being passed to the repository?

**Decision**: **Yes** — the service normalizes each element in `relation_types` (strip + lowercase) before passing the list to the repository, consistent with how `relation_type` is normalized in `list_related_items()`.

**Rationale**: `ItemRelationLink.relation_type` is stored normalized. Filters must be normalized too to match. The pattern already exists in the single-item service method.

---

## Decision 8: Items Missing from `list_items()` Lookup

**Question**: What happens if a `target_item_id` from a link is not found in the `list_items()` result (e.g., orphaned link)?

**Decision**: Raise `TaxomeshItemNotFoundError` — consistent with how `get_item()` behaves for missing items (Constitution Principle V: no silent failures).

**Rationale**: If a link references a non-existent item, that is a data integrity problem. Silent omission would mask bugs. Raising an error is consistent with existing service behavior.
