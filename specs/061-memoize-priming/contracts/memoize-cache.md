# Contract: the caching utility

`taxomesh/utils/memoize.py` changes shape. `memoize(ttl)` keeps its name and its call
syntax — textually unchanged at all 16 service decoration sites and for a consumer's own
decorated functions — but returns a typed callable object instead of a plain function.

**Removed**: the module-level `prime(func, value, /, *args, **kwargs)` helper added in
`238cd12`. It reached the cache through `getattr` plus a `cast`, defeating the argument
checking it existed to provide, and NFR-005 forbids a new module-level function with side
effects. It was never released (`main` is `0.1.0a50`), so nothing depends on it.

**Unchanged**: `clear_all_caches()`, the module-level registry behind it, and the key shape.

## Public surface

| Name | Kind | Role |
|---|---|---|
| `memoize(ttl)` | function | Decorator factory. Returns `MemoizedFunction[P, R]`. |
| `MemoizedFunction[**P, R]` | class | The decorated callable. A descriptor, so it binds as a method. |
| `MemoizedMethod[**P, R]` | class | A `MemoizedFunction` accessed through an instance. |
| `Miss` | class | Singleton type for "no fresh entry". |
| `clear_all_caches()` | function | Unchanged. |

## Operations

All four are available on both `MemoizedFunction` and `MemoizedMethod`, typed against the
decorated callable's own parameters `P` and return type `R`. On `MemoizedMethod` the bound
instance is supplied automatically, so a call site never passes it.

### `__call__(*args: P.args, **kwargs: P.kwargs) -> R`

Unchanged behaviour. Serves a fresh entry if one exists; otherwise calls the function and
stores the result with the current timestamp.

### `prime(value: R, /, *args: P.args, **kwargs: P.kwargs) -> None`

Insert `value` as the cached result of calling with `*args, **kwargs`, so a subsequent
identical call is served without invoking the function. `value` is checked against the
function's real return type and the arguments against its real signature — priming the
wrong type, or keying on the wrong arguments, is a type error rather than a silent extra
read.

```python
self.get_category.prime(category, category_id)   # bound: no explicit instance
```

### `cached(*args: P.args, **kwargs: P.kwargs) -> R | Miss`

Return the fresh cached value for those arguments, or the `Miss` singleton. **Strictly
read-only**: it never writes, refreshes or evicts an entry. This is what keeps a
read-through hit from extending an entry's lifetime (FR-003, FR-004).

```python
hit = self.get_category.cached(category_id)
if isinstance(hit, Miss):
    ...                       # fetch it
else:
    found[category_id] = hit  # narrowed to Category
```

A stale entry is reported as a miss. The `Miss` sentinel rather than `None` is what lets a
caller distinguish a miss from a cached value that is itself `None` or falsy (FR-001).

### `clear_cache() -> None`

Unchanged. Empties this callable's cache only.

## Guarantees

| Condition | Behaviour |
|---|---|
| Arguments are unhashable | `prime` and `cached` are no-ops — `cached` reports a miss — matching the call path's own behaviour for the same arguments. Never raises. |
| `prime` called twice for the same key | Idempotent in effect; the second write overwrites. |
| A read-through hit | Timestamp untouched. Expiry stays measured from the fetch. |
| A write occurs afterwards | Entry cleared by `clear_all_caches()`, exactly as a normally cached entry. |
| TTL elapses | Entry reported as a miss by `cached`, and re-fetched by a call. |
| Decorated callable's identity | `__name__`, `__qualname__`, `__module__`, `__doc__` and `__wrapped__` are the decorated callable's own, so `help()` and `inspect.signature` behave as they do today (NFR-003). |

## Non-guarantees, stated so they are not assumed

- **No entry for a row that was not read.** `prime` inserts what the caller passes; a row
  absent from a batch is absent from the cache, so a later lookup still misses and still
  raises `TaxomeshCategoryNotFoundError` with the same message (FR-005).
- **No bound on the cache.** No eviction, no size cap, before or after this change. Callers
  are responsible for not priming unbounded result sets — which is why the item path does
  neither (FR-007).
- **No new invalidation path.** Wholesale clearing on write remains the only one.
- **No negative caching.** A miss is never stored as a miss.

## Service-layer call sites

| Method | Primes | Reads through | Rows |
|---|---|---|---|
| `list_categories(parent_id=…)` | `get_category` | ✅ | children of one parent |
| `list_categories_by_item(item_id)` | `get_category` | ✅ | categories holding one item |
| `list_items(category_id=…)` | **nothing** | **no** | — |

No signature, return type or exception changes at any of the three. A single cold call to
any of them costs exactly what it costs on `0.1.0a50` — every id misses, so there is
exactly one batch read — which is why 060's exact-constant gates pass unmodified (FR-006).
