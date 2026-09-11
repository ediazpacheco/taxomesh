# Quickstart: Safe HTTP 500 response bodies

**Feature**: 059-safe-error-bodies

## What changed for a consuming application

Before, a storage failure told the client what broke:

```python
status, body = to_tuple(exc)
# (500, {"detail": 'duplicate key value violates unique constraint "taxomesh_item_external_id_key"'})
```

After, it does not:

```python
status, body = to_tuple(exc)
# (500, {"detail": "An internal error occurred."})
```

Client errors are untouched:

```python
status, body = to_tuple(TaxomeshDuplicateSlugError("slug 'jazz' already exists"))
# (409, {"detail": "slug 'jazz' already exists"})
```

## Getting the detail back

It is not gone, it moved. Attach a handler anywhere on the `taxomesh` logger tree:

```python
import logging

logging.getLogger("taxomesh").addHandler(logging.StreamHandler())
logging.getLogger("taxomesh").setLevel(logging.ERROR)
```

Now the same failure produces, on the server:

```text
Mapping a taxomesh error to HTTP 500
Traceback (most recent call last):
  ...
django.db.utils.IntegrityError: duplicate key value violates unique constraint ...
```

An application that configures no logging still sees nothing — the `NullHandler`
registered at import keeps taxomesh silent by default.

## If you compared against the 500 body

Compare against the constant instead of a literal:

```python
from taxomesh.contrib.api.errors import GENERIC_SERVER_ERROR_DETAIL

if status == 500:
    assert body["detail"] == GENERIC_SERVER_ERROR_DETAIL
```

Better: branch on the status code. That was always the contract; the body text never
was.

## Verifying the change locally

```bash
uv run pytest tests/contrib/test_api_errors.py -v
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy --strict .
```

The mapping's exhaustiveness guard in `tests/contrib/test_api_errors.py` will fail if a
new `TaxomeshError` subclass is added without a decision about its status, so adding an
exception type cannot silently change what clients receive.
