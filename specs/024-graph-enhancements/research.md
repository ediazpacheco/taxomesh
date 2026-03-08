# Research: Graph Enhancements (CLI + Admin)

**Branch**: `024-graph-enhancements` | **Date**: 2026-03-08

## R-001: FR-004 Already Implemented

**Finding**: The admin graph template at
`taxomesh/contrib/django/templates/admin/taxomesh_contrib_django/graph.html`
already sets `text-decoration: none` on `.taxomesh-label a` and `text-decoration: underline`
on `.taxomesh-label a:hover`.

**Decision**: No code change required for FR-004.
**Rationale**: The requirement is already satisfied; touching it would be scope creep.

## R-002: Item Relations Service API

**Finding**: `TaxomeshService` already exposes:
- `list_item_relations(item_id, direction="outgoing") -> list[ItemRelationLink]`
- `list_related_items(item_id, direction="outgoing") -> list[Item]`

**Decision**: Use `list_item_relations` to get relation metadata (type, target UUID) and
`get_item(target_item_id)` to resolve target names. No new service methods needed.

**Rationale**: The existing API provides everything required. Adding a new method for
"all relations across the graph" would be premature given the current graph size expectations.

## R-003: Admin Expand/Collapse — Vanilla JS Approach

**Decision**: Depth-stack algorithm at page load.

Each `.taxomesh-entry` element receives a `data-idx` attribute (sequential integer).
On page load, JS walks the entries in order and builds a `parentIdx[]` array where
`parentIdx[i]` is the `data-idx` of the nearest ancestor (the most recent entry with
`depth < depth[i]`). Clicking `[-]` on entry N sets `data-collapsed-by="N"` on all
descendants; clicking `[+]` removes it. A CSS rule `[data-collapsed-by] { display: none }`
hides them. Nested collapses work because the outermost `data-collapsed-by` is already
hiding the row, so inner toggles are irrelevant visually.

**Rationale**: No dependencies; O(n) setup; handles arbitrary nesting depth; survives
the flat-list template structure without restructuring the context data.

## R-004: TAXOMESH_LINKED_MODEL Resolution

**Decision**: Read at request time using `django.conf.settings` and `django.apps.apps.get_model()`.
Resolve admin URL via `django.urls.reverse(f"admin:{app}_{model}_change", args=[pk])`.

If the model string is malformed, the app is not installed, or the instance does not exist,
the icon is silently suppressed (no exception propagated to the user).

**Rationale**: Standard Django pattern; zero additional dependencies; request-time reading
means changes are reflected without server restart.

**Lookup field**: Always `pk` (FR-013, user choice A). No secondary setting.

## R-005: Item Relations in Admin — Embedded vs. Separate Context

**Decision**: Pass item relations as a separate context dict
`item_relations: dict[str, list[dict[str, str]]]` (keyed by item UUID string), not embedded
in the flat `entries` list.

**Rationale**: Keeps `_flatten_graph` single-purpose. Template renders relations as a
hidden sub-block inside each item row, toggled by the JS checkbox — no structural change
to the entry list needed. The separate dict also makes testing each concern independently
straightforward.

## R-006: TypedDict for GraphEntry

**Decision**: Replace `list[dict[str, object]]` with `list[GraphEntry]` using a `TypedDict`
to satisfy `mypy --strict`.

**Rationale**: The current `dict[str, object]` type is too loose for strict mypy; a TypedDict
captures the exact shape of each entry, making template access safe and self-documenting.
