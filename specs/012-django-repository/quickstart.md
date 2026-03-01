# Quickstart: Django Repository

**Branch**: `012-django-repository` | **Date**: 2026-02-28

This guide shows a Django developer how to integrate taxomesh with their existing Django
project using the ORM-backed `DjangoRepository`.

---

## Prerequisites

- Python 3.11+
- Django 4.2+
- taxomesh installed with the `django` extra

---

## Step 1: Install

```bash
pip install "taxomesh[django]"
```

---

## Step 2: Add to INSTALLED_APPS

In your Django project's `settings.py`:

```python
INSTALLED_APPS = [
    # ... your existing apps ...
    "taxomesh.contrib.django",
]
```

---

## Step 3: Run Migrations

```bash
python manage.py migrate
```

This creates six tables in your database:

```
taxomesh_category
taxomesh_item
taxomesh_tag
taxomesh_category_parent_link
taxomesh_item_parent_link
taxomesh_item_tag_link
```

---

## Step 4: Use DjangoRepository

```python
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.django_repository import DjangoRepository

# Uses Django's "default" database alias
svc = TaxomeshService(repository=DjangoRepository())

# Create a category
books = svc.create_category("Books")
print(books.category_id)  # UUID

# Create a child category
fiction = svc.create_category("Fiction", parent_id=books.category_id)

# Create an item (e.g., your app's primary key)
item = svc.create_item(external_id=42)  # int, str, or UUID all work

# Place the item in a category
svc.place_item(item.item_id, fiction.category_id)

# Build the graph
graph = svc.get_graph()
print(graph.roots)
```

---

## Step 5: Use a Non-Default Database (optional)

If your taxonomy lives in a separate database alias:

```python
repo = DjangoRepository(using="taxonomy_db")
svc = TaxomeshService(repository=repo)
```

Ensure `"taxonomy_db"` is configured in `DATABASES` in your settings.

---

## Step 6: Configure via taxomesh.toml (optional)

Create `taxomesh.toml` in your project root:

```toml
[repository]
type = "django"
using = "default"   # optional; defaults to "default"
```

Then construct the service without arguments — it auto-discovers the config:

```python
svc = TaxomeshService()  # reads taxomesh.toml → constructs DjangoRepository
```

---

## Step 7: Django Admin (optional)

All six taxomesh models are registered in the admin automatically. Visit `/admin/` and look
for the **Taxomesh Contrib Django** section.

---

## Verification

```bash
# Confirm no pending migrations
python manage.py makemigrations --check taxomesh_contrib_django

# Run taxomesh tests (requires pytest-django)
pytest tests/contrib/django/ -v
```

---

## What Gets Stored Where

| Domain object | Django admin section | DB table |
|---|---|---|
| `Category` | Category Models | `taxomesh_category` |
| `Item` | Item Models | `taxomesh_item` |
| `Tag` | Tag Models | `taxomesh_tag` |
| Category parent links | Category Parent Link Models | `taxomesh_category_parent_link` |
| Item placements | Item Parent Link Models | `taxomesh_item_parent_link` |
| Tag–item associations | Item Tag Link Models | `taxomesh_item_tag_link` |

---

## Switching Backends

Changing from YAML to Django requires changing exactly one constructor argument:

```python
# Before (YAML)
from taxomesh.adapters.repositories.yaml_repository import YAMLRepository
svc = TaxomeshService(repository=YAMLRepository("taxomesh.yaml"))

# After (Django ORM)
from taxomesh.adapters.repositories.django_repository import DjangoRepository
svc = TaxomeshService(repository=DjangoRepository())
```

All domain logic, categories, items, and tags work identically regardless of backend.
