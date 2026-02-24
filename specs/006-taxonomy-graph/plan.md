# Implementation Plan: Taxonomy Graph

**Branch**: `006-taxonomy-graph` | **Date**: 2026-02-24 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/006-taxonomy-graph/spec.md`

> **Note on prior work**: FR-011–FR-014 (root category prerequisite) were implemented
> directly in this conversation before the formal SDD cycle was completed. All 200 tests
> pass and all quality gates are green. This plan covers the remaining scope:
> FR-001–FR-010 (`TaxomeshGraph` type, `get_graph()` service method, `graph` CLI command).

---

## Summary

Add a `TaxomeshGraph` read-only snapshot type to the domain layer, expose it via
`TaxomeshService.get_graph()`, and render it as a rich colour-coded tree in the terminal
via a new `graph` Typer command. The graph excludes the internal root category and tag data.
Rich ≥ 13.0 is added as a runtime dependency to provide the tree renderer.

---

## Technical Context

**Language/Version**: Python 3.11 (targets 3.11–3.13)
**Primary Dependencies**: Pydantic v2 (via FastAPI), Typer ≥ 0.12, Rich ≥ 13.0 (new)
**Storage**: Pluggable via `TaxomeshRepositoryBase` (default: `JsonRepository`)
**Testing**: pytest + pytest-cov, `InMemoryRepository` fixture, `typer.testing.CliRunner`
**Target Platform**: Any ANSI-capable terminal (Linux/macOS/Windows Terminal)
**Project Type**: Python library + CLI tool
**Performance Goals**: `get_graph()` + `graph` render within 3 seconds for ≤ 50 categories / 200 items (SC-005)
**Constraints**: No external I/O beyond repository reads; must pass mypy --strict
**Scale/Scope**: ≤ 50 categories, ≤ 200 items for typical use; no hard upper limit imposed by code

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I — Hexagonal architecture | `TaxomeshGraph`/`CategoryNode` live in `domain/`; `get_graph()` in `application/`; CLI render in `adapters/cli/` | ✅ |
| II — TaxomeshService is the single facade | `get_graph()` is a method on `TaxomeshService`, not a new class | ✅ |
| III — Protocol structural typing | No changes to repository protocol; `get_graph()` reads via existing protocol methods | ✅ |
| IV — Pydantic domain models + mypy strict | Core entities unchanged; `CategoryNode`/`TaxomeshGraph` are `@dataclass` aggregates (not new entity types) — see research.md decision R-003 | ✅ |
| V — Custom exception hierarchy | No new exceptions needed; `get_graph()` raises existing errors only | ✅ |
| VI — DAG integrity in domain layer | `get_graph()` reads existing links; no writes; cycle-detection unchanged | ✅ |
| VII — Spec-driven development | Retroactive plan for root-category work; FR-001–FR-010 now planned before implementation | ✅ |
| VIII — Quality gates | All gates currently green; new code must maintain ≥ 80% coverage | ✅ |
| IX — Pluggable REST views | Out of scope for this feature | N/A |

---

## Project Structure

### Documentation (this feature)

```text
specs/006-taxonomy-graph/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── service-api.md
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (affected paths)

```text
taxomesh/
├── domain/
│   ├── models.py          # unchanged
│   └── graph.py           # NEW — CategoryNode, TaxomeshGraph
├── application/
│   └── service.py         # MODIFIED — add get_graph()
├── adapters/
│   └── cli/
│       └── main.py        # MODIFIED — add graph command
└── exceptions.py          # unchanged (no new exceptions needed)

tests/
├── service/
│   └── test_service_graph.py   # NEW — get_graph() tests
└── test_cli.py                 # MODIFIED — add graph CLI tests
```

**Structure Decision**: Single-project layout (existing). Two new files, two modified files.

---

## Complexity Tracking

No constitution violations.

---

## Phases

### Phase 0 (complete) — Research

See `research.md` for full decisions. Summary:

| Decision ID | Question | Resolution |
|---|---|---|
| R-001 | Terminal rendering library | `rich` (explicit dep) — see research.md |
| R-002 | Top-level vs child category logic | Root-link-only → top-level; has explicit parent(s) → child only |
| R-003 | TaxomeshGraph / CategoryNode type | Python `@dataclass` (not Pydantic) — see research.md |
| R-004 | Composition-root exception (already documented for root-category work) | Carries forward unchanged |

### Phase 1 (complete) — Design

See `data-model.md` for entity design and `contracts/service-api.md` for the public API contract.

---

## Implementation Design

### New type: `taxomesh/domain/graph.py`

```python
from __future__ import annotations
from dataclasses import dataclass, field
from taxomesh.domain.models import Category, Item

@dataclass
class CategoryNode:
    category: Category
    items: list[Item]          # ordered by sort_index within this category
    children: list[CategoryNode]  # ordered by sort_index

@dataclass
class TaxomeshGraph:
    roots: list[CategoryNode]  # top-level categories (root-only parents), sorted by sort_index
```

### Service method: `TaxomeshService.get_graph()`

**Algorithm** (all reads, no writes):

1. Call `self._repo.list_categories()` → filter out root (by `_root_id`).
2. Call `self._repo.list_category_parent_links()` → split into:
   - `root_links`: `parent_category_id == self._root_id`
   - `explicit_links`: all others
3. **Top-level categories**: UUIDs that appear in `root_links` but NOT as `category_id`
   in any `explicit_links` record.
4. Call `self._repo.list_item_parent_links()` + `self._repo.list_items()`.
5. Build `items_by_cat: dict[UUID, list[Item]]` — per-category item lists,
   each sorted by `sort_index` ascending.
6. Build `children_by_parent: dict[UUID, list[tuple[int, Category]]]` — for each
   `explicit_link`, record `(sort_index, child_category)` under `parent_category_id`.
7. Recursively build `CategoryNode` tree:
   - Top-level `roots` = children of root, sorted by their `root_link.sort_index`.
   - `_build_node(cat)`: creates `CategoryNode(cat, items_by_cat[cat.id],
     [_build_node(child) for child sorted by sort_index])`.
8. Return `TaxomeshGraph(roots=roots)`.

**Signature**:
```python
def get_graph(self) -> TaxomeshGraph: ...
```

No arguments. No exceptions beyond existing repository errors.

### CLI command: `taxomesh graph`

```python
@app.command("graph")
def graph_cmd(ctx: typer.Context) -> None:
    """Display the full taxonomy as a colour-coded tree."""
```

**Rendering** (using `rich`):
- Empty graph → `typer.echo("No categories found.")` then exit 0.
- Non-empty → build `rich.tree.Tree` rooted at `"Taxonomy"` label.
- For each top-level `CategoryNode`: add a styled branch (bold cyan category name).
- For each `item` under a node: add a leaf showing all three fields:
  `[yellow]{item.external_id}[/yellow]  [dim]{item.item_id}[/dim]  [green]enabled=True[/green]`
  or `[yellow]{item.external_id}[/yellow]  [dim]{item.item_id}[/dim]  [red]enabled=False[/red]`
- Recursively add child `CategoryNode` branches.
- Print with `rich.console.Console().print(tree)`.

**Color scheme** (ANSI-safe, tested via output markers):
- Root tree label: bold white
- Category names: `[bold cyan]`
- Item `external_id`: `[yellow]`
- Item `item_id`: `[dim]`
- `enabled=True`: `[green]`
- `enabled=False`: `[red]`

**Empty taxonomy message**: `"No categories found. Add one with: taxomesh category add --name <name>"`

---

## Out of Scope (this plan)

- Filtering / subtree views
- Exporting to file
- Interactive navigation
- Non-ANSI fallback
- Tag data
