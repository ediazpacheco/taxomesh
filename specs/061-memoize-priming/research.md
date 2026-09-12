# Phase 0 Research: Category priming and read-through after 060

Regenerated 2026-09-12 for the narrowed, re-scoped spec. R1–R4 carry forward from the
2026-09-10 revision, with R2's decision replaced and its dead end kept. R5–R8 fold in the
measurements, each re-run in this session unless marked otherwise.

---

## R1 — The cache key shape, and how priming must reproduce it

**Decision**: Priming reuses the cache's own key construction rather than reimplementing
it. The key includes the bound instance.

**Findings** (verified by running against the installed package, not read from source
alone):

`memoize` builds `key = (args, tuple(sorted(kwargs.items())))`. For a decorated method
the decorator wraps the *function*, so a call written `self.get_category(cid)` arrives as
`args == (self, cid)`. A probe confirmed two calls with the same `(self, cid)` hit the
cache and only one reached the underlying function.

The consequence is that any insert must account for the instance. Under the class design
(R2) that happens structurally: `MemoizedMethod` prepends the instance it was bound to, so
a call site writes `self.get_category.prime(value, cid)` and cannot forget it. The
2026-09-10 module-level helper made this the caller's job — `prime(TaxomeshService.get_category,
category, self, category_id)` — and an omitted instance wrote an entry the accessor would
never find.

**Rationale**: The key shape is internal to the utility. Duplicating its construction at
the call site would give it two definitions that can drift silently, and a drifted key
fails open — quietly costing a read rather than raising.

**Alternatives considered**: Reconstructing the key at each call site — rejected, DRY
violation with a silent failure mode.

---

## R2 — Typing insert and lookup under `mypy --strict` without `Any`

**Decision**: Descriptor classes. `memoize(ttl)` returns a `MemoizedFunction[**P, R]`;
accessing it on an instance returns a `MemoizedMethod[**P, R]`. `prime` and `cached` are
methods on both, typed against the decorated callable's own `P` and `R`. A miss is the
`Miss` sentinel, so `cached` returns `R | Miss`.

### The dead end, kept because it is still the reason the shape looks like this

The obvious approach — widening the decorator's return type to a `Protocol` carrying
`__call__`, `clear_cache` and `prime` — **does not work**. A Protocol attribute is not a
descriptor, so mypy stops binding the method: `self.get_category(cid)` is then checked
against `__call__(self, category_id)` with the instance unconsumed, producing
`Missing positional argument "category_id"` and
`Argument 1 has incompatible type "Service"; expected …`. Verified, two errors.

This is why the 2026-09-10 revision chose a module-level `prime(func, value, /, *args, **kwargs)`
helper instead. **A real class with `__get__` is a different mechanism**, and it works: a
class *is* a descriptor, so binding happens through `__get__` and mypy follows it. The
Protocol finding does not generalise to it.

### What replaced the module-level helper, and why

The helper reached into the closure through `getattr(func, _PRIME_ATTR, None)` plus a
`cast(_Primer, primer)` — an untyped hop that defeated the argument checking it existed to
provide, and a module-level function with side effects, which NFR-005 forbids. It was
never released (`main` is `0.1.0a50`), so removing it breaks nothing.

### The `__get__` overload, and where precision stops

`MemoizedFunction.__get__` is overloaded: `(None, owner) -> Self` for class-level access,
and a second overload that narrows its own `self` type to recover the instance:

```python
@overload
def __get__(self, instance: None, owner: type[object]) -> Self: ...
@overload
def __get__[S, **Q](
    self: "MemoizedFunction[Concatenate[S, Q], R]", instance: S, owner: type[S]
) -> MemoizedMethod[Q, R]: ...
```

**`MemoizedMethod` holds its owner as `MemoizedFunction[..., R]` — gradual in the
parameters, precise in the return type.** This was tested rather than assumed. Making it
precise means making the bound view generic in the instance type as well
(`MemoizedMethod[S, **P, R]` holding `MemoizedFunction[Concatenate[S, P], R]`), and mypy
then rejects `__get__`'s own body, which it checks once and generically:

```
error: Overloaded function implementation cannot produce return type of signature 2  [misc]
error: Argument 1 to "MemoizedMethod" has incompatible type "Self";
       expected "MemoizedFunction[[object, VarArg(Any), KwArg(Any)], R]"  [arg-type]
```

Recovering that would need a `cast`, which Principle IV and the project's elegance rule
both rule out. And the precise form buys nothing: `S` appears in no caller-visible
signature, so it would be a phantom type parameter whose only effect is to make `__get__`
uncheckable.

**Justification under Principle IV** (also recorded in the plan's Complexity Tracking):
the gradual form is confined to one private attribute. Every caller-visible signature on
`MemoizedMethod` — `__call__`, `prime`, `cached`, `clear_cache` — is stated in terms of
`P` and `R`, so nothing gradual reaches a call site. `...` is the ParamSpec analogue of a
gradual type, not `Any`; no `Any`, `cast` or `type: ignore` appears anywhere in the design.

### Why the sentinel, and not a wrapper

`cached` must distinguish a miss from a cached value that is itself falsy or `None`
(FR-001). Two shapes were prototyped and both type-check clean:

| shape | narrowing | cost | verdict |
|---|---|---|---|
| `R \| Miss` (sentinel singleton) | `isinstance(hit, Miss)` | no allocation | **chosen** |
| `Hit[R] \| None` (frozen slotted wrapper) | `is None` | one allocation per hit | rejected |

The sentinel narrows correctly — mypy reports `str | Miss` where `str` is expected, and
narrows to `str` in the negative branch — and the read-through loop runs once per category,
so avoiding an allocation per hit is free. The wrapper's advantage is soundness for a
return type of `object` or one that could itself include `Miss`; none of the 16 memoized
sites has such a return type. Decided by the user, 2026-09-12.

### Evidence

Prototype and misuse file: `measurements/unified_proto.py` / `unified_misuse.py`, updated
this session to the chosen shape. `mypy --strict --python-version 3.13` over the prototype
reports **no issues**; over the misuse file it reports **13 errors, one per deliberate
misuse** — the 6 the 2026-09-11 prototype caught (value type, argument type, return type,
too many args on a zero-argument function, positional-for-keyword-only, argument type on a
plain function) plus 7 for the lookup path (argument type and arity on `cached` for both a
method and a plain function, unnarrowed `R | Miss` assigned to `R`, wrong key type on
`prime`, and a narrowed value assigned to the wrong type).

---

## R3 — Asserting exact read counts across all four backends

**Decision**: Django asserts with `CaptureQueriesContext`; the file and in-memory backends
assert with a counting spy at the repository boundary. Both already exist in the suite
from 060.

**Rationale**: 060 established both mechanisms and they agreed exactly on every row when
the consumer cross-checked them. Reusing them keeps the new assertions comparable with the
existing gates rather than introducing a third notion of "a read". One repository call
counts as one storage read — the equivalence R6 relies on.

**Alternatives considered**: Timing-based assertions — rejected, non-deterministic and
unable to distinguish a cache hit from a fast query.

---

## R4 — Why eviction is not bundled, and why invalidation stays as it is

**Decision**: Both out of scope. Recorded as follow-up.

**Rationale**: The cache has no eviction and no size cap today — a single write per key is
its only insert, and an expired entry never accessed again is never reclaimed. That is a
pre-existing property, not one this feature introduces, and priming categories does not
make it material: 93 entries at 0.17 MB measured.

It *would* be material on the item path, which is precisely why the item path is excluded
(R7: priming items adds 2.37 MB per `list_items` call on a 2,000-item fixture, and the
consumer's own corpus figure is 108 MB per worker). Adding an LRU is the right long-term
answer and is what would unblock item priming, but it touches all 16 memoized reads and
needs gates of its own.

Reclaiming *expired* entries is the cheaper candidate: an expired entry is never served, so
dropping it cannot change any read count. Still out of scope here.

**Invalidation** — the module-level `_cache_registry` and `clear_all_caches()` — stays
exactly as it is, by the user's decision (spec Clarifications, 2026-09-11). The class
redesign makes encapsulating it tempting, but every write path in the service calls
`clear_all_caches()` and changing that is a behaviour surface this feature has no gate for.
The Principle XI exception is recorded in the plan's Complexity Tracking.

---

## R5 — The consumer's own walk (external provenance; NOT re-run this session)

LetrasTango's pre-rewrite `_category_paths_from_main`, copied verbatim from its
`c842522fc^`, against a copy of its local SQLite database (93 categories, 178
category-parent links). Counted with `CaptureQueriesContext`, cold, median of 3.

| version | total | `category_parent_link` | `category` | output |
|---|---:|---:|---:|---|
| `0.1.0a49` | 150 | 75 | 75 | identical |
| `0.1.0a50` | 177 | 75 | 102 | identical |
| priming | 103 | 75 | 28 | identical |
| priming + read-through | 103 | 75 | 28 | identical |

**Not reproducible in this repository**: the database is not committed
(`measurements/lt/db_copy.sqlite3` must be pointed at your own copy), so this table keeps
external provenance under FR-014 rather than being re-measured. The equivalent
consumer-shaped tree in R6 — which *is* reproducible here — gives 150 / 177 / 103 / 103,
matching row for row.

**103, not 102.** The consumer's own measurement of the same walk reads 102, taken with
*every* category pre-cached, root included. Priming cannot pre-cache the walk's own root —
nothing returns it as anybody's child — so its validation stays the one genuine miss. 103
is the floor for this walk without changing the single-call cost 060's gates fix at 3.

---

## R6 — Read counts per access pattern (re-run 2026-09-12, all figures reproduced)

Each version behind its own `JsonRepository`, wrapped in a proxy counting every `get_*` /
`list_*` repository call. Cold before each pattern: `clear_all_caches()` + counter reset.
Script: `measurements/reads.py`; variants built by `measurements/make_variants.py`.

| pattern | a49 | a50 | priming only | **priming + read-through** | itemprime | full |
|---|---:|---:|---:|---:|---:|---:|
| walk, 12 nodes, depth 2 | 26 | 30 | 18 | **18** | 18 | 18 |
| walk, 84 nodes, depth 3 | 170 | 191 | 107 | **107** | 107 | 107 |
| walk, 75 nodes, consumer-shaped | 150 | 177 | 103 | **103** | 103 | 103 |
| walk over shared children (multi-parent) | 12 | 16 | 11 | **9** | 11 | 9 |
| fetch children by id, then list them | 7 | 8 | 8 | **7** | 8 | 7 |
| `list_categories_by_item` × 40 over 5 categories | 85 | 120 | 120 | **84** | 120 | 84 |
| `list_items`, then `list_categories_by_item` per item | 45 | 63 | 63 | **46** | 43 | 26 |
| `list_items`, then `get_item` per item | 22 | 23 | 23 | **23** | 3 | 3 |
| 10 small `list_items` sharing 3 items | 23 | 30 | 30 | **30** | 30 | 21 |
| cold single calls (060's gates) | 22 / 7 / 8 | 3 / 3 / 3 | 3 / 3 / 3 | **3 / 3 / 3** | 3 / 3 / 3 | 3 / 3 / 3 |

Every figure reproduced exactly against the 2026-09-11 recording. Each run's `taxomesh`
import path was asserted to come from its own version directory.

**What the table decides.** Priming alone is above `0.1.0a49` on two patterns — 8 vs 7 and
120 vs 85 — and the second is the shape of a per-item URL builder the consumer measured and
rejected on `0.1.0a50`. Read-through closes both (7 and 84) and improves the multi-parent
walk from 11 to 9. This is why the spec requires both and not priming alone.

**The item residual.** The chosen column exceeds `0.1.0a49` on exactly the three item
patterns, by +1, +1 and +7 — at most one read per `list_items(category_id=…)` call in the
pattern, which is the bound the spec states. The `full` column is what closing it would buy
(26 / 3 / 21) and is excluded by FR-007.

---

## R7 — Retained memory (re-run 2026-09-12; a50 and itemprime exact, a49 within noise)

Django backend (fresh objects per query, as in production), 2,000 items at ~3.3 KB of
metadata JSON each, 10% disabled. `tracemalloc` bytes still held after the caller drops its
own reference to the result. Script: `measurements/memory.py <version> 2000`.

| version | one `list_items(category_id=…)`, `enabled=True` | `enabled=None` |
|---|---:|---:|
| a49 | 20.06 MB *(recorded 2026-09-11: 20.09)* | 20.07 MB *(recorded: 20.08)* |
| a50 | 17.44 MB | 19.37 MB |
| itemprime | 19.81 MB | 19.80 MB *(recorded: 19.81)* |

`tracemalloc` totals carry roughly ±0.03 MB of run-to-run noise, which is the whole of the
a49 drift; a50 and itemprime reproduced to the cent. The figure the argument rests on is a
**difference measured within one run shape** and is exact either way: priming `get_item`
adds **2.37 MB** (19.81 − 17.44) on top of what `list_items`'s own result cache already
retains.

That last point is the one worth keeping in view: `list_items` is itself memoized, so a50
already retains the listing until the next write. Not priming items avoids only the
increment, not the retention. The retention is a pre-existing property of the unbounded
cache and is out of scope (R4).

The consumer's own corpus figures — 108 MB per worker, ≈13.6 KB per item, cross-checked
against 25.9 MB of metadata JSON on disk — are its measurements, relayed under FR-014's
external-provenance clause and not reproduced here.

---

## R8 — The read ladder (re-run 2026-09-12; reproduced — now provenance for the API refactor)

Throwaway prototypes of the two read shapes considered instead of, or alongside, priming,
measured on the same trees as R6. Script: `measurements/ladder.py`.

| tree | per-level read | subtree read |
|---|---:|---:|
| 12 nodes, depth 2 | 6 | 3 |
| 84 nodes, depth 3 | 8 | 3 |
| 75 nodes, consumer-shaped | 8 | 3 |

The per-level cost grows with depth; the subtree cost does not grow at all.

**This is no longer a 061 decision.** The subtree read left this feature on 2026-09-12
because its name repeats the defect the API-UX refactor exists to fix — a `list_*` that
returns a mapping. The table is kept here as the measured provenance that refactor
inherits; `docs/backlog/prompt-api-refactor.md` (defect 6) cites it, together with the
behaviour already specified in this spec's 2026-09-11 revision.
