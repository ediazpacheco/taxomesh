# Phase 1 Data Model: Atomic Multi-Write Service Operations

This feature introduces **no new domain models** and **no schema/migration
changes**. It adds one behavioral contract to the repository port and reuses an
existing exception. The "entities" below are contracts and behaviors, not
persisted data.

## Port capability (new)

### `TaxomeshRepositoryBase.atomic()`

| Aspect | Value |
|---|---|
| Signature | `def atomic(self) -> AbstractContextManager[None]: ...` |
| Location | `taxomesh/ports/repository.py` (Protocol method) |
| Semantics | Returns a context manager defining a per-backend consistency boundary around a sequence of writes. |
| Django | Returns `transaction.atomic(using=self._using)` — a rollback boundary; inner per-method `atomic` blocks nest as savepoints. |
| JSON / YAML / InMemory | Returns `contextlib.nullcontext()` — best-effort no-op; partial state may remain after a mid-operation failure. |
| Yields | `None` |
| Raises | Nothing on entry; on `__exit__`, propagates whatever the wrapped body raised (Django additionally performs rollback). |

## Reused exception (no new type)

### `TaxomeshRepositoryError`

- Already defined in `taxomesh/exceptions.py` (`TaxomeshError` → `TaxomeshRepositoryError`).
- Already mapped to HTTP 500 in `taxomesh/contrib/api/errors.py` — no mapping change.
- Reused as the wrapper for any **raw** (non-`TaxomeshError`) exception escaping
  an affected operation's consistency boundary. The original error is chained as
  `__cause__` via `raise ... from exc`.

## Affected service operations (behavior, unchanged orchestration)

Each is wrapped in `with self._repo.atomic():`; write sequences are unchanged.

| Operation | Write shape | Writes inside the boundary |
|---|---|---|
| `create_category` | fixed pair | `save_category` → `save_category_parent_link` |
| `reorder_subcategories` | loop | N × `save_category_parent_link` |
| `reorder_items_in_category` | loop | N × `save_item_parent_link` |
| `reparent_category` | delete + loop | `delete_category_parent_link` → `add_category_parent` (domain cycle check + save) → N × `save_category_parent_link` |
| `reparent_item` | delete + loop | `delete_item_parent_link` → N × `save_item_parent_link` |

**Invariant protected**: on a transactional backend, either *all* writes of an
operation commit or *none* do. Concretely: no category is ever persisted without
its parent link; no reorder/reparent is ever half-applied.

## Test doubles (must implement the new port method)

Any repository test double passed to `TaxomeshService` and exercised through one
of the five operations must provide `atomic()` (returning `nullcontext()`), plus
a dedicated **failure-injection** double whose Nth write raises mid-operation.

| Double | Change |
|---|---|
| `InMemoryRepository` (tests/service/conftest.py) | add `atomic()` → `nullcontext()` |
| Failure-injection repository (new, in tests) | wraps a real repo; raises on the Nth targeted write; delegates `atomic()` to the wrapped repo |
| Other in-test doubles passed to `TaxomeshService` | add `atomic()` where they reach an affected operation |
