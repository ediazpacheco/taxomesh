# Data Model: 039-search-perf

**Date**: 2026-03-16

No new persistent data models are introduced by this feature. All changes are internal to the application layer and involve transient, in-memory structures only.

---

## Internal Representation: SearchCandidate

**Purpose**: Bundle a domain object (Item or Category) with its pre-normalized field values to avoid repeated normalization work per search call.

**Location**: `taxomesh/application/search.py` (private; not exported)

**Fields**:

| Field | Type | Description |
|---|---|---|
| `obj` | `_T` (TypeVar bound to Item or Category) | The original domain object |
| `norm_name` | `str` | `SearchEngine.normalize(obj.name)` — computed once |
| `norm_slug` | `str` | `SearchEngine.normalize(obj.slug)` — computed once |
| `norm_ext` | `str` | `SearchEngine.normalize(obj.external_id)` if not sentinel, else `""` |

**Lifecycle**: Created at the beginning of `_score_and_rank` for each candidate, discarded after the ranked result list is returned. Not persisted, not cached across calls (cross-call caching is deferred).

**Constraints**:
- `SearchCandidate` is a private implementation detail; it MUST NOT appear in any public method signature.
- It MUST be a class (Principle XI), typed with a generic TypeVar for `obj`.

---

## Modified Behavior: SearchEngine._score_prenorm (new private method)

**Purpose**: Accept pre-normalized field values directly, bypassing the internal `self.normalize()` calls in the existing `score_candidate` method.

**Inputs**: pre-normalized query (`norm_q`), pre-normalized name (`norm_name`), pre-normalized slug (`norm_slug`), pre-normalized external_id (`norm_ext`), fuzzy flag.

**Output**: `float | None` — same semantics as `score_candidate`.

**Note**: The existing public `score_candidate` method MUST remain unchanged and continue to normalize its inputs internally. It may delegate to `_score_prenorm` after normalizing, or remain independent. No removal of public methods.

---

## Unchanged Domain Models

The following domain models are unchanged by this feature:

- `Item` — no field additions or removals
- `Category` — no field additions or removals
- `CategoryParentLink` — unchanged
- `ItemParentLink` — unchanged

No migrations are required.
