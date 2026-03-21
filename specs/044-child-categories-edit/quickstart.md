# Quickstart: Admin Child Categories Editable Inline (044)

## What Changes

The "Child categories" section on the Django admin Category change page becomes fully editable,
mirroring the existing "Parent categories" section. Admins can now:

- Add a new child category link (with searchable autocomplete selector + sort index)
- Edit the sort index of an existing child link
- Remove an existing child link

No migration is required. No new URL or model is introduced.

## Files Affected

| File | Change |
|------|--------|
| `taxomesh/contrib/django/admin.py` | Add `CategoryChildLinkForm`; replace read-only `CategoryChildLinkInline` with editable version |
| `tests/contrib/django/test_admin.py` | Replace/extend `TestCategoryChildLinkInline` with tests covering add, edit, delete, cycle validation, and duplicate validation |

## Validation Behaviour

| User action | Expected result |
|-------------|-----------------|
| Add a valid child link | Link created; child appears in section on reload |
| Add a duplicate child link | Form error on `category` field: "This category is already a child" |
| Add a link that creates a DAG cycle | Form error on `category` field: cycle description |
| Delete an existing child link | Link removed; child disappears from section on reload |
| Edit sort index of existing child link | New sort index persisted |
| Add a child link without sort index | Defaults to 0; link created |

## Running Tests

```bash
pytest tests/contrib/django/test_admin.py -k "ChildLink" -v
```

Full quality gates:

```bash
ruff check .
ruff format --check .
mypy --strict .
pytest --cov=taxomesh --cov-fail-under=80
```
