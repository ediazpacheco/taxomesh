# Research: 039-search-perf

**Status**: Complete — no NEEDS CLARIFICATION items remain
**Date**: 2026-03-16

---

## Finding 1: Dual Normalization in Current Code

**Decision**: Eliminate the second normalization pass inside `score_candidate` by accepting pre-normalized fields.

**Rationale**: `_score_and_rank` (service.py:1350) already calls `SearchEngine.normalize(get_name(c))` to produce `norm_name`, then passes it as the `name` argument to `score_candidate`. However, `score_candidate` (search.py:100) calls `self.normalize(name)` again. This means every candidate name is normalized twice per search call. Slug and external_id are normalized only once (inside `score_candidate`), but they too benefit from pre-computation.

**Alternatives considered**:
- Keep `score_candidate` as-is and add a separate "pre-normalized" path: increases API surface unnecessarily.
- Add a `_score_candidate_prenorm` private overload: cleaner but duplicates scoring logic.
- Change `score_candidate` to accept pre-normalized fields via a flag/sentinel: chosen approach — a private internal method `_score_prenorm` avoids changing the existing public signature.

---

## Finding 2: Top-K Selection vs Full Sort

**Decision**: Use `heapq.nsmallest(limit, scored, key=lambda t: (-t[0], t[1]))` when `limit < len(scored)` to avoid O(N log N) full sort. Retain full sort as fallback when `limit >= len(scored)` (i.e., all results needed). Scored tuples are stored as `(-score, norm_name, obj)`, so `nsmallest` on the tuple yields the highest-scoring, alphabetically-earliest candidates — equivalent to `nlargest` on `(score, -name)` but consistent with the stored representation.

**Rationale**: `heapq.nlargest(k, iterable, key=...)` runs in O(N log k) time — strictly better than O(N log N) sort when k << N. For autocomplete (typical limit=5–20, catalog size=100–10000), this is the dominant gain. Python's `heapq.nlargest` is stdlib, zero new dependencies.

**Alternatives considered**:
- `sorted()` + slice: current approach; O(N log N), correct, simple. Retained as the fallback path for completeness.
- `heapq.nlargest` with positive score: equivalent; `nsmallest` was chosen because the scored tuples already store negated scores `(-score, name)`, making `nsmallest` the more natural and consistent call.
- Partial quicksort (introselect): not available in Python stdlib without `numpy`; rejected (no new deps).

**Threshold rule**: Apply heap path when `limit < len(scored) / 2` (conservative) or simply always use `nlargest` when `limit < len(scored)`. The simpler rule (always use `nlargest` when `limit < len(scored)`) is chosen — Python's implementation already falls back to sorted() for large k.

---

## Finding 3: Pre-Normalizing Candidate Fields

**Decision**: Introduce a `SearchCandidate` dataclass (or named tuple) that bundles a domain object with its pre-normalized name, slug, and external_id. Compute these once at the start of each `search_items()` / `search_categories()` call (not per-query-character).

**Rationale**: In autocomplete, the same catalog is queried on every keystroke. Even within a single multi-character session, normalizing the same 1000 candidates on each of 10 keystrokes is 10× redundant work. Within a single search call, the pre-computed `SearchCandidate` list eliminates the per-candidate double-normalization. Cross-call caching (within the service instance lifetime) can be layered on top but is deferred — the single-call improvement is the primary target.

**Alternatives considered**:
- Cross-call LRU cache keyed on catalog version: higher impact but requires a catalog version/hash mechanism; deferred to a future spec.
- Normalize at insert time (when items are added to the repo): touches adapters; out of scope for a pure application-layer optimization.
- `@functools.lru_cache` on `normalize()`: helps for repeated inputs but still pays per-call call overhead; `SearchCandidate` is more direct.

---

## Finding 4: Constitution Compliance

**Decision**: Implement `SearchCandidate` as a private internal class inside `search.py` (application layer). No new public exports. No changes to domain models or adapters.

**Rationale**:
- Hexagonal: optimization is entirely in the application layer; no adapter or domain code changes.
- Principle XI (OO by default): `SearchCandidate` is a class, not a bare tuple or namedtuple.
- Principle X (named constants): no new magic literals; existing constants unchanged.
- Principle IV (mypy strict): `SearchCandidate` will be typed; `_score_prenorm` will use typed signatures.

---

## Finding 5: Backward Compatibility

**Decision**: Keep the public signatures of `search_items()` and `search_categories()` unchanged. `_score_and_rank` is private and may be refactored freely.

**Rationale**: The spec mandates backward compatibility. No new parameters are needed for the top-k or pre-normalization changes — both are internal implementation details. The `SearchEngine.score_candidate()` public method signature is preserved; the optimization path uses a new private method `_score_prenorm` that accepts pre-normalized fields directly.

---

## Finding 6: Changelog and Documentation

**Decision**: Update `CHANGELOG.md` with a performance improvement entry under an `[Unreleased]` section. Update the search section of `README.md` to note the autocomplete performance improvement.

**Rationale**: The spec explicitly requested "update API changes in doc and in changelog." Since the API surface is unchanged (no new public params, no changed return types), the changelog entry is a "performance" note, not an "API change" note.
