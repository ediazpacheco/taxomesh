# Quickstart: Atomic Multi-Write Service Operations

## What changes for consumers

Nothing in the API surface. The five multi-write operations keep their exact
signatures and return types. The only observable difference is on failure:

- **On a transactional backend (Django)**: if one of these operations fails
  part-way, the datastore is left untouched — no orphaned category, no
  half-applied reorder or reparent.
- **On file/in-memory backends (JSON, YAML)**: the boundary is a best-effort
  no-op; a mid-operation failure may still leave partial state. This is a
  documented, accepted limitation of those backends.

Raw backend exceptions never leak from these operations: a raw error is
re-raised as `TaxomeshRepositoryError` (with the original chained as its cause);
existing `TaxomeshError` types (e.g. `TaxomeshDuplicateSlugError`) are unchanged.

## Custom backend authors

If you implement your own repository (structural `TaxomeshRepositoryBase`), add:

```python
from contextlib import AbstractContextManager, nullcontext

class MyRepository:
    ...
    def atomic(self) -> AbstractContextManager[None]:
        """Consistency boundary for a multi-write service operation.

        Return your backend's transaction context manager for full rollback,
        or ``contextlib.nullcontext()`` for best-effort (no-op) semantics.
        """
        return nullcontext()  # or: my_transaction_manager()
```

Without `atomic()`, the five multi-write operations will fail with `AttributeError`.

## Verifying the guarantee (Django)

```python
# Force the parent-link write to fail after the category is saved.
# On Django, create_category leaves NO category behind.
import pytest
from taxomesh.exceptions import TaxomeshRepositoryError

with pytest.raises(TaxomeshError):          # raw failure surfaces as a TaxomeshError
    service.create_category(name="Orphan?")

assert service.list_categories() == before  # datastore unchanged — full rollback
```

## Running the checks

```bash
ruff check .
ruff format --check .
mypy --strict .
pytest --cov=taxomesh --cov-fail-under=80
# Django rollback tests require pytest-django + the django extra:
#   uv sync --extra dev --extra django --python 3.12
```
