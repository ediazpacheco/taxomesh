# Data Model: Django CLI Compatibility and Admin Graph View

**Feature**: `015-django-cli-admin`
**Phase**: 1 — Design & Contracts
**Date**: 2026-03-01

---

## No New Domain Entities

This feature introduces no new domain entities, Pydantic models, ORM models, or repository
protocol methods. All data consumed and produced exists in the current domain.

---

## New Named Constants

### `DJANGO_REPO_TYPE` — `taxomesh/adapters/repositories/django_repository.py`

| Field | Value |
|-------|-------|
| Name | `DJANGO_REPO_TYPE` |
| Type | `Final[str]` |
| Value | `"django"` |
| Purpose | Canonical identifier for the Django ORM repository type in `taxomesh.toml` `[repository] type` |
| Replaces | Bare string literal `"django"` in `service.py` `_REPO_BUILDERS` dict |
| Pattern | Matches `YAML_REPO_TYPE` in `yaml_repository.py` and `JSON_REPO_TYPE` in `json_repository.py` |

### `SUPPORTED_REPO_TYPES` — `taxomesh/adapters/cli/config.py`

| Field | Value |
|-------|-------|
| Name | `SUPPORTED_REPO_TYPES` |
| Type | `Final[tuple[str, ...]]` |
| Value | `(YAML_REPO_TYPE, JSON_REPO_TYPE, DJANGO_REPO_TYPE)` |
| Purpose | Single authoritative collection of all valid `repository.type` values; consumed by `dump_config()` accepted-values comment and any validation logic |
| Replaces | The hardcoded list in `dump_config()` comment and the implicit list in `_REPO_BUILDERS` |

---

## Modified Signatures

### `dump_config(repo_type, repo_detail)` — `cli/config.py`

**Before**:
```python
def dump_config(repo_type: str, repo_path: str) -> str: ...
```

**After**:
```python
def dump_config(repo_type: str, repo_detail: str) -> str: ...
```

| Parameter | Previous meaning | New meaning |
|-----------|-----------------|-------------|
| `repo_type` | Repository type string (`"yaml"`, `"json"`) | Same — plus `"django"` |
| `repo_path` | File path to the repository data file | Renamed `repo_detail`; for yaml/json: file path; for django: `using` alias |

**Behaviour change**: When `repo_type == DJANGO_REPO_TYPE`, `dump_config` emits:
```toml
[repository]
# ... accepted values comment referencing SUPPORTED_REPO_TYPES
type = "django"

# Django database alias (key in Django DATABASES settings).
# Default: "default"
using = "default"
```

When `repo_type` is `yaml` or `json`, behaviour is unchanged except the accepted-values
comment lists all three values from `SUPPORTED_REPO_TYPES`.

### `_resolve_effective_config(config_path)` — `cli/config.py`

**Return type unchanged**: `tuple[str, str]`

| Return element | For yaml/json | For django |
|----------------|--------------|-----------|
| First (`repo_type`) | `"yaml"` or `"json"` | `"django"` |
| Second (`repo_detail`) | File path string | `using` alias string (default: `"default"`) |

**Added logic**: When `repo_type == DJANGO_REPO_TYPE`, extract `section.get("using", _USING_DEFAULT)`.

### `CONFIG_KEYS` — `cli/config.py`

**Before**: `["repository.type", "repository.path"]`

**After**: `["repository.type", "repository.path", "repository.using"]`

All three values represent recognised TOML configuration keys across all supported
repository types. Any single `dump_config()` call emits a strict subset (type-specific).

---

## New Runtime Objects (Admin View)

### `GraphViewEntry` (internal, not a class — a dict passed to template)

The admin graph view passes a context variable `entries: list[dict]` to the template.
Each dict represents one rendered row (category or item):

| Key | Type | Description |
|-----|------|-------------|
| `depth` | `int` | Nesting level (0 = root category) |
| `kind` | `str` | `"category"` or `"item"` |
| `name` | `str` | For categories: `category.name`; for items: `str(item.external_id)` |
| `uuid` | `str` | For categories: `str(category.category_id)`; for items: `str(item.item_id)` |
| `enabled` | `bool` | Whether the entity is enabled |
| `external_id` | `str \| None` | For categories: `category.external_id` (if set); for items: N/A (use `name`) |

The flattening algorithm is a depth-first traversal of `TaxomeshGraph.roots`:

```
def _flatten_graph(graph: TaxomeshGraph) -> list[dict]:
    entries = []
    def _visit(node: CategoryNode, depth: int) -> None:
        entries.append({kind: "category", depth: depth, ...})
        for item in node.items:
            entries.append({kind: "item", depth: depth + 1, ...})
        for child in node.children:
            _visit(child, depth + 1)
    for root in graph.roots:
        _visit(root, depth=0)
    return entries
```

This is a pure stateless function — appropriate as a module-level utility per Principle XI.
