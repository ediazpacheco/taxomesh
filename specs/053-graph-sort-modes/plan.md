# Implementation Plan: Pluggable Graph Sort Modes

**Branch**: `053-graph-sort-modes` | **Date**: 2026-03-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/053-graph-sort-modes/spec.md`

---

## Summary

Add a pluggable sort mode registry to the Django admin graph view. taxomesh ships two
built-in sort modes (`sort_index_asc`, `sort_index_desc`); consumers extend the list by
overriding a `sort_modes` class attribute on their admin subclass with additional
`(key, label, callable)` 3-tuples. The active mode is propagated as a `sort_by` query
param to both the root graph view and the lazy-load children AJAX endpoint. A `<select>`
toolbar above the graph lets users switch modes. taxomesh remains fully agnostic — it
knows nothing about consumer-specific sort criteria.

---

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Django ≥ 4.2 (admin framework), Pydantic v2 (domain models — unchanged), Typer ≥ 0.12 (CLI — unchanged)
**Storage**: N/A — no new models, no migrations
**Testing**: pytest + pytest-django
**Target Platform**: Django admin (browser UI + server-side views)
**Project Type**: Library with optional Django admin adapter (`taxomesh.contrib.django`)
**Performance Goals**: No new queries — sort is an in-process list operation applied after entries are already built
**Constraints**: No circular imports between new modules; mypy --strict must pass
**Scale/Scope**: Registry expected to have 2–5 entries per consumer; linear scan is acceptable

---

## Constitution Check

| Principle | Status | Notes |
|---|---|---|
| I. Hexagonal — dependency direction | ✅ | All changes in `contrib/django/` (adapter layer). No domain or application layer touched. |
| II. TaxomeshService is the facade | ✅ | Not affected — graph views already call service directly. |
| III. Repository as Protocol | ✅ | Not affected. |
| IV. Pydantic + mypy strict | ✅ | `SortModeFn` and `SortMode` properly typed; no `Any`. `GraphEntry` moved to resolve circular import. |
| V. Custom exception hierarchy | ✅ | No new exceptions needed. |
| VI. DAG integrity | ✅ | Read-only feature. |
| VII. Spec-driven development | ✅ | Spec 053 exists. |
| VIII. Quality gates | ✅ | All gates must pass before PR. |
| IX. Framework-agnostic HTTP handlers | ✅ | Not affected — this is the Django admin, not `contrib.api`. |
| X. Named constants — no magic literals | ✅ | `DEFAULT_SORT_MODE: Final[str]` defined; no bare string literals for sort keys. |
| XI. OOP by default | ✅ | Sort callables are pure stateless functions — Principle XI explicitly allows module-level functions for this case. |

**Constitution Check result**: PASS — no violations.

---

## Project Structure

### Documentation (this feature)

```text
specs/053-graph-sort-modes/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   └── sort_mode_extension.md   ← consumer extension contract
└── tasks.md             ← Phase 2 output (/speckit.tasks)
```

### Source Code

```text
taxomesh/contrib/django/
├── graph_types.py       ← NEW: GraphEntry, RelationEntry TypedDicts (moved from admin.py)
├── graph_sort.py        ← NEW: SortModeFn, SortMode, DEFAULT_SORT_MODE,
│                                DEFAULT_SORT_MODES, sort_index_asc, sort_index_desc
└── admin.py             ← MODIFIED: import from graph_types + graph_sort;
                                      add sort_modes attr; apply sort in views;
                                      extend template context

taxomesh/contrib/django/templates/admin/taxomesh_contrib_django/
└── graph.html           ← MODIFIED: sort selector toolbar; propagate sort_by in AJAX

tests/contrib/django/
└── test_admin_graph_sort_modes.py   ← NEW: sort mode tests
```

---

## Complexity Tracking

No constitution violations to justify.

---

## Implementation Phases

### Phase A: Extract shared types (prerequisite for no circular imports)

**Files**: `graph_types.py` (new), `admin.py` (import update only)

1. Create `taxomesh/contrib/django/graph_types.py` with `GraphEntry` and `RelationEntry` TypedDicts verbatim from `admin.py`.
2. In `admin.py`, replace the two TypedDict class bodies with imports from `graph_types`.
3. Quality gate: `mypy --strict .` + `pytest` must pass with no behaviour change.

**Why first**: `graph_sort.py` needs `GraphEntry` without creating a cycle.

---

### Phase B: Sort module and built-in callables

**Files**: `graph_sort.py` (new)

```python
# taxomesh/contrib/django/graph_sort.py
"""Built-in graph sort callables and sort mode registry helpers."""

from __future__ import annotations

from typing import Callable, Final, TypeAlias

from taxomesh.contrib.django.graph_types import GraphEntry

SortModeFn: TypeAlias = Callable[[list[GraphEntry]], list[GraphEntry]]
SortMode: TypeAlias = tuple[str, str, SortModeFn]

DEFAULT_SORT_MODE: Final[str] = "sort_index_asc"


def sort_index_asc(entries: list[GraphEntry]) -> list[GraphEntry]:
    """Return entries sorted by sort_index ascending."""
    return sorted(entries, key=lambda e: e["sort_index"])


def sort_index_desc(entries: list[GraphEntry]) -> list[GraphEntry]:
    """Return entries sorted by sort_index descending."""
    return sorted(entries, key=lambda e: e["sort_index"], reverse=True)


DEFAULT_SORT_MODES: Final[list[SortMode]] = [
    ("sort_index_asc",  "Sort index ↑", sort_index_asc),
    ("sort_index_desc", "Sort index ↓", sort_index_desc),
]
```

---

### Phase C: Admin class — sort_modes attribute + view integration

**Files**: `admin.py`

1. **Import** `SortModeFn`, `SortMode`, `DEFAULT_SORT_MODE`, `DEFAULT_SORT_MODES` from `graph_sort`.

2. **Class attribute and helper on `TaxomeshAdminMixin`** (shared by all admin classes — avoids duplication):
   ```python
   sort_modes: list[SortMode] = list(DEFAULT_SORT_MODES)
   ```

3. **Helper** `_resolve_sort_fn` on `TaxomeshAdminMixin`:
   ```python
   def _resolve_sort_fn(self, sort_by: str) -> SortModeFn:
       """Return the callable for sort_by key, falling back to DEFAULT_SORT_MODE."""
       for key, _label, fn in self.sort_modes:
           if key == sort_by:
               return fn
       # Unknown key → fall back to first registered mode (sort_index_asc)
       return self.sort_modes[0][2]
   ```

4. **`graph_view`** changes:
   - Read `sort_by = request.GET.get("sort_by", DEFAULT_SORT_MODE)`
   - After building `entries`, apply: `entries = self._resolve_sort_fn(sort_by)(entries)`
   - Add to template context: `"sort_by": sort_by`, `"sort_mode_options": [{"key": k, "label": l} for k, l, _ in self.sort_modes]`

5. **`graph_children_view`** changes:
   - Read `sort_by = request.GET.get("sort_by", DEFAULT_SORT_MODE)`
   - After `_build_child_entries` and linked_url resolution, apply: `entries = self._resolve_sort_fn(sort_by)(entries)`
   - Note: `sort_by` is **not** passed to the `render_to_string` context — `_graph_entry_list.html` does not use it

---

### Phase D: Template — sort selector UI + JS propagation

**Files**: `graph.html`

1. **Sort selector** — add above `<div id="taxomesh-graph">`, inside `{% else %}` block:
   ```html
   <form method="get" style="margin-bottom: 0.75rem; display: inline-flex; align-items: center; gap: 0.5rem;">
     <label for="taxomesh-sort-select" style="font-size: 0.875rem;">Sort:</label>
     <select id="taxomesh-sort-select" name="sort_by"
             onchange="this.form.submit()"
             style="font-size: 0.875rem;">
       {% for mode in sort_mode_options %}
         <option value="{{ mode.key }}"{% if mode.key == sort_by %} selected{% endif %}>{{ mode.label }}</option>
       {% endfor %}
     </select>
   </form>
   ```

2. **`data-sort-by` on the graph container** — add attribute to `<div id="taxomesh-graph">`:
   ```html
   <div id="taxomesh-graph" data-sort-by="{{ sort_by }}">
   ```

3. **JS — propagate `sort_by` in the children AJAX fetch** (line ~185):
   ```js
   var sortBy = graph.dataset.sortBy || "";
   // … in the fetch call:
   fetch(CHILDREN_URL + "?parent_uuid=" + encodeURIComponent(uuid)
         + "&depth=" + (depth + 1)
         + (sortBy ? "&sort_by=" + encodeURIComponent(sortBy) : ""))
   ```

---

### Phase E: Tests

**Files**: `tests/contrib/django/test_admin_graph_sort_modes.py`

Tests to cover (all must pass before implementation is considered complete):

| Test | Description |
|---|---|
| `test_sort_index_asc_builtin` | `sort_index_asc` returns entries in ascending sort_index order |
| `test_sort_index_desc_builtin` | `sort_index_desc` returns entries in descending sort_index order |
| `test_default_sort_modes_registry` | `DEFAULT_SORT_MODES` has exactly 2 entries with correct keys |
| `test_resolve_sort_fn_known_key` | `_resolve_sort_fn("sort_index_desc")` returns desc callable |
| `test_resolve_sort_fn_unknown_key` | `_resolve_sort_fn("unknown")` returns first mode callable (asc) |
| `test_graph_view_default_sort` | GET `/graph/` with no `sort_by` renders entries sorted asc |
| `test_graph_view_sort_desc` | GET `/graph/?sort_by=sort_index_desc` renders entries sorted desc |
| `test_graph_children_view_sort_propagated` | GET `/graph/children/?…&sort_by=sort_index_desc` applies desc sort |
| `test_consumer_custom_sort_mode` | Admin subclass with custom sort mode appears in sort_modes and is applied |
| `test_no_regression_default_order` | Without `sort_by` param, behaviour matches pre-feature (sort_index_asc) |

---

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Circular import between `admin.py` and `graph_sort.py` | Resolved by Phase A: `GraphEntry` moved to `graph_types.py` before `graph_sort.py` is created |
| Consumer callable raises an exception | By contract (see `contracts/sort_mode_extension.md`): uncaught exceptions propagate — it is the consumer's responsibility. No silent swallowing. |
| `sort_modes` mutable list shared across subclasses | Document in contract: consumers must use `list(DEFAULT_SORT_MODES) + [...]` or `[*DEFAULT_SORT_MODES, ...]` to avoid mutating the parent class attribute |
| Template unpack of 3-tuple `(key, label, _)` in Django template for loop | Django templates don't support tuple unpacking in `{% for %}`. Use a helper or restructure. See note below. |

### Template iteration note

Django templates cannot unpack 3-tuples in `{% for key, label, fn in sort_modes %}`.
The template must either:
- Use index access: `{% for mode in sort_modes %}{{ mode.0 }}{{ mode.1 }}{% endfor %}`
- Or the view converts `sort_modes` to a list of dicts before passing to context:
  ```python
  "sort_mode_options": [{"key": k, "label": l} for k, l, _ in self.sort_modes]
  ```
  **Decision**: Use `sort_mode_options` dict list in context — cleaner template.

---

## Dependency Order

```
Phase A (graph_types.py) → Phase B (graph_sort.py) → Phase C (admin.py) → Phase D (template) → Phase E (tests)
```

Tests in Phase E cover Phases A–D. Per TDD rule: write failing tests first (Phase E skeleton),
then implement A → D, then run tests to green.
