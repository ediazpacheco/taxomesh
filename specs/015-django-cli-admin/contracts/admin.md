# Admin Contract: Taxonomy Graph View

**Feature**: `015-django-cli-admin`
**Phase**: 1 — Design & Contracts
**Date**: 2026-03-01

---

## URL

```
GET /admin/taxomesh_contrib_django/categorymodel/graph/
```

Registered via `CategoryModelAdmin.get_urls()` as:

```python
path(
    "graph/",
    self.admin_site.admin_view(self.graph_view),
    name="taxomesh_contrib_django_graph",
)
```

Reverse URL name: `admin:taxomesh_contrib_django_graph`

---

## Access Control

| Requirement | Value |
|-------------|-------|
| `request.user.is_staff` | Must be `True` |
| `request.user.is_active` | Must be `True` |
| Taxomesh-specific permission | None — same access as admin login |

Enforced by `admin_site.admin_view()` wrapper — not `ModelAdmin`-level permission checks.

---

## Response: Success (HTTP 200)

Renders `admin/taxomesh_contrib_django/graph.html` extending `admin/base_site.html`.

### Template context

| Variable | Type | Description |
|----------|------|-------------|
| `title` | `str` | Page title: `"Taxonomy Graph"` |
| `entries` | `list[dict]` | Flattened tree rows (see `data-model.md`) |
| `has_entries` | `bool` | `True` when at least one root category exists |
| `error` | `str \| None` | Error message if `get_graph()` raised `TaxomeshError`; `None` on success |
| `opts` | `Options` | Django model meta options (required by `admin/base_site.html`) |

### Entry dict shape (per row)

```python
{
    "depth": int,          # 0 = root category
    "kind": "category" | "item",
    "name": str,           # category.name or str(item.external_id)
    "uuid": str,           # str(category.category_id) or str(item.item_id)
    "enabled": bool,
    "external_id": str | None,  # categories only; None for items
}
```

### Visual rendering rules

| Property | Category row | Item row |
|----------|-------------|----------|
| Indent | `depth * 1.5rem` left padding | `(depth) * 1.5rem` left padding |
| Text colour (enabled) | Standard admin text | Standard admin text |
| Text colour (disabled) | Muted / grey | Muted / grey |
| Enabled indicator | ✓ (green) or ✗ (red) | ✓ (green) or ✗ (red) |
| UUID shown | Yes (dim/small) | Yes (dim/small) |
| External ID shown | Only when non-empty | N/A (external_id is the primary identifier) |

No external CSS or JavaScript required. Styling uses Django admin's built-in class utilities.

---

## Response: Empty taxonomy (HTTP 200)

When `graph.roots` is empty (no categories), `has_entries = False`.
Template renders an empty-state message (e.g., "No categories found. Add one to get started.")
instead of a tree.

---

## Response: Repository error (HTTP 200)

When `get_graph()` raises `TaxomeshError`, `error` is set to the exception message string
and `has_entries = False`. Template renders the error message prominently (e.g., in a
Django admin `errornote` div).

The view does NOT raise `Http500` — it degrades gracefully.

---

## App index link

The taxomesh admin app section (`/admin/taxomesh_contrib_django/`) shows a "Graph" link
via `taxomesh/contrib/django/templates/admin/taxomesh_contrib_django/app_index.html`.

Link label: `"Graph"`
Link target: `{% url 'admin:taxomesh_contrib_django_graph' %}`
Link description: `"View the full taxonomy as a tree"`

The link appears in a separate table block ("Visualization") appended after the model links
block, using the same `<table>` / `<caption>` / `<tr>` structure as the built-in model list.

---

## Template files

| Path | Purpose |
|------|---------|
| `taxomesh/contrib/django/templates/admin/taxomesh_contrib_django/app_index.html` | Extends `admin/app_index.html`; appends Graph link to app section |
| `taxomesh/contrib/django/templates/admin/taxomesh_contrib_django/graph.html` | Extends `admin/base_site.html`; renders the taxonomy tree |

Template discovery requires `APP_DIRS=True` in `TEMPLATES` settings (Django default). Both
templates use only built-in Django template tags (`{% extends %}`, `{% block %}`, `{% url %}`,
`{% for %}`, `{% if %}`) — no custom template tag libraries.

---

## Not in scope

- Pagination (single-page render for any taxonomy size)
- Filtering or search on the graph page
- Interactive collapse/expand (no JavaScript)
- Per-model permission checks beyond `is_staff`
