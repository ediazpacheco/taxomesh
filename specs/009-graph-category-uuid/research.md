# Research: Graph Category UUID Display

**Feature**: 009-graph-category-uuid
**Date**: 2026-02-26

## Research Summary

No unknowns or NEEDS CLARIFICATION items existed in the technical context.
This is a minimal display-only change. Research confirmed the following:

### Decision 1: UUID Display Style

**Decision**: Use `[dim]` Rich markup for the category UUID.
**Rationale**: This matches the existing pattern for `item_id` display on item
lines (line 433 of `main.py`: `[dim]{item.item_id}[/dim]`). Consistency with
the existing visual language is the strongest UX choice.
**Alternatives considered**:
- `[italic dim]` — adds no value, deviates from item pattern
- `[cyan dim]` — could confuse with bold cyan category name
- Parentheses wrapping `(uuid)` — adds visual noise, not used for items

### Decision 2: Separator Between Name and UUID

**Decision**: Two spaces (`"  "`), matching the item line separator.
**Rationale**: Item lines use two-space separation between `external_id`,
`item_id`, and `enabled` status. Same convention applies.
**Alternatives considered**:
- Single space — too tight, hard to distinguish visually
- Tab — inconsistent with existing Rich tree rendering
- Dash/pipe separator — adds visual noise

### Decision 3: No New CLI Flags

**Decision**: Always show the UUID; no `--show-uuid` / `--hide-uuid` flag.
**Rationale**: Item UUIDs are always shown. Category UUIDs should follow the
same convention. Adding a flag for this is YAGNI.
