# Research: Django CLI Compatibility and Admin Graph View

**Feature**: `015-django-cli-admin`
**Phase**: 0 — Research & unknowns resolution
**Date**: 2026-03-01

---

## R-001: When does Django raise `ImproperlyConfigured` during DjangoRepository init?

**Decision**: Catch `ImproperlyConfigured` as a broad `Exception` subtype inside a nested
try/except in `DjangoRepository.__init__`, immediately after the `ImportError` guard.

**Finding**: `ImproperlyConfigured` is raised during
`from taxomesh.contrib.django.models import CategoryModel ...` because:

1. `models.py` defines `CategoryModel(models.Model)`.
2. Django's `ModelBase.__new__` metaclass calls `Apps.register_model()` during class creation.
3. `register_model()` calls `self.check_apps_ready()`, which accesses `settings.INSTALLED_APPS`.
4. If `DJANGO_SETTINGS_MODULE` is not set, `LazySettings.__getattr__` raises
   `ImproperlyConfigured("Requested setting INSTALLED_APPS, but settings are not configured")`.

The error is therefore raised at import time of `CategoryModel`, not at query time.

**Interception pattern** (deferred import of `ImproperlyConfigured` to avoid module-level Django dependency):

```python
try:
    from taxomesh.contrib.django.models import (CategoryModel, ...)  # noqa: PLC0415
except ImportError as exc:
    raise TaxomeshRepositoryError("Django is not installed. Run: pip install taxomesh[django]") from exc
except Exception as exc:
    try:
        from django.core.exceptions import ImproperlyConfigured  # noqa: PLC0415
        if isinstance(exc, ImproperlyConfigured):
            raise TaxomeshRepositoryError(
                "Django settings are not configured. "
                "Set the DJANGO_SETTINGS_MODULE environment variable before running "
                "taxomesh with type = 'django'."
            ) from exc
    except ImportError:
        pass
    raise
```

**Alternatives considered**:
- Catching `Exception` broadly (without the inner isinstance check): fragile — could suppress genuine bugs.
- Checking `DJANGO_SETTINGS_MODULE` env var before the import: fragile — settings could be configured via `django.conf.settings.configure()` without the env var.
- Adding detection to `build()` in `cli/config.py`: would require reading TOML twice and
  adding Django-specific logic to a non-Django module; violates separation of concerns.

---

## R-002: Django admin custom URL + app index link — best practice for library authors

**Decision**: Override `CategoryModelAdmin.get_urls()` to add the graph URL; use a template
override (`app_index.html` in the app's template directory) to add the Graph link to the
app section index — no `AdminSite` subclassing.

**Finding**:

### URL registration
Django's `ModelAdmin.get_urls()` returns a list of URL patterns. The standard override pattern:

```python
def get_urls(self) -> list[URLPattern]:
    urls = super().get_urls()
    custom = [
        path(
            "graph/",
            self.admin_site.admin_view(self.graph_view),
            name="taxomesh_contrib_django_graph",
        )
    ]
    return custom + urls
```

`self.admin_site.admin_view()` wraps the view with Django's admin access control
(`is_staff`, active session, CSRF). The URL is rooted at the model's admin URL prefix:
`/admin/taxomesh_contrib_django/categorymodel/graph/`.

Wait — actually `ModelAdmin.get_urls()` produces URLs relative to the model's changelist URL.
For `CategoryModelAdmin` registered on `admin.site`, the changelist URL is
`/admin/taxomesh_contrib_django/categorymodel/`. So the graph view would be at
`/admin/taxomesh_contrib_django/categorymodel/graph/`.

**Alternative**: Register the URL at the app level (`/admin/taxomesh_contrib_django/graph/`)
by subclassing `AdminSite`. Rejected — requires consumers to replace `admin.site` with a
custom site, which is invasive.

**Revised decision**: Accept the URL path `/admin/taxomesh_contrib_django/categorymodel/graph/`
as the canonical graph URL. The app index template link uses `{% url 'admin:taxomesh_contrib_django_graph' %}`.

### App index link via template override

Django's template loader (with `APP_DIRS=True`, which is the Django default) discovers
templates in `<app>/templates/` directories. A template at:

```
taxomesh/contrib/django/templates/admin/taxomesh_contrib_django/app_index.html
```

overrides `admin/app_index.html` for the `taxomesh_contrib_django` app. This template
can extend `admin/app_index.html` and use `{% block content %}{{ block.super }}...{% endblock %}`
to append the Graph link after the existing model links.

**Note**: `APP_DIRS=True` is the default in `django-admin startproject` generated settings.
If a consumer uses a custom template loader (e.g., `loaders` key instead of `APP_DIRS`), they
must add `django.template.loaders.app_directories.Loader` manually. This is standard Django
behaviour and does not require special documentation for taxomesh.

---

## R-003: SUPPORTED_REPO_TYPES — placement and circular import safety

**Decision**: Define `SUPPORTED_REPO_TYPES` in `cli/config.py`.

**Finding**:

Import chain from `cli/config.py` importing `DJANGO_REPO_TYPE` from `django_repository.py`:

```
cli/config.py
  → taxomesh/__init__.py (for TaxomeshService)
      → taxomesh/application/service.py
          → taxomesh/domain/* (no adapter imports)
  → taxomesh/adapters/repositories/yaml_repository.py (YAML_REPO_TYPE, DEFAULT_YAML_PATH)
  → taxomesh/adapters/repositories/json_repository.py (JSON_REPO_TYPE, DEFAULT_JSON_PATH)
  → taxomesh/adapters/repositories/django_repository.py (DJANGO_REPO_TYPE) ← NEW
      → taxomesh/application/service.py (ROOT_CATEGORY_NAME) ← already loaded
      → taxomesh/domain/models.py ← already loaded
```

`django_repository.py` has **no Django imports at module level** — all Django symbols are
imported lazily inside `__init__` and method bodies. Importing `DJANGO_REPO_TYPE` from
`django_repository.py` at module level of `config.py` is therefore safe and adds no
Django runtime dependency to the CLI path.

No circular import risk: `django_repository.py` → `service.py`, but `service.py` does NOT
import from `cli/config.py`. The cycle is absent.

**Alternatives considered**:
- New shared `taxomesh/constants.py` module: unnecessary extra module for a small constant.
- In `django_repository.py` itself: would need to import `YAML_REPO_TYPE` + `JSON_REPO_TYPE` from sibling adapters, making `SUPPORTED_REPO_TYPES` a cross-adapter aggregate — less clean.
- In `taxomesh/application/service.py`: would couple the application layer to adapter-level type identifiers without the lazy-import exemption — violates Principle I.

---

## R-004: CONFIG_KEYS invariant test update strategy

**Decision**: Change the `test_config_keys_covers_all_dump_output_keys` assertion from
strict equality (`==`) to subset check (`⊆`). Keep `CONFIG_KEYS` as the exhaustive union
of all possible TOML keys across all repo types.

**Finding**: The current invariant `dumped_keys == set(CONFIG_KEYS)` was valid when all
repo types produced the same TOML keys (type + path). With the django type emitting
`using` instead of `path`, the union of all possible keys is
`{repository.type, repository.path, repository.using}`, but any single dump invocation
produces only a subset.

Updated invariant: "every key in the dump output must appear in `CONFIG_KEYS`" — a forward
safety check ensuring the dump never emits an undocumented key, regardless of repo type.

The reverse invariant ("every CONFIG_KEY appears in the dump") is intentionally relaxed;
it is replaced by type-specific assertions (e.g., "yaml dump has `path`; django dump has
`using` and not `path`").

---

## R-005: django_repository.py — _USING_DEFAULT vs DJANGO_REPO_USING_DEFAULT in models.py

**Finding**: Two independent constants exist with the same value `"default"`:
- `_USING_DEFAULT: str = "default"` in `django_repository.py`
- `DJANGO_REPO_USING_DEFAULT: Final[str] = "default"` in `models.py`

This is a Principle X violation (duplicate magic literal). **Resolution for this feature**:
Keep `_USING_DEFAULT` in `django_repository.py` as-is (private constant, owned by the adapter).
Consolidating the two is out of scope here; record as tech debt for a future cleanup feature.
The `_build_django` function in `service.py` imports `_USING_DEFAULT` from `django_repository`;
no change needed.

---

## R-006: Template rendering — CategoryNode tree for the admin graph view

**Finding**: `TaxomeshService.get_graph()` returns a `TaxomeshGraph` with a `roots: list[CategoryNode]`
attribute. Each `CategoryNode` has:
- `category: Category` (with `.name`, `.category_id`, `.enabled`, `.external_id`)
- `items: list[Item]` (with `.external_id`, `.item_id`, `.enabled`)
- `children: list[CategoryNode]`

Django templates do not support recursion natively. Options:
1. **Recursive include** using `{% include "..." with node=child %}` — works but requires
   a separate partial template and is slow for deep trees.
2. **Flatten in view** into an annotated list with depth levels — iterative, fast, no recursion needed.
3. **Template tag** — overkill for a library.

**Decision**: Flatten the `TaxomeshGraph` into a list of `(depth: int, node_type: str, data: dict)`
tuples in the view function before passing to the template. The template renders a flat list
with CSS `padding-left` based on depth. Clean, no recursive includes, no custom template tags.

**Rationale**: Avoids recursive template includes (slow, complex). Template stays simple.
The flattening logic lives in the view method, which is easy to unit-test independently.
