# Research: Search Corpus Cache (040)

**Branch**: `040-search-corpus-cache`
**Date**: 2026-03-16

---

## R-001: Current candidate loading hot-path

**Decision**: Fix `_load_item_candidates()` to call `self.list_items()` (memoized) instead of `self._repository.list_items()` (unmemoized) when `category_id is None`.

**Finding**: In `service.py`, `_load_item_candidates()` currently calls `self._repository.list_items()` directly for the unfiltered path. This bypasses the `@memoize(5)` cache on `self.list_items()`. For `search_categories()`, the code directly calls repository or list helpers that also bypass the memoized path.

**Rationale**: The service already has `list_items()` decorated with `@memoize(DEFAULT_CACHE_TTL)`. Routing the unfiltered search candidate load through this method is a one-line change with zero architectural impact. The memoized copy is already invalidated by `clear_all_caches()` on every write.

**Alternatives considered**:
- Add a new repository method: rejected per FR-020 and spec §9.4 — prefer service-layer optimization first.
- Use a separate cache keyed by entity ID set: more complex; the TTL memoize on `list_items()` already solves the cross-call reuse.

---

## R-002: Should the corpus cache use the existing TTL memoize utility or a dedicated explicit cache?

**Decision**: Use a **dedicated explicit `None`-sentinel cache** owned directly by `TaxomeshService` instance attributes (`_item_corpus`, `_category_corpus`), not the TTL memoize utility.

**Rationale**:
- The TTL memoize utility invalidates entries by time, not by write event. A corpus that is valid for 5 seconds after a write would return stale normalized candidates until TTL expiry.
- The corpus cache must be invalidated the moment a write occurs — the existing `clear_all_caches()` mechanism applies to TTL caches, but the corpus cache needs precise write-triggered invalidation.
- A `None`-sentinel pattern (`if self._item_corpus is None: build it`) is the simplest and most readable approach, with zero external dependencies.
- Each write method that already calls `clear_all_caches()` also sets `self._item_corpus = None` or `self._category_corpus = None`. This is explicit and easy to audit.

**Alternatives considered**:
- Register corpus cache clears into the `_cache_registry` in `memoize.py`: would work, but ties the corpus lifecycle to the global TTL registry, which is designed for TTL-based caches. Mixing semantics would be confusing.
- TTL memoize on a `_build_item_corpus()` method: would have the same TTL-staleness problem described above.

---

## R-003: Should category search receive the same normalized-corpus treatment as item search in this cycle?

**Decision**: Yes — both item and category corpus caches ship in the same implementation cycle.

**Rationale**: The spec explicitly requires FR-005 and FR-006 (item and category corpus caches). Both have the same pattern and cost. Deferring category corpus to a follow-up adds release coordination overhead with minimal benefit given the code is essentially symmetric.

---

## R-004: Should `_score_and_rank()` be split or overloaded to accept pre-normalized candidates?

**Decision**: Add a private method `_score_corpus()` in `TaxomeshService` that accepts `list[SearchCandidate[_T]]` and calls `SearchEngine._score_prenorm()` directly, skipping normalization. Keep `_score_and_rank()` unchanged for the filtered (per-query) path.

**Rationale**:
- `_score_and_rank()` currently normalizes each candidate's fields on every call. For cached corpus scoring, the candidates are already normalized — calling normalize again would be wasteful and redundant.
- Splitting into a corpus-aware path keeps existing behavior unchanged for filtered searches, which build fresh `SearchCandidate` wrappers from a subset of items.
- A separate private method preserves single responsibility: `_score_and_rank()` = "build candidates + score", `_score_corpus()` = "score pre-built candidates".

**Alternatives considered**:
- Modify `_score_and_rank()` to accept `list[_T] | list[SearchCandidate[_T]]`: union type is harder to reason about under mypy strict.
- Replace `_score_and_rank()` entirely: would change the filtered search path unnecessarily, risking regressions.

---

## R-005: How should corpus invalidation be wired into write methods?

**Decision**: Each write method calls the existing `clear_all_caches()` and then explicitly sets `self._item_corpus = None` (for item-affecting writes) or `self._category_corpus = None` (for category-affecting writes). Both are set to `None` by a helper method `_invalidate_search_corpora()` that is called from `clear_all_caches()` — no: the service layer will handle it directly with per-corpus invalidation.

**Final approach**:
- Item writes: After `clear_all_caches()`, set `self._item_corpus = None`.
- Category writes: After `clear_all_caches()`, set `self._category_corpus = None`.
- Item placement changes (`place_item_in_category`, `remove_item_from_category`, `reparent_item`): Do **not** invalidate `_item_corpus`. These only affect placement structure, not the global item corpus fields (name, slug, external_id). Filtered search loads candidates dynamically, not from the global corpus.
- Category parent link changes: Do **not** invalidate `_category_corpus`. Same reasoning — corpus fields are entity fields, not structural link fields.

**Per the spec §9.2**: "If a cached search corpus depends only on entity fields and not on placement links, item placement changes do not need to invalidate it for unrestricted global item search."

---

## R-006: What fields should SearchCandidate include for the corpus?

**Decision**: Exactly the fields already in `SearchCandidate`: `obj`, `norm_name`, `norm_slug`, `norm_ext`. No additions.

**Rationale**: `SearchCandidate` already exists in `search.py` and is exactly the right shape. It contains only generic search-relevant fields. No application-specific fields are needed or appropriate per FR-007 and FR-008.

**Finding**: `SearchCandidate.__init__` takes `(obj, norm_name, norm_slug, norm_ext)`. The corpus build step normalizes `item.name`, `item.slug`, and `item.external_id` once at corpus build time using `SearchEngine.normalize()`.

---

## R-007: Is staged fuzzy scoring worth adding in this cycle?

**Decision**: **Deferred**. Not implemented in this feature cycle.

**Rationale**: After the candidate-loading fix (R-001) and the normalized corpus cache (R-002), the two most expensive operations — repository I/O and field normalization — are eliminated from the hot path. Staged scoring would reduce fuzzy computation work, but this is secondary and carries ranking-correctness risk. It should be evaluated after Phase 1 and Phase 2 are benchmarked in production.

---

## R-008: Test strategy for behavioral verification without wall-clock assertions

**Decision**: Count repository calls (via `unittest.mock.patch` or a call-counting wrapper) and count corpus rebuilds (by tracking the `_item_corpus` object identity or a build counter) across repeated searches.

**Pattern**:
```python
# Verify repository not called on warm cache
with patch.object(service._repository, "list_items", wraps=service._repository.list_items) as mock_list:
    service.search_items("foo")   # cold
    service.search_items("bar")   # warm
    assert mock_list.call_count == 1  # only called once
```

**For corpus identity**:
```python
service.search_items("foo")   # builds corpus
corpus_before = service._item_corpus
service.search_items("bar")   # reuses corpus
assert service._item_corpus is corpus_before  # same object, not rebuilt
```

**For invalidation**:
```python
service.search_items("foo")
service.create_item(...)       # should invalidate
assert service._item_corpus is None
service.search_items("foo")   # should contain new item
```

This approach is deterministic, backend-neutral, and not brittle.
