# Data Model: Feature 026

## Entities Changed

### TaxomeshService (application/service.py)

No new domain entities. Changes are additions to the existing service facade.

**New attributes on `TaxomeshService`**:

| Attribute | Type | Set at | Description |
|-----------|------|--------|-------------|
| `_config_name` | `str \| None` | `__init__` | Name of the active TOML config, or `None` if no config file was used |

**New / changed methods**:

| Method | Change | Notes |
|--------|--------|-------|
| `create_category(name, description, metadata, slug, external_id)` | Add `external_id: str = ""` parameter | Passed through to `Category(external_id=external_id)` at construction |
| `update_category(category_id, name, description, slug, metadata, external_id)` | Add `external_id: str \| None = None` parameter | `None` → no-op; `""` → explicit clear |
| `list_categories(*, parent_id, external_id)` | Add `external_id: str \| None = None` parameter | When non-None, delegates to `_repo.list_categories_by_external_id(external_id)` then optionally intersects with `parent_id` filter |
| `get_debug()` | New method | Returns `dict[str, Any]` (see contract below) |

---

### TaxomeshRepositoryBase Protocol (ports/repository.py)

**New method added to the Protocol**:

| Method | Return type | Description |
|--------|-------------|-------------|
| `get_debug_info()` | `dict[str, Any]` | Returns adapter-specific storage information for diagnostic purposes |

Each adapter's returned dict keys:

| Adapter | Key | Value |
|---------|-----|-------|
| `JsonRepository` | `path` | `str` — absolute or relative path to the JSON file |
| `YamlRepository` | `path` | `str` — absolute or relative path to the YAML file |
| `DjangoRepository` | `database_alias` | `str` — Django database alias (default: `"default"`) |

---

### Django Admin (contrib/django/admin.py)

**New setting constant**:

| Constant | Value | Description |
|----------|-------|-------------|
| `TAXOMESH_CATEGORY_LINKED_MODEL_SETTING` | `"TAXOMESH_CATEGORY_LINKED_MODEL"` | Django settings key for category-specific linked-model resolution |

**New proxy model** (no migration required):

| Attribute | Value |
|-----------|-------|
| Class name | `TaxomeshDebugProxy` |
| Base | `CategoryModel` |
| `proxy` | `True` |
| `verbose_name` | `"Debug"` |
| `verbose_name_plural` | `"Debug"` |
| `app_label` | `APP_LABEL` (`"taxomesh_contrib_django"`) |

**New list filters**:

| Class | Registered on | Filter choices |
|-------|---------------|----------------|
| `HasLinkedObjectListFilter` | `CategoryModelAdmin.list_filter` | "Has linked object" / "No linked object" |
| `TaxomeshCategoryListFilter` | `ItemCategoryAssignmentMixin` default `list_filter` | All non-root taxomesh categories by name |

---

## get_debug() Contract

```
{
  "version":         str,        # installed taxomesh version from package metadata
  "config_name":     str | None, # TOML config name if loaded, else None
  "repository_type": str,        # class name of the active repository adapter
  "working_path":    str | None, # file path (JSON/YAML) or None (Django ORM)
  "repository_info": dict        # adapter-specific extras from get_debug_info()
}
```

---

## State Transitions

### update_category external_id semantics

| `external_id` argument value | Effect on stored `external_id` |
|------------------------------|--------------------------------|
| `None` (default) | Unchanged — no write |
| `""` (empty string) | Cleared to `""` — explicit update |
| `"some-value"` | Set to `"some-value"` |

This mirrors the existing `None`-as-no-op convention used by `name`, `description`, `slug`, and `metadata` parameters.

---

## Files Affected

| File | Type of change |
|------|---------------|
| `taxomesh/ports/repository.py` | Add `get_debug_info()` to Protocol |
| `taxomesh/application/service.py` | Add `_config_name`, update 3 methods, add `get_debug()` |
| `taxomesh/adapters/repositories/json_repository.py` | Implement `get_debug_info()` |
| `taxomesh/adapters/repositories/yaml_repository.py` | Implement `get_debug_info()` |
| `taxomesh/adapters/repositories/django_repository.py` | Implement `get_debug_info()` |
| `taxomesh/adapters/cli/main.py` | Change `show_relations` default to `True` |
| `taxomesh/contrib/django/admin.py` | New constant, proxy model, admin class, search_fields, list_filter, linked_object_url |
| `tests/service/test_service_categories.py` | Tests for new `create_category`/`update_category`/`list_categories` params |
| `tests/service/test_service_config.py` | Tests for `get_debug()` |
| `tests/contrib/django/test_admin.py` | Tests for UUID search, linked object, filters |
| `tests/contrib/django/test_admin_graph.py` | Tests for show-relations default in admin |
| `tests/adapters/cli/test_graph_output.py` | Tests for show-relations default in CLI |
