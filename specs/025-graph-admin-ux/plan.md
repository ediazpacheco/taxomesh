# Implementation Plan: Graph & Admin UX Improvements

**Branch**: `025-graph-admin-ux` | **Date**: 2026-03-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/025-graph-admin-ux/spec.md`

## Summary

Six targeted improvements across the CLI graph command and Django admin: add `--max-depth`
(default 3) to filter the tree by depth; make item relations always present in the admin graph
but collapsed by default (removing the toggle); add `↗` icon-links to Item/Category list and
detail admin views; show taxomesh version + backend info in the admin home; remove the
standalone `ItemRelationLinkModelAdmin`; update README and bump version to `0.1.0a12`.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Typer ≥ 0.12, Rich ≥ 13.0 (CLI); Django ≥ 4.2 (admin); Pydantic v2 (domain)
**Storage**: DjangoRepository (admin); any configured repo (CLI)
**Testing**: pytest, pytest-cov; Django test client (admin views)
**Target Platform**: Terminal (CLI), Django admin (browser)
**Project Type**: Library / CLI / Django contrib
**Performance Goals**: Graph page < 2 s for up to 1 000 nodes (unchanged)
**Constraints**: Vanilla JS only; `importlib.metadata` for version (stdlib); no new runtime deps
**Scale/Scope**: Taxonomies up to ~1 000 nodes in practice

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Hexagonal Architecture | ✅ PASS | All changes in adapters (CLI, Django contrib); domain untouched |
| II. TaxomeshService is the facade | ✅ PASS | CLI and admin both use TaxomeshService |
| III. Repository as Protocol | ✅ PASS | No protocol changes |
| IV. Pydantic + mypy strict | ✅ PASS | `_flatten_graph` gains typed `max_depth` param |
| V. Custom Exception Hierarchy | ✅ PASS | Error handling unchanged; icon resolution stays silent |
| VI. DAG Integrity | ✅ PASS | Not affected |
| VII. Spec-Driven | ✅ PASS | This plan is the spec artefact |
| VIII. Quality Gates | ✅ PASS | All gates must pass before PR |
| IX. Pluggable REST | ✅ PASS | Not affected |
| X. Named Constants | ✅ PASS | New constants required — see below |
| XI. OO by Default | ✅ PASS | New shared helper `_resolve_linked_url` is pure stateless function |

**Complexity tracking**: No violations.

## Project Structure

### Documentation (this feature)

```text
specs/025-graph-admin-ux/
├── plan.md              ← this file
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── cli-graph.md
└── tasks.md             ← /speckit.tasks output
```

### Source Code (repository root)

```text
taxomesh/
├── adapters/
│   └── cli/
│       └── main.py                    # graph_cmd: add --max-depth; _add_graph_node: depth gate
├── contrib/
│   └── django/
│       ├── admin.py                   # _flatten_graph + depth; _resolve_linked_url helper;
│       │                              # ItemModelAdmin + CategoryModelAdmin icon-link columns;
│       │                              # remove ItemRelationLinkModelAdmin
│       ├── templatetags/
│       │   └── taxomesh_tags.py       # add taxomesh_version_info template tag
│       └── templates/
│           └── admin/
│               └── taxomesh_contrib_django/
│                   ├── app_index.html # version + backend info widget
│                   └── graph.html     # remove toggle; relations collapsed by default
pyproject.toml                         # version bump 0.1.0a11 → 0.1.0a12
README.md                              # document new features

tests/
├── adapters/
│   └── cli/
│       └── test_graph_output.py       # add --max-depth tests
└── contrib/
    └── django/
        └── test_admin_graph.py        # update toggle tests; add depth, version widget, icon-link tests
```

## Phase 0: Research

*All NEEDS CLARIFICATION items resolved at spec time. See [research.md](research.md).*

## Phase 1: Design

### US1: `--max-depth` — CLI design

**Current**: `_add_graph_node` recurses unconditionally.

**Change**:
1. Add constants to `taxomesh/adapters/cli/main.py`:
   - `MAX_DEPTH_UNLIMITED: Final[int] = 0`
   - `GRAPH_DEFAULT_MAX_DEPTH: Final[int] = 3`
2. Add `max_depth: int = typer.Option(GRAPH_DEFAULT_MAX_DEPTH, "--max-depth", ...)` to `graph_cmd`.
3. Pass `max_depth` and `current_depth: int = 0` into `_add_graph_node`.
4. In `_add_graph_node`: skip items when `max_depth != MAX_DEPTH_UNLIMITED and current_depth + 1 > max_depth`; skip child recursion when `max_depth != MAX_DEPTH_UNLIMITED and current_depth + 1 > max_depth`.

**Depth convention** (matches `_flatten_graph`):
- Root categories = depth 0; items under root = depth 1; child categories of root = depth 1.
- `--max-depth 3` shows depths 0–2 for categories, depths 1–3 for items.
- `--max-depth 0` = unlimited.

### US1: `--max-depth` — Admin `_flatten_graph`

Add `ADMIN_GRAPH_DEFAULT_MAX_DEPTH: Final[int] = 3` to `taxomesh/contrib/django/admin.py`.

`_flatten_graph` gains signature: `_flatten_graph(graph: TaxomeshGraph, max_depth: int = ADMIN_GRAPH_DEFAULT_MAX_DEPTH) -> list[GraphEntry]`

In `_visit(node, depth)`: if `max_depth != MAX_DEPTH_UNLIMITED and depth > max_depth`, return early (skip entry + descendants).

Also skip items when `max_depth != MAX_DEPTH_UNLIMITED and depth + 1 > max_depth`.

`graph_view` calls: `entries = _flatten_graph(graph)` (default applies automatically).

### US2: Relations always shown, collapsed (Admin graph)

**Remove** from `graph.html`:
- The `<label><input type="checkbox" id="taxomesh-show-relations">` block.
- The JS that gates relation rows on the checkbox.
- The CSS `.taxomesh-relations-visible .taxomesh-relations { display: block }` pattern.

**Keep/adjust**:
- `.taxomesh-relations` blocks stay, still hidden by default (`display: none`).
- Each item with relations still gets a `[+]`/`[-]` toggle button (`taxomesh-rel-toggle`).
- Clicking `[+]` on an item shows its `.taxomesh-relations` block; `[-]` hides it.
- This JS is simpler than the checkbox approach — just a direct toggle per item.

`graph_view` still loads `item_relations` for all items within depth limit (no change there).

### US3: `↗` icon-link in Item/Category list and detail

**Shared helper** in `admin.py` (module-level, pure stateless function):

```python
def _resolve_linked_url(external_id: str) -> str | None:
    """Return admin change URL for the configured linked model, or None."""
    ...  # same logic currently in graph_view; extracted to avoid duplication
```

**`ItemModelAdmin`**:
- Add method `linked_object_url(self, obj: ItemModel) -> str` using `mark_safe` + `_resolve_linked_url(obj.external_id or "")`.
- `linked_object_url.short_description = "↗"` (or `"Linked"`)
- `linked_object_url.allow_tags = True` (Django < 4.0 compat note: use `mark_safe`)
- Add `"linked_object_url"` to `list_display` and `readonly_fields`.

**`CategoryModelAdmin`**: same pattern.

### US4: Admin home version + backend widget

**Template tag** (`taxomesh_tags.py`): add simple tag `taxomesh_version_info` that returns:
```python
{"version": version("taxomesh"), "backend": "<path or 'Django ORM backend'>"}
```
- Version: `importlib.metadata.version("taxomesh")`, fallback `"unknown"`.
- Backend: check `Path(settings.BASE_DIR) / "taxomesh.toml"` — if exists, return its str path; else `"Django ORM backend"`.

**`app_index.html`**: add a second table row in the existing "Visualization" module:
```html
{% load taxomesh_tags %}
{% taxomesh_version_info as info %}
<tr>
  <th>taxomesh {{ info.version }}</th>
  <td>{{ info.backend }}</td>
  ...
</tr>
```

### US5: Remove `ItemRelationLinkModelAdmin`

Delete lines 940–984 in current `admin.py` (the `@admin.register` decorator + full class).
The `ItemRelationLinkModel` import stays (used by `OutgoingRelationInline`, `IncomingRelationInline`, `ItemRelationLinkForm`).

### US6: README + version

- `pyproject.toml` line 3: `version = "0.1.0a11"` → `version = "0.1.0a12"`.
- `README.md`: update Django integration section with `--max-depth`, admin graph collapsed relations, `TAXOMESH_LINKED_MODEL` in list/detail, admin home widget.

## Named Constants Required (Principle X)

```python
# taxomesh/adapters/cli/main.py  (new)
MAX_DEPTH_UNLIMITED: Final[int] = 0
GRAPH_DEFAULT_MAX_DEPTH: Final[int] = 3

# taxomesh/contrib/django/admin.py  (new)
ADMIN_GRAPH_DEFAULT_MAX_DEPTH: Final[int] = 3
# TAXOMESH_LINKED_MODEL_SETTING — already defined in 024
```

## Complexity Tracking

No constitution violations.
