# Research: Graph & Admin UX Improvements

**Branch**: `025-graph-admin-ux` | **Date**: 2026-03-08

## R-001: `--max-depth` Flag Name

**Decision**: `--max-depth INTEGER` (Typer option).

**Rationale**: `--max-depth` is the established convention across Unix tools (`find -maxdepth`,
`tree --max-depth`, `du --max-depth`). More readable than `--deep-level` or `--depth-level`.

**Alternatives considered**: `--depth-level` (user's suggestion), `--depth`, `--levels`.

## R-002: `max_depth = 0` Means Unlimited

**Decision**: `0` means "no limit". Any positive integer N limits output to depth ≤ N.

**Rationale**: Consistent with `find -maxdepth 0` semantics; avoids a `--no-max-depth` flag;
a single integer covers both cases.

**Named constants**: `MAX_DEPTH_UNLIMITED: Final[int] = 0`, `GRAPH_DEFAULT_MAX_DEPTH: Final[int] = 3`.

## R-003: Depth Convention

**Decision**: Root categories = depth 0. Items directly under a root = depth 1. Child categories
of root = depth 1; their items = depth 2. This is the convention already in `_flatten_graph`.

**Impact on `--max-depth 3`**: categories at depths 0, 1, 2 are shown; items at depths 1, 2, 3
are shown; depth-4 categories and depth-4 items are omitted.

## R-004: Relations Toggle Removal Strategy

**Decision**: Remove the global checkbox entirely. Each item with relations gets its own
per-item `[+]`/`[-]` toggle (already implemented in 024). Relations start collapsed. The JS
simplifies — no checkbox event listener needed; only per-item toggle buttons remain.

**Rationale**: Removing the toggle reduces UI complexity; relations are still accessible via
the per-item controls. Starting collapsed keeps the graph readable by default.

## R-005: `↗` Link in Admin List/Detail — `mark_safe` vs Template

**Decision**: Use a `ModelAdmin` method returning `mark_safe(html)` with `short_description`.

**Rationale**: Standard Django admin pattern for custom HTML columns; no template override
needed; works in both `list_display` and `readonly_fields`. The `format_html` helper from
`django.utils.html` is preferred over raw `mark_safe` for safety.

## R-006: Version Info Template Tag Strategy

**Decision**: Simple tag (`@register.simple_tag`) that returns a dict with `version` and
`backend` keys. Used as `{% taxomesh_version_info as info %}` in `app_index.html`.

**Rationale**: Keeps logic out of the template; no view override needed; `importlib.metadata`
is stdlib (Python 3.8+); `BASE_DIR` check is a standard Django pattern.

## R-007: `_resolve_linked_url` Shared Helper

**Decision**: Extract the linked-model URL resolution from `graph_view` into a module-level
helper `_resolve_linked_url(external_id: str) -> str | None`. Called by `graph_view` (per-entry
loop), `ItemModelAdmin.linked_object_url`, and `CategoryModelAdmin.linked_object_url`.

**Rationale**: DRY — same logic in three places would violate Principle X (no duplicate literals)
and Principle XI (shared code should be extracted). Private helper (underscore prefix) is fine
since it's stateless and has no domain responsibility.

## R-008: `ItemRelationLinkModelAdmin` Still Present

**Finding**: Confirmed via code inspection — `@admin.register(ItemRelationLinkModel)` is still
at lines 945–984 in `admin.py`. Prior removal attempt was reverted. This spec treats full
removal as in scope; the import of `ItemRelationLinkModel` must remain for inline/form use.
