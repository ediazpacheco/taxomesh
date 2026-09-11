# Contract: the cache insert path

`taxomesh/utils/memoize.py` gains one public function. Nothing else in the module's
surface changes, and `memoize`'s own signature and return type are unchanged.

## `prime(func, value, /, *args, **kwargs) -> None`

Insert `value` as the cached result of calling `func` with `*args, **kwargs`, so that a
subsequent identical call is served without invoking `func`.

**Typing**: `func: Callable[P, R]`, `value: R`, then `*args: P.args, **kwargs: P.kwargs`.
The value is checked against the function's real return type and the arguments against
its real signature — priming the wrong type, or keying on the wrong arguments, is a
type error rather than a silent extra read. Verified to pass `mypy --strict` with no
`Any` (research.md R2).

**Call shape for a decorated method**: pass the *unbound* function and the instance
explicitly.

```python
prime(TaxomeshService.get_category, category, self, category.category_id)
```

### Guarantees

| Condition | Behaviour |
|---|---|
| `func` is memoized | Entry written, keyed exactly as a real call would key it. |
| `func` is not memoized | No-op. Never raises. |
| Arguments are unhashable | No-op, matching the wrapper's own behaviour for the same arguments. Never raises. |
| Called twice for the same key | Idempotent in effect. The second write refreshes the timestamp, exactly as a second real call would. |
| A write occurs afterwards | Entry cleared by `clear_all_caches()`, exactly as a normally cached entry. |
| TTL elapses | Entry refreshed on next access, exactly as a normally cached entry. |

### Non-guarantees, stated so they are not assumed

- **Does not create entries for rows that were not read.** Priming inserts what the
  caller passes; a row absent from a batch is absent from the cache, so a later lookup
  of it still misses and still raises `TaxomeshCategoryNotFoundError` (FR-004).
- **Does not bound the cache.** There is no eviction and no size cap, before or after
  this change. Callers are responsible for not priming unbounded result sets — which is
  why the item path does not prime (FR-007).
- **Does not add an invalidation path.** Wholesale clearing on write remains the only
  one.

## Service-layer call sites

| Method | Primes | Rows |
|---|---|---|
| `list_categories(parent_id=…)` | `get_category`, from the batch it already fetched | children of one parent |
| `list_categories_by_item(item_id)` | `get_category`, from the batch it already fetched | categories holding one item |
| `list_items(category_id=…)` | **nothing** | — |

No signature, return type or exception changes at any of the three. A single cold call
to any of them costs exactly what it costs on `0.1.0a50`, because priming writes to a
dict and reads nothing (FR-005).
