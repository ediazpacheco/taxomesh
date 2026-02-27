# Implementation Plan: Graph Category UUID Display

**Branch**: `009-graph-category-uuid` | **Date**: 2026-02-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/009-graph-category-uuid/spec.md`

## Summary

Display the `category_id` (UUID) on each category line in the `taxomesh graph`
CLI output, matching the dim style already used for `item_id` on item lines.
This is a single-line change in the `_add_graph_node()` helper function in the
CLI adapter module, plus corresponding test additions.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Typer ≥ 0.12, Rich ≥ 13.0
**Storage**: N/A — display-only change, no storage impact
**Testing**: pytest + pytest-cov
**Target Platform**: CLI (cross-platform terminal)
**Project Type**: Library / CLI
**Performance Goals**: N/A — negligible impact (string formatting)
**Constraints**: None
**Scale/Scope**: Single function change + test additions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Hexagonal Architecture | ✅ Pass | Change is in adapters/cli layer only; no domain changes |
| II. Single Public Facade | ✅ Pass | No service API changes |
| III. Repository as Protocol | ✅ Pass | No repository changes |
| IV. Pydantic Models + mypy | ✅ Pass | No model changes; `category_id` is already `UUID` type |
| V. Custom Exceptions | ✅ Pass | No new error paths |
| VI. DAG Integrity | ✅ Pass | No write operations affected |
| VII. Spec-Driven Dev | ✅ Pass | This spec exists |
| VIII. Quality Gates | ✅ Pass | Will run ruff, mypy, pytest before merge |
| IX. Pluggable REST Views | ✅ Pass | No API changes |
| X. Named Constants | ✅ Pass | No new magic literals introduced (UUID style already follows dim pattern) |
| XI. OOP by Default | ✅ Pass | Change is in an existing module-level helper function; no new stateful logic |

No violations. No complexity tracking needed.

## Project Structure

### Documentation (this feature)

```text
specs/009-graph-category-uuid/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
taxomesh/
└── adapters/
    └── cli/
        └── main.py          # _add_graph_node() — line 428 modified

tests/
└── test_cli.py              # new test: test_graph_shows_category_uuid()
```

**Structure Decision**: No new files or directories needed. Single modification
to the existing CLI adapter module and one new test function in the existing
test file.

## Implementation Approach

### Change Detail

**File**: `taxomesh/adapters/cli/main.py`, function `_add_graph_node()` (line 428)

**Current**:
```python
branch = tree_node.add(f"[bold cyan]{category_node.category.name}[/bold cyan]")
```

**After**:
```python
branch = tree_node.add(
    f"[bold cyan]{category_node.category.name}[/bold cyan]"
    f"  [dim]{category_node.category.category_id}[/dim]"
)
```

This mirrors the existing item pattern where `item_id` is rendered in `[dim]`
style with two-space separation.

### Test Addition

**File**: `tests/test_cli.py`

New test `test_graph_shows_category_uuid()` — creates a category, runs
`taxomesh graph`, asserts `str(cat.category_id)` appears in output. Follows
the exact same pattern as `test_graph_shows_item_item_id()`.
