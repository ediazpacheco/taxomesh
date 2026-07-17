# Phase 0 Research: Atomic Multi-Write Service Operations

The spec's approach was pre-decided; research here confirms the two mechanisms
that carry correctness risk and pins the mypy-strict typing approach.

## Decision 1 — Django nested `transaction.atomic` = savepoints that roll back together

**Decision**: The outer `with self._repo.atomic():` maps to
`transaction.atomic(using=self._using)`. The existing per-method
`transaction.atomic(using=self._using)` blocks are left in place and become
**savepoints** nested inside the outer transaction.

**Rationale**: Django's `atomic()` is reentrant. The outermost block opens a real
database transaction; each inner block opens a savepoint. If any inner block
propagates an exception past the outer block, the whole outer transaction is
rolled back — no partial writes commit. Critically, when an inner block itself
catches a `DatabaseError`/`IntegrityError` and re-raises (as taxomesh adapters
do, translating to `TaxomeshExternalIdConflictError` / `TaxomeshRepositoryError`),
the exception still propagates out of the outer block unless the service
swallows it — and the service does not. So the outer transaction rolls back.

**Gotcha handled**: After an `IntegrityError` inside an atomic block, Django
forbids further queries in that transaction until the savepoint unwinds. Because
each write's own inner `atomic` wraps a savepoint, the erroring savepoint unwinds
as the exception leaves that inner block; the service performs no further repo
calls after the raising write (the exception propagates straight to the outer
`with`), so no "broken transaction" query is attempted. Verified by the
failure-injection tests (Django parametrization) asserting an unchanged datastore.

**Alternatives considered**:
- *Remove inner per-method atomic blocks, rely only on the outer one*: rejected —
  it would change the atomicity guarantee of those methods when called
  standalone (outside the five operations) and is explicitly out of scope
  ("verify this nesting works, don't remove the inner blocks").
- *Manual savepoint API (`transaction.savepoint()` / `savepoint_rollback()`)*:
  rejected — reimplements what nested `atomic()` already provides; more code, more
  risk, no benefit.

## Decision 2 — Best-effort no-op for file/in-memory backends via `contextlib.nullcontext`

**Decision**: `JsonRepository`, `YAMLRepository`, and the test `InMemoryRepository`
implement `atomic()` as `return contextlib.nullcontext()`.

**Rationale**: These backends have no transaction primitive. A no-op context
manager satisfies the port, never alters the success path, and makes the
best-effort limitation explicit and honest (documented in the `atomic()`
docstring per FR-008). `nullcontext()` yields `None`, matching
`AbstractContextManager[None]`.

**Alternatives considered**:
- *Snapshot-and-restore the whole file on failure*: rejected — this feature is
  scoped to L2 via a context manager only; snapshotting is a different (heavier)
  mechanism the spec explicitly excludes, and it would create a false impression
  of transactional guarantees these backends don't otherwise provide.

## Decision 3 — mypy `--strict` typing of the return

**Decision**: Annotate the port method and every implementation as returning
`contextlib.AbstractContextManager[None]`. For Django, the return
`transaction.atomic(using=self._using)` comes from an untyped import
(`# type: ignore[import-untyped]` is already the project convention for Django);
add a localized `# type: ignore` (or `cast`) only if mypy flags the untyped
value, mirroring existing Django-adapter ignores. JSON/YAML/in-memory return
`nullcontext()`, which mypy already types as
`AbstractContextManager[None]` — no ignore needed.

**Rationale**: `AbstractContextManager[None]` is the precise structural type for
"an object usable in a `with` block that yields nothing." It keeps the port
free of any Django/`transaction` import (Principle I) while remaining strict.

**Alternatives considered**:
- *`Iterator[None]` + `@contextmanager`*: rejected — the adapters already have
  ready-made context managers (`transaction.atomic`, `nullcontext`); wrapping
  them in a generator adds indirection for no gain.
- *`typing.ContextManager`*: rejected — deprecated alias; `contextlib.AbstractContextManager`
  is the current spelling and subscriptable on py311.

## Decision 4 — Boundary scope + error-wrapping placement in the service

**Decision**: The `with self._repo.atomic():` block **and** the `try/except`
enclose the **write sequence only**. All *pre-write* work — argument validation,
existence checks, domain reads, and `pydantic` model construction — stays
**outside** the boundary. Structure per method:

```text
<pre-write validation / reads / model construction>   # OUTSIDE — unchanged
try:
    with self._repo.atomic():
        <the repository mutations only>
except TaxomeshError:
    raise                      # already library-owned → propagate unchanged
except Exception as exc:       # raw backend/other error escaped the boundary
    raise TaxomeshRepositoryError(str(exc)) from exc
<clear_all_caches() / corpus reset / return>          # OUTSIDE — success path
```

**Why writes-only scope is mandatory (fixes analysis finding C1)**: Several of
the five operations raise **non-`TaxomeshError`** exceptions from their
*pre-write* validation:

- `create_category` constructs a `Category` (`pydantic.ValidationError`) and its
  docstring documents `Raises: pydantic.ValidationError`.
- `reorder_subcategories` and `reorder_items_in_category` raise a **builtin
  `ValueError`** ("… is not a child of …" / "… is not placed in category …").

If those validations sat *inside* the `try`, the `except Exception` arm would
convert them to `TaxomeshRepositoryError`, silently breaking each method's
documented `Raises:` contract and the existing tests — a direct violation of
FR-007 / User Story 2. Keeping validation outside preserves current behavior
exactly. Validation also has no business running inside a DB transaction.

**Per-method boundary contents** (mutations that go *inside* the `with`):

| Operation | Inside the boundary |
|---|---|
| `create_category` | `save_category` → `save_category_parent_link` |
| `reorder_subcategories` | the `save_category_parent_link` loop |
| `reorder_items_in_category` | the `save_item_parent_link` loop |
| `reparent_category` | `delete_category_parent_link` → `add_category_parent` (cycle check + save) → `save_category_parent_link` loop |
| `reparent_item` | `delete_item_parent_link` → `save_item_parent_link` loop |

Note `reparent_category` keeps `add_category_parent` (and thus domain cycle
detection) **inside** the boundary on purpose: a `TaxomeshCyclicDependencyError`
must roll back the preceding `delete_category_parent_link`. Because it is a
`TaxomeshError`, it propagates unchanged while Django still rolls back.

**Rationale**: Satisfies FR-011 — raw backend exception types never leak from the
mutation phase, the original is chained via `from exc`, and existing
`TaxomeshError` subclasses keep their exact current propagation, so User Story 2
holds. On Django the rollback has already happened by the time control reaches
the `except` (the outer `atomic` unwinds on the way out).

**Alternatives considered**:
- *Wrap the whole method body*: rejected — see C1 above; converts pre-write
  `ValueError`/`ValidationError` and breaks documented contracts + tests.
- *Wrap all escaping exceptions* (including `TaxomeshError`): rejected in
  planning Q&A — it would bury `TaxomeshDuplicateSlugError` as a `__cause__` and
  break current callers/tests.
- *No wrapping, rely on per-method translation only*: rejected — a raw error
  from a mutation without per-method translation could still leak; FR-011
  requires the guarantee at the operation boundary.

## Open questions

None. All NEEDS CLARIFICATION resolved.
