# Phase 0 Research: Memoize priming for batch category reads

## R1 — The cache key shape, and how priming must reproduce it

**Decision**: Priming reuses the wrapper's own key construction rather than
reimplementing it. The key includes the bound instance.

**Findings** (verified by running against the installed package, not read from source
alone):

`memoize` builds `key = (args, tuple(sorted(kwargs.items())))`. For a decorated method
the decorator wraps the *function*, so a call written `self.get_category(cid)` arrives
as `args == (self, cid)`. A probe confirmed two calls with the same `(self, cid)` hit
the cache and only one reached the underlying function.

The consequence is that priming must pass the instance explicitly — priming
`get_category` for category `cid` on service `svc` means keying on `(svc, cid)`. Any
implementation that omits the instance writes an entry the accessor will never find.

**Rationale**: The key shape is an internal detail of the utility. Duplicating its
construction at the call site would give it two definitions that can drift silently —
and a drifted key fails open, quietly costing a read rather than raising. Building the
key in one place means the wrapper and the primer cannot disagree.

**Alternatives considered**: Reconstructing the key at each call site — rejected, DRY
violation with a silent failure mode.

---

## R2 — Typing the insert path under `mypy --strict` without `Any`

**Decision**: A module-level `prime(func, value, *args, **kwargs)` helper, typed
`Callable[Concatenate[R, P], None]`-style via a positional-only `value` ahead of `P`.
The decorator's return type stays `Callable[P, R]`, exactly as today.

**Findings** (both prototyped and type-checked before committing to the approach):

The obvious approach — widening the decorator's return type to a `Protocol` carrying
`__call__`, `clear_cache` and `prime` — **does not work**. A Protocol attribute is not a
descriptor, so mypy stops binding the method: `self.get_category(cid)` is then checked
against `__call__(self, category_id)` with the instance unconsumed, producing
`Missing positional argument "category_id"` and
`Argument 1 has incompatible type "Service"; expected …`. Verified, two errors.

The working shape keeps the decorator signature unchanged and reaches the cache through
a module-level helper:

```python
def prime(func: Callable[P, R], value: R, /, *args: P.args, **kwargs: P.kwargs) -> None
```

Called as `prime(TaxomeshService.get_category, category, self, category_id)` — the
*unbound* function supplies `P` and `R`, so mypy checks the primed value against the
accessor's real return type and the arguments against its real signature. A prototype of
this shape passes `mypy --strict` with **no errors and no `Any`**, and behaves correctly
at runtime (a primed call produced no cache miss).

**Rationale**: Type safety at the call site is the point — priming a `Category` into
`get_item`'s cache, or keying on the wrong argument, is exactly the class of bug that
would otherwise surface as a silent extra read. `Concatenate` buys that for free.

**Alternatives considered**:
- Protocol return type — rejected, breaks method binding (measured above).
- `wrapper.prime` accessed directly with `# type: ignore[attr-defined]` at each call
  site — rejected, spreads suppressions into `service.py` and gives up argument checking.
- Untyped `*args: Any` — rejected; Principle IV forbids `Any` without justification, and
  here a justification does not exist because a typed alternative works.

---

## R3 — Asserting a read count of zero across all four backends

**Decision**: Django asserts with `CaptureQueriesContext`; the file and in-memory
backends assert with a counting spy at the repository boundary. Both already exist in
the suite from 060.

**Rationale**: 060 established both mechanisms and they agreed exactly on every row when
the consumer cross-checked them. Reusing them keeps the new assertions comparable with
the existing gates rather than introducing a third notion of "a read".

**Alternatives considered**: Timing-based assertions — rejected, non-deterministic and
unable to distinguish a cache hit from a fast query.

---

## R4 — Why eviction is not bundled

**Decision**: Out of scope. Recorded as follow-up.

**Rationale**: The cache has no eviction and no size cap today — `cache[key] = (now,
result)` is its only write, and an expired entry never accessed again is never
reclaimed. That is a pre-existing property, not one this feature introduces, and
priming categories does not make it material: 93 entries at 0.17 MB measured.

It *would* be material on the item path, which is precisely why the item path is
excluded (see the spec's "Why categories only": 108 MB measured, reachable through a
public unauthenticated endpoint). Adding an LRU is the right long-term answer and is
what would unblock item priming, but it touches all nine memoized reads and needs its
own regression gates. Bundling it would put a measured, urgent fix behind unrelated
risk.

**Alternatives considered**: Adding a size cap now and priming both paths — rejected on
sequencing, not on merit.
