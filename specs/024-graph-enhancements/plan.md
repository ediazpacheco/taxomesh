# Implementation Plan: Graph Enhancements (CLI + Admin)

**Branch**: `024-graph-enhancements` | **Date**: 2026-03-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/024-graph-enhancements/spec.md`

## Summary

Extend the CLI `graph` command with an optional `--show-relations` flag that prints outgoing
item-to-item relations. Enhance the Django admin graph view with: expand/collapse `[+]`/`[-]`
controls (vanilla JS), an item-relations toggle, and icon-links to a configurable Django model
resolved via `external_id` → `pk`.

Note: FR-004 (remove link underlines) is **already implemented** — the template already sets
`text-decoration: none` on `.taxomesh-label a`. No code change required for that requirement.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Typer ≥ 0.12, Rich ≥ 13.0 (CLI); Django ≥ 4.2 (admin); Pydantic v2 (domain)
**Storage**: DjangoRepository (admin), any configured repository (CLI)
**Testing**: pytest, pytest-cov; Django test client for admin views
**Target Platform**: Terminal (CLI), Django admin (browser)
**Project Type**: Library / CLI / Django contrib
**Performance Goals**: Graph page must render in < 2 s for taxonomies up to 1 000 nodes
**Constraints**: Vanilla JS only (no new front-end dependencies); no new runtime Python dependencies
**Scale/Scope**: Taxonomies up to ~1 000 categories + items in practice

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Hexagonal Architecture | ✅ PASS | All changes are in adapters (`cli/`, `contrib/django/`) and leave domain untouched |
| II. TaxomeshService is the facade | ✅ PASS | CLI and admin both use `TaxomeshService`; no direct repo calls outside adapters |
| III. Repository as Protocol | ✅ PASS | No protocol changes |
| IV. Pydantic + mypy strict | ✅ PASS | New dicts in `_flatten_graph` must be typed; function signature to be updated |
| V. Custom Exception Hierarchy | ✅ PASS | Existing error handling preserved; icon resolution fails silently per spec |
| VI. DAG Integrity | ✅ PASS | Not affected |
| VII. Spec-Driven | ✅ PASS | This plan is the spec artefact |
| VIII. Quality Gates | ✅ PASS | All gates must pass before PR |
| IX. Pluggable REST | ✅ PASS | Not affected |
| X. Named Constants | ✅ PASS | `TAXOMESH_LINKED_MODEL` setting name must be a `Final[str]` constant |
| XI. OO by Default | ✅ PASS | `_add_graph_node` and `_flatten_graph` are private helpers; no class needed |

**Complexity tracking**: No violations.

## Project Structure

### Documentation (this feature)

```text
specs/024-graph-enhancements/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/           ← Phase 1 output
│   └── cli-graph.md
└── tasks.md             ← Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
taxomesh/
├── adapters/
│   └── cli/
│       └── main.py                    # graph_cmd + _add_graph_node — add --show-relations
├── contrib/
│   └── django/
│       ├── admin.py                   # _flatten_graph, graph_view — relations + icon-link
│       └── templates/
│           └── admin/
│               └── taxomesh_contrib_django/
│                   └── graph.html     # [+]/[-] controls, toggle, icon-links, JS

tests/
├── adapters/
│   └── cli/
│       └── test_graph_output.py       # add --show-relations tests
└── contrib/
    └── django/
        └── test_admin_graph.py        # add expand/collapse, toggle, icon-link tests
```

**Structure Decision**: Single project, existing layout. All changes are isolated to the two
adapter layers (CLI and Django contrib). No domain changes required.

## Phase 0: Research

*All NEEDS CLARIFICATION items were resolved during /speckit.specify. See [research.md](research.md).*

## Phase 1: Design

### CLI `--show-relations` design

**Current**: `_add_graph_node(tree_node, category_node)` — no service access inside the helper.

**Change**:
1. Add `show_relations: bool = False` parameter to `graph_cmd`.
2. When `show_relations` is `True`, pre-fetch all item relations once before rendering:
   collect every `Item` from all `CategoryNode` objects in the graph, call
   `service.list_item_relations(item.item_id)` for each, build a
   `dict[UUID, list[ItemRelationLink]]` lookup.
3. Pass the lookup (or `None`) into `_add_graph_node`. After rendering an item's label,
   if the lookup contains outgoing relations for that item, add a Rich leaf per relation
   showing `relation_type → target_item_name` (dim style).
4. Target name resolution: use `service.get_item(link.target_item_id)` — already available.

**Pre-fetch strategy** (avoids N+1): collect unique item UUIDs from the entire graph first,
then batch-call `list_item_relations` in a loop before the recursive render. Store in a
`dict[UUID, list[ItemRelationLink]]`.

**Signature changes**:
```
_add_graph_node(
    tree_node: Tree,
    category_node: CategoryNode,
    relations: dict[UUID, list[ItemRelationLink]] | None = None,
    item_lookup: dict[UUID, Item] | None = None,
) -> None
```

### Admin graph: `_flatten_graph` extension

Add two new keys to every item/category entry dict:

| Key | Type | Description |
|-----|------|-------------|
| `external_id` | `str` | Raw `external_id` from domain model; empty string if absent |
| `linked_url` | `str \| None` | Admin change URL for the configured linked model, or `None` |

The `linked_url` is resolved inside `graph_view` (not `_flatten_graph`) so the flatten
function stays framework-agnostic. After flattening, a second pass updates each entry's
`linked_url` based on the resolved model.

**Typed signature**:
```python
class GraphEntry(TypedDict):
    depth: int
    kind: Literal["category", "item"]
    name: str
    uuid: str
    enabled: bool
    external_id: str
    linked_url: str | None
```

Replace `list[dict[str, object]]` with `list[GraphEntry]` throughout.

### Admin graph: item relations in context

Relations are **not** embedded as extra entries in the flat list. Instead, pass a separate
context variable `item_relations: dict[str, list[dict[str, str]]]` mapping item UUID string
→ list of `{relation_type, target_name, target_uuid}` dicts. The template renders them
conditionally inside each item's row, hidden by default.

This keeps `_flatten_graph` clean and keeps relation data separate from the structural tree.

### Admin graph: `graph_view` extension

```python
# pseudocode for new graph_view additions

# 1. Resolve linked model (once per request)
linked_model_label: str | None = getattr(settings, TAXOMESH_LINKED_MODEL_SETTING, None)
linked_model = None
if linked_model_label:
    try:
        linked_model = apps.get_model(linked_model_label)
    except (LookupError, ValueError):
        pass  # silently disabled

# 2. Flatten graph + populate linked_url
for entry in entries:
    entry["external_id"] = entry.get("external_id", "")
    entry["linked_url"] = None
    if linked_model and entry["external_id"]:
        app_label = linked_model._meta.app_label
        model_name = linked_model._meta.model_name
        try:
            linked_model.objects.get(pk=entry["external_id"])
            entry["linked_url"] = reverse(f"admin:{app_label}_{model_name}_change",
                                          args=[entry["external_id"]])
        except (linked_model.DoesNotExist, Exception):
            pass

# 3. Build item_relations dict
item_relations = {}
if show_relations:
    for entry in entries:
        if entry["kind"] == "item":
            links = svc.list_item_relations(UUID(entry["uuid"]))
            if links:
                item_relations[entry["uuid"]] = [...]
```

Note: The `show_relations` toggle is **client-side only** — all relation data is always sent
to the template (hidden by default via CSS/JS). This avoids a server round-trip on toggle.

### Admin graph: HTML/JS design

**[+]/[-] controls**: Each category entry (and items with relations when data is present)
gets a `<button class="taxomesh-toggle">[-]</button>` prepended. JS sets a
`data-collapsed` attribute on the control; a CSS rule hides `.taxomesh-entry`s whose
closest ancestor with `data-collapsed` is set. Implementation uses the sequential index
approach: JS assigns each entry a `data-index` and computes a `data-parent-index` from
the depth stack during page load.

**Relations toggle**: A `<label><input type="checkbox" id="taxomesh-show-relations">
Show item relations</label>` at the top of the graph. JS toggles a class on `#taxomesh-graph`
that shows/hides all `.taxomesh-relations` blocks (the per-item relation lists).

**Icon-link**: When `entry.linked_url` is set, render `<a href="..." title="View in admin">↗</a>`
as a small inline element after the label.

**Named constant**:
```python
TAXOMESH_LINKED_MODEL_SETTING: Final[str] = "TAXOMESH_LINKED_MODEL"
```
Defined in `taxomesh/contrib/django/admin.py` (or a `constants.py` within the contrib package).

## Complexity Tracking

No constitution violations.
