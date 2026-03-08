# Data Model: Graph & Admin UX Improvements

**Branch**: `025-graph-admin-ux` | **Date**: 2026-03-08

## Entities (unchanged)

No domain entities are added or modified.

## New / Modified Types (adapter layer only)

### `_flatten_graph` signature update

```python
def _flatten_graph(
    graph: TaxomeshGraph,
    max_depth: int = ADMIN_GRAPH_DEFAULT_MAX_DEPTH,
) -> list[GraphEntry]:
```

`GraphEntry` TypedDict is unchanged (already has all required fields from 024).

### New constants

```python
# taxomesh/adapters/cli/main.py
MAX_DEPTH_UNLIMITED: Final[int] = 0
GRAPH_DEFAULT_MAX_DEPTH: Final[int] = 3

# taxomesh/contrib/django/admin.py
ADMIN_GRAPH_DEFAULT_MAX_DEPTH: Final[int] = 3
```

### New helper function

```python
# taxomesh/contrib/django/admin.py (module-level)
def _resolve_linked_url(external_id: str) -> str | None:
    """Return the Django admin change URL for the configured linked model instance.

    Args:
        external_id: The external_id string from a Category or Item.

    Returns:
        Admin change URL string, or None if setting absent, model unresolvable,
        or instance not found.
    """
```

### New template tag

```python
# taxomesh/contrib/django/templatetags/taxomesh_tags.py
@register.simple_tag
def taxomesh_version_info() -> dict[str, str]:
    """Return taxomesh version and active backend/config info.

    Returns:
        Dict with keys 'version' (installed version string or 'unknown')
        and 'backend' (taxomesh.toml path if found, else 'Django ORM backend').
    """
```

Return type: `dict[str, str]` with keys `version` and `backend`.

## Configuration (unchanged)

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `TAXOMESH_LINKED_MODEL` | `str \| None` | not set | Django model `"app_label.ModelName"` for icon-links |
