# Contract: `TaxomeshRepositoryBase.atomic()`

The single new method on the repository port. This is the entire public
mechanism for operation-level (L2) atomicity.

## Signature

```python
from contextlib import AbstractContextManager

def atomic(self) -> AbstractContextManager[None]:
    ...
```

## Behavioral contract

- Returns a context manager usable as `with repo.atomic():`.
- Entering the context MUST NOT raise.
- On normal exit, the wrapped writes are made durable per the backend's normal
  semantics.
- On exceptional exit, the context manager MUST propagate the exception. A
  **transactional** backend MUST additionally roll back every write performed
  within the boundary (including nested inner boundaries), leaving the datastore
  in its pre-boundary state.
- A **non-transactional** backend (file/in-memory) MUST treat the boundary as a
  best-effort no-op: it never alters the success path, and after a mid-boundary
  failure partial state MAY remain. This limitation MUST be documented in the
  method's docstring.
- `atomic()` MUST be re-usable/reentrant to the extent the backend's own writes
  already open their per-method boundaries (Django: inner `atomic` blocks nest as
  savepoints).

## Per-adapter implementations

| Adapter | Implementation | Guarantee |
|---|---|---|
| `DjangoRepository` | `return transaction.atomic(using=self._using)` | Full rollback |
| `JsonRepository` | `return contextlib.nullcontext()` | Best-effort (no-op) |
| `YAMLRepository` | `return contextlib.nullcontext()` | Best-effort (no-op) |
| `InMemoryRepository` (test) | `return contextlib.nullcontext()` | Best-effort (no-op) |

## Caller contract (service)

Each of the five multi-write operations wraps **only its write sequence** —
pre-write validation, reads, and model construction stay outside the boundary:

```python
...  # pre-write validation / reads / model construction — OUTSIDE, unchanged
try:
    with self._repo.atomic():
        ...  # the repository mutations only
except TaxomeshError:
    raise
except Exception as exc:
    raise TaxomeshRepositoryError(str(exc)) from exc
...  # clear_all_caches() / corpus reset / return — OUTSIDE, success path
```

- Existing `TaxomeshError` subclasses propagate unchanged.
- Raw (non-`TaxomeshError`) exceptions from the mutation phase are re-raised as
  `TaxomeshRepositoryError` with the original chained as `__cause__`.
- Pre-write `pydantic.ValidationError` (`create_category`) and builtin
  `ValueError` (`reorder_*`) stay outside the boundary and are **not** wrapped —
  their documented `Raises:` contracts are preserved.

## Verification

- **Django (transactional)**: force the Nth write of each operation to raise;
  assert the datastore equals its pre-operation snapshot (no orphan, no partial
  reorder/reparent) and that the caller sees a `TaxomeshError` (raw types never
  leak).
- **File/in-memory (best-effort)**: assert `atomic()` returns a working no-op
  context manager and that success-path behavior is identical to today.
