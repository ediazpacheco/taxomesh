# Research: Taxonomy Graph (006-taxonomy-graph)

**Date**: 2026-02-24 | **Branch**: `006-taxonomy-graph`

---

## R-001: Terminal Rendering Library

**Question**: Should the `graph` CLI command use `rich`, Typer's built-in ANSI helpers, or raw escape codes?

**Decision**: Add `rich >= 13.0` as an explicit runtime dependency.

**Rationale**:
- `rich.tree.Tree` provides out-of-the-box tree connectors (│, ├──, └──) with no manual rendering code.
- Rich markup (`[bold cyan]`, `[yellow]`) is clear and testable (markup strings appear in captured output when `Console(markup=True)` is used).
- Typer ≥ 0.12 supports Rich optionally; our use requires it explicitly.
- Raw ANSI codes satisfy color but require manual tree-connector logic — poor ROI for this scope.

**Alternatives considered**:
- *Typer `typer.style()` only*: provides foreground colors but no tree connectors.
- *`curses`*: far too heavy for a one-shot display command.
- *`colorama`*: Windows ANSI shim, but provides no tree structure.

---

## R-002: Top-Level vs Child Category Display Logic

**Question**: Because every category is auto-linked to root, how do we decide which categories are "top-level" (shown at root of tree) vs "child-only" (shown only under their explicit parents)?

**Decision**: A category is **top-level** if and only if it has NO explicit parent links (i.e., its only `CategoryParentLink` has `parent_category_id == _root_id`). A category with one or more explicit parents appears **only** under those explicit parents — never also at the top level.

**Rationale**:
- This matches user mental model: explicitly nesting "Mammals" under "Animals" means "Mammals" should not also float at the root level.
- Categories with multiple explicit parents appear under each (the "repeated under each parent" requirement from spec Clarification and FR-005/FR-002).
- Simple set-difference: `top_level = {c for c in root_link_category_ids} - {c for c in explicit_link_category_ids}`.

**Alternatives considered**:
- *Show all categories at top-level AND under explicit parents*: confusing duplication, violates user expectations.
- *Show only categories with no links at top-level (strict tree)*: breaks multi-parent DAG semantics.

---

## R-003: TaxomeshGraph / CategoryNode Type

**Question**: Should `TaxomeshGraph` and `CategoryNode` be Pydantic `BaseModel` subclasses (like core domain entities) or Python `@dataclass` instances?

**Decision**: Use Python `@dataclass` (stdlib, no Pydantic).

**Rationale**:
- Constitution Principle IV lists the core domain entities as Pydantic models: `Item`, `Category`, `Tag`, `CategoryParentLink`. `TaxomeshGraph` and `CategoryNode` are **read-model aggregates**, not entities — analogous to `BuildResult` in `adapters/cli/config.py` which also uses `@dataclass`.
- `CategoryNode` is recursive (`children: list[CategoryNode]`). Pydantic v2 handles this via `model_rebuild()`, but it adds boilerplate and the type is never serialised or validated at construction; `@dataclass` is simpler.
- These types are never persisted or deserialized from external input — they are always produced programmatically by `get_graph()`.

**Alternatives considered**:
- *Pydantic BaseModel with `model_rebuild()`*: works but adds unnecessary ceremony for a non-persisted aggregate.
- *`NamedTuple`*: recursive named tuples are awkward in Python.
- *Plain `dict`*: untyped, violates mypy strict, rejected.

**File placement**: New `taxomesh/domain/graph.py` (separate from `models.py` to keep entity models clean).

---

## R-004: Composition-Root Exception (carried forward)

**Status**: Already documented in prior feature plans. The lazy import of `JsonRepository` inside `TaxomeshService.__init__` is the sole `application → adapters` dependency, lives only in the `if repository is None:` guard, and is exempt per Constitution Principle I clause.

No change needed for this feature.

---

## R-005: `get_graph()` Return Scope — Root Visibility

**Question**: Should the `__root__` category appear anywhere in `TaxomeshGraph`?

**Decision**: Root is **completely hidden** from `TaxomeshGraph`. It is an internal implementation detail. The graph's top-level `roots` list contains the children of `__root__`, not `__root__` itself.

**Rationale**: Users never interact with `__root__` directly. Exposing it in the graph would confuse consumers and pollute the CLI display.
