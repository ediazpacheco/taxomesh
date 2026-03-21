# Quickstart: Admin Child Categories Display

**Feature**: 042-admin-child-categories

## What changes

One new class in `taxomesh/contrib/django/admin.py`, and one line added to `CategoryModelAdmin.inlines`.

## After implementation

Open the Django admin change view for any category:

```
/taxomesh_contrib_django/categorymodel/<uuid>/change/
```

You will see:

- **Parent categories** — existing editable inline (unchanged)
- **Child categories** — new read-only inline listing all categories that reference this one as a parent

The child categories section is display-only. To modify which categories are children, open the child category's own change page and edit its "Parent categories" inline.

## No migration needed

Run the existing test suite to verify:

```bash
pytest tests/contrib/django/test_admin.py -v
```
