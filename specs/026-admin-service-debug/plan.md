# Implementation Plan: Admin & Service Improvements — Category External ID, Debug, and UX

**Branch**: `026-admin-service-debug` | **Date**: 2026-03-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/026-admin-service-debug/spec.md`

## Summary

Seven improvements across the service layer, CLI, and Django admin: (1) expose `external_id` on `create_category`, `update_category`, and `list_categories`; (2) add `TaxomeshService.get_debug()`; (3) fix Category linked-object resolution in admin with a dedicated `TAXOMESH_CATEGORY_LINKED_MODEL` setting; (4) add partial UUID search to admin list views; (5) add better admin filters for Category and the generic mixin; (6) flip `show-relations` default to `True` in CLI and admin graph; (7) add a read-only Debug admin page under the TAXOMESH section.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Pydantic v2 (domain), Typer ≥ 0.12 (CLI), Django ≥ 4.2 (admin), `importlib.metadata` (stdlib — version lookup)
**Storage**: JSON file (`JsonRepository`), YAML file (`YamlRepository`), Django ORM (`DjangoRepository`)
**Testing**: pytest with pytest-cov; Django test client for admin views
**Target Platform**: Library + optional Django admin contrib
**Project Type**: Python library with optional Django contrib
**Performance Goals**: No new performance requirements; UUID substring search is bounded by admin list pagination
**Constraints**: `mypy --strict` compliance; `ruff` clean; ≥ 80% coverage; no new migrations
**Scale/Scope**: 8 source files changed; ~3 new test files or extensions to existing test files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Hexagonal architecture — dependency direction | ✅ Pass | `get_debug_info()` added to Protocol (port); service calls the Protocol; adapters implement it. No adapter imports in service. |
| I. Adapter defaults stay in adapters | ✅ Pass | No adapter-specific defaults duplicated in service |
| II. TaxomeshService is the single public facade | ✅ Pass | `get_debug()` and updated category methods live on `TaxomeshService` |
| III. Repository as Protocol | ✅ Pass | `get_debug_info()` added to `TaxomeshRepositoryBase` Protocol; structural typing enforced |
| IV. Pydantic domain models + mypy strict | ✅ Pass | No new domain model fields; service params typed correctly; `str | None` union syntax used |
| IV. String length rule | ✅ Pass | `external_id` already has `max_length=256`; no new unbounded str fields |
| V. Custom exception hierarchy | ✅ Pass | No silent failures; `get_debug()` degrades gracefully but never silently swallows real errors |
| VI. DAG integrity | ✅ Pass | Not touched by this feature |
| VII. Spec-driven development | ✅ Pass | Spec exists at `specs/026-admin-service-debug/spec.md` |
| VIII. Quality gates | ✅ Required | ruff, mypy --strict, pytest ≥ 80% cov must pass before PR |
| X. Named constants | ✅ Pass | `TAXOMESH_CATEGORY_LINKED_MODEL_SETTING: Final[str]` added; no magic literals |
| XI. Object-oriented by default | ✅ Pass | All new admin filters are classes; `get_debug()` is a method on `TaxomeshService` |

**Post-design re-check**: ✅ All principles satisfied by the designs in `research.md` and `data-model.md`.

## Project Structure

### Documentation (this feature)

```text
specs/026-admin-service-debug/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   └── service-api.md   ← Phase 1 output
├── checklists/
│   └── requirements.md
└── tasks.md             ← Phase 2 output (/speckit.tasks — not yet created)
```

### Source Code (files affected)

```text
taxomesh/
├── ports/
│   └── repository.py                    # add get_debug_info() to Protocol
├── application/
│   └── service.py                       # _config_name attr; update 3 methods; add get_debug()
├── adapters/
│   ├── repositories/
│   │   ├── json_repository.py           # implement get_debug_info()
│   │   ├── yaml_repository.py           # implement get_debug_info()
│   │   └── django_repository.py         # implement get_debug_info()
│   └── cli/
│       └── main.py                      # show_relations default True
└── contrib/
    └── django/
        └── admin.py                     # TAXOMESH_CATEGORY_LINKED_MODEL_SETTING; search_fields;
                                         # HasLinkedObjectListFilter; TaxomeshCategoryListFilter;
                                         # TaxomeshDebugProxy + TaxomeshDebugProxyAdmin;
                                         # CategoryModelAdmin.linked_object_url update;
                                         # admin graph show-relations default

tests/
├── service/
│   ├── test_service_categories.py       # extend with external_id tests
│   └── test_service_config.py           # extend with get_debug() tests
└── contrib/
    └── django/
        ├── test_admin.py                # extend with UUID search, linked object, filter tests
        ├── test_admin_graph.py          # show-relations default in admin graph
        └── test_admin_debug.py          # NEW — TaxomeshDebugProxyAdmin tests
    adapters/
    └── cli/
        └── test_graph_output.py         # show-relations default in CLI
```

**Structure Decision**: Single project — all changes are within the existing `taxomesh` package. No new sub-packages or top-level modules required.

## Implementation Phases

---

### Phase A: Repository Protocol + Adapters — get_debug_info()

**Goal**: Add `get_debug_info() -> dict[str, Any]` to the `TaxomeshRepositoryBase` Protocol and implement it in all three repository adapters.

**Files**:
- `taxomesh/ports/repository.py` — add method to Protocol
- `taxomesh/adapters/repositories/json_repository.py` — implement
- `taxomesh/adapters/repositories/yaml_repository.py` — implement
- `taxomesh/adapters/repositories/django_repository.py` — implement

**Implementation details**:

`ports/repository.py`:
```
def get_debug_info(self) -> dict[str, Any]: ...
```

`JsonRepository.get_debug_info()`:
```
return {"path": str(self._path)}
```

`YamlRepository.get_debug_info()`:
```
return {"path": str(self._path)}
```

`DjangoRepository.get_debug_info()`:
```
return {"database_alias": self._using}
```

**Tests** (extend `test_json_repository.py`, `test_yaml_repository.py`, `test_django_repository.py` or add to `test_service_config.py`):
- Each adapter's `get_debug_info()` returns a dict with the expected keys
- `JsonRepository` and `YamlRepository` return the correct path string
- `DjangoRepository` returns the correct database alias

---

### Phase B: TaxomeshService — external_id + get_debug()

**Goal**: Update `create_category`, `update_category`, `list_categories`, store `_config_name`, and add `get_debug()`.

**Files**: `taxomesh/application/service.py`

**Implementation details**:

`__init__` additions:
- Add `self._config_name: str | None = None`
- When reading `taxomesh.toml`, populate `self._config_name` from the TOML `[taxomesh]` section's `name` key (if present; fall back to `None`)

`create_category`:
- Add `external_id: str = ""` as the last keyword parameter
- Pass `external_id=external_id` to `Category(...)` construction

`update_category`:
- Add `external_id: str | None = None` as the last keyword parameter
- In the update-existing-values block, apply `if external_id is not None: category.external_id = external_id`

`list_categories`:
- Add `external_id: str | None = None` keyword parameter
- When `external_id is not None`: call `results = self._repo.list_categories_by_external_id(external_id)`, filter out root (`cat.category_id != self._root_id`), and if `parent_id` is also given, intersect with the children of that parent
- When `external_id is None`: existing behaviour unchanged

`get_debug()`:
```python
def get_debug(self) -> dict[str, Any]:
    import importlib.metadata
    try:
        version = importlib.metadata.version("taxomesh")
    except importlib.metadata.PackageNotFoundError:
        version = "unknown"
    repo_info = self._repo.get_debug_info()
    working_path: str | None = repo_info.get("path")
    return {
        "version": version,
        "config_name": self._config_name,
        "repository_type": type(self._repo).__name__,
        "working_path": working_path,
        "repository_info": repo_info,
    }
```

**Note on memoize and `list_categories`**: The `@memoize(DEFAULT_CACHE_TTL)` decorator caches by argument tuple. Adding `external_id` as a keyword parameter creates distinct cache keys for each unique `(parent_id, external_id)` combination. Cache invalidation continues via TTL — no additional mechanism required.

**Tests** (extend `test_service_categories.py`, `test_service_config.py`):
- `create_category(name="X", external_id="abc")` → category has `external_id == "abc"`
- `create_category(name="X")` → category has `external_id == ""`
- `update_category(id, external_id="new")` → stored value updated
- `update_category(id, external_id=None)` → stored value unchanged
- `update_category(id, external_id="")` → stored value cleared
- `list_categories(external_id="abc")` → only matching categories returned
- `list_categories(external_id="")` → only categories with `external_id == ""` returned
- `list_categories(external_id=None)` → all categories returned (existing behaviour)
- `get_debug()` returns dict with required keys; `repository_type` matches adapter class name
- `get_debug()` `working_path` is set for file-backed repos, `None` for Django repo

---

### Phase C: Django Admin — Category Linked-Object Resolution

**Goal**: Add `TAXOMESH_CATEGORY_LINKED_MODEL_SETTING` and update `CategoryModelAdmin.linked_object_url` to use it.

**Files**: `taxomesh/contrib/django/admin.py`

**Implementation details**:

Add constant (near `TAXOMESH_LINKED_MODEL_SETTING`):
```python
TAXOMESH_CATEGORY_LINKED_MODEL_SETTING: Final[str] = "TAXOMESH_CATEGORY_LINKED_MODEL"
```

Update or add a category-specific `_resolve_category_linked_url(external_id: str) -> str | None` function that reads `settings.TAXOMESH_CATEGORY_LINKED_MODEL` instead of `settings.TAXOMESH_LINKED_MODEL`. The resolution logic is identical to the existing `_resolve_linked_url`.

Update `CategoryModelAdmin.linked_object_url` to call `_resolve_category_linked_url` (or pass the settings key as a parameter to the shared helper).

**Tests** (extend `test_admin.py`):
- With `TAXOMESH_CATEGORY_LINKED_MODEL` set: icon shown for categories with non-empty `external_id`
- Without `TAXOMESH_CATEGORY_LINKED_MODEL`: no icon, no error, `external_id` shown as text
- `TAXOMESH_LINKED_MODEL` still works for Item (unchanged)

---

### Phase D: Django Admin — Partial UUID Search

**Goal**: Add UUID fields to `search_fields` on `CategoryModelAdmin` and `ItemModelAdmin`.

**Files**: `taxomesh/contrib/django/admin.py`

**Implementation details**:

`CategoryModelAdmin`:
```python
search_fields = ("name", "slug", "category_id")
```

`ItemModelAdmin`:
```python
search_fields = ("name", "external_id", "slug", "item_id")
```

Django admin applies `__icontains` to each search field. UUID stored as `UUIDField` is cast to text for substring matching.

**Tests** (extend `test_admin.py`):
- Search for partial `category_id` UUID substring → matching category appears in queryset
- Search for partial `item_id` UUID substring → matching item appears in queryset
- Search for non-matching substring → empty queryset, no error

---

### Phase E: Django Admin — Better Filters

**Goal**: Add `HasLinkedObjectListFilter` to `CategoryModelAdmin` and `TaxomeshCategoryListFilter` to `ItemCategoryAssignmentMixin`.

**Files**: `taxomesh/contrib/django/admin.py`

**Implementation details**:

`HasLinkedObjectListFilter(SimpleListFilter)`:
- `title = "linked object"`
- `parameter_name = "has_linked_object"`
- `lookups`: returns `[("yes", "Has linked object"), ("no", "No linked object")]`
- `queryset`: `"yes"` → filter `external_id != ""`; `"no"` → filter `external_id == ""`
  - Note: "has linked object" in terms of external_id presence is defined as `external_id != ""`. Full resolution to an existing external record in the filter would require hitting the external DB — out of scope; use `external_id != ""` as the proxy condition.
- Register on `CategoryModelAdmin.list_filter`

`TaxomeshCategoryListFilter(SimpleListFilter)`:
- `title = "taxomesh category"`
- `parameter_name = "taxomesh_category"`
- `lookups`: queries `DjangoRepository().assignable_categories_qs()` for `(slug, name)` pairs; returns `[(slug, name), ...]`
- `queryset`: look up items in the selected category; filter external model queryset by `pk__in=[item.external_id for item in items]` where `taxomesh_external_id_attr` is `"pk"`

  **Note**: `TaxomeshCategoryListFilter` is available for use in `ItemCategoryAssignmentMixin`; it is not added to mixin's `list_filter` automatically because external model admins vary in their `list_filter` setup. Instead, expose it as an importable class and document in `quickstart.md`. [NEEDS CLARIFICATION: should this be added automatically to `ItemCategoryAssignmentMixin.list_filter` or left as opt-in?]

  **Resolved via clarification (Q2 → A: auto-included)**: `TaxomeshCategoryListFilter` IS automatically added to `ItemCategoryAssignmentMixin.list_filter` as a class attribute. Integrators get the filter with no extra configuration. This supersedes the research.md Decision 3 note.

**Tests** (extend `test_admin.py`):
- `HasLinkedObjectListFilter` "yes" → only categories with `external_id != ""` returned
- `HasLinkedObjectListFilter` "no" → only categories with `external_id == ""` returned
- `HasLinkedObjectListFilter` unfiltered → all categories returned

---

### Phase F: CLI — show-relations Default

**Goal**: Change `show_relations` default from `False` to `True` in the CLI `graph` command.

**Files**: `taxomesh/adapters/cli/main.py`

**Implementation details**:

In `graph_cmd`:
```python
show_relations: bool = typer.Option(
    True,  # was: False
    "--show-relations/--no-show-relations",
    help="Show outgoing item relations",
),
```

No other changes required.

**Tests** (extend `test_graph_output.py`):
- Run `graph` command with no flags → output contains relation lines for items with relations
- Run `graph --no-show-relations` → output does not contain relation lines

---

### Phase G: Admin Graph — show-relations Default

**Goal**: Change the admin graph view to display item relations by default.

**Files**: `taxomesh/contrib/django/admin.py`

**Implementation details**:

Locate the admin graph view (the view registered under `admin:taxomesh_contrib_django_graph`). Find the parameter that controls whether relations are rendered (likely a `show_relations` URL query parameter or a local variable). Change its default value to `True` so that the graph renders relations when the parameter is absent from the request.

The specific change depends on the current graph view implementation — the URL parameter or context variable controlling relations must be identified during implementation and its default flipped from `False` to `True`.

**Tests** (extend `test_admin_graph.py`):
- GET request to the graph view with no `show_relations` query param → response contains relation data
- GET request with `show_relations=0` → response does not contain relation data

---

### Phase H: Admin Debug Page

**Goal**: Add `TaxomeshDebugProxy` model and `TaxomeshDebugProxyAdmin` to display `get_debug()` output under the TAXOMESH section.

**Files**: `taxomesh/contrib/django/admin.py` (and possibly `taxomesh/contrib/django/models.py` for the proxy model definition)

**Implementation details**:

Proxy model (follow `CategoryGraphProxy` pattern):
```python
class TaxomeshDebugProxy(CategoryModel):
    class Meta:
        proxy = True
        verbose_name = "Debug"
        verbose_name_plural = "Debug"
        app_label = APP_LABEL
```

Admin class:
```python
@admin.register(TaxomeshDebugProxy)
class TaxomeshDebugProxyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
    def has_view_permission(self, request, obj=None): return request.user.is_staff

    def changelist_view(self, request, extra_context=None):
        # Instantiate TaxomeshService and call get_debug()
        # Render a minimal template or return a TemplateResponse
        # showing the four debug fields as read-only key/value pairs
        ...
```

The view renders a dedicated template (reuse existing admin template patterns) displaying the four `get_debug()` fields. No redirect — the debug data is shown inline on the changelist page.

**No migration required**: proxy model inherits `CategoryModel`'s table but adds no new columns.

**Tests** (`tests/contrib/django/test_admin_debug.py` — new file):
- `TaxomeshDebugProxy` is registered in the admin
- GET to `/admin/taxomesh_contrib_django/taxomeshdebugproxy/` returns HTTP 200 for staff user
- Response contains the four debug field labels (version, config_name, repository_type, working_path)
- Non-staff user receives HTTP 302 redirect (standard Django admin auth)

---

## Complexity Tracking

No constitution violations. All changes are additive or minimal modifications to existing patterns.

## Implementation Order

Execute phases in this order (each depends on the previous being complete for integration, but tests within each phase are independent):

1. **Phase A** — Protocol + adapter `get_debug_info()` (foundation for Phase B)
2. **Phase B** — Service enhancements (`external_id` + `get_debug()`) (foundation for Phase H)
3. **Phase C** — Category linked-object admin (standalone)
4. **Phase D** — UUID search fields (standalone, tiny change)
5. **Phase E** — Admin filters (standalone)
6. **Phase F** — CLI show-relations default (standalone, tiny change)
7. **Phase G** — Admin graph show-relations default (standalone)
8. **Phase H** — Admin Debug page (depends on Phase B's `get_debug()`)

Each phase must include its failing test(s) before the implementation (TDD). No phase is considered done until `pytest [relevant test file]` passes.
