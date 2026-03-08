# Quickstart: Feature 026 — Admin & Service Improvements

## 1. Category external_id via TaxomeshService

```python
from taxomesh import TaxomeshService

service = TaxomeshService()

# Create a category with an external_id
genre = service.create_category(name="Fiction", external_id="genre-42")
assert genre.external_id == "genre-42"

# Update a category's external_id
service.update_category(genre.category_id, external_id="genre-99")

# Clear a category's external_id
service.update_category(genre.category_id, external_id="")

# List categories filtered by external_id
matches = service.list_categories(external_id="genre-99")
```

## 2. Diagnostic info

```python
info = service.get_debug()
# {
#   "version":         "0.1.0a12",
#   "config_name":     "My Taxonomy",
#   "repository_type": "YamlRepository",
#   "working_path":    "data/taxomesh.yaml",
#   "repository_info": {"path": "data/taxomesh.yaml"}
# }
```

## 3. Category linked object in Django admin

```python
# settings.py
TAXOMESH_LINKED_MODEL = "content.Content"           # for Item.external_id links
TAXOMESH_CATEGORY_LINKED_MODEL = "content.Genre"    # for Category.external_id links
```

With `TAXOMESH_CATEGORY_LINKED_MODEL` set, the Category admin list displays a `↗` icon that navigates to the linked `Genre` admin change page when `external_id` is non-empty.

## 4. Partial UUID search in admin

Navigate to `/admin/taxomesh_contrib_django/categorymodel/` and type any UUID substring (e.g. `2b0bf7ef6646`) in the search box. Results include categories and items whose UUID contains that substring.

## 5. Integration filter in external model admin

```python
# myapp/admin.py
from taxomesh.contrib.django.admin import ItemCategoryAssignmentMixin

@admin.register(Content)
class ContentAdmin(ItemCategoryAssignmentMixin, ModelAdmin):
    taxomesh_external_id_attr = "pk"
    # TaxomeshCategoryListFilter is included automatically in list_filter
```

The Content list admin will show a "Taxomesh Category" filter sidebar for narrowing by category.

## 6. CLI graph with relations visible by default

```bash
taxomesh graph                   # relations shown (new default)
taxomesh graph --no-show-relations  # opt-out
```

## 7. Debug page in admin

Visit `/admin/taxomesh_contrib_django/taxomeshdebugproxy/` (or click "Debug" under the TAXOMESH section on the admin home page) to see the current taxomesh version, config, repository type, and storage path.
