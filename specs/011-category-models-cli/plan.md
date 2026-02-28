# Implementation Plan: Category Fields, Models Refactor, CLI Output & Service Cache

**Branch**: `011-category-models-cli` | **Date**: 2026-02-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/011-category-models-cli/spec.md`

## Summary

Add `enabled` (bool, default `True`) and `external_id` (optional, default `""`) fields to the `Category` model, matching `Item`'s feature set. Refactor `taxomesh/domain/models.py` into a `models/` package with one module per class while preserving all existing import paths via `__init__.py` re-exports. Update `taxomesh graph` CLI output to replace `enabled=<value>` text with colored icons (green checkmark / red cross) and display `external_id` for both items and categories. Add a closure-based `memoize` decorator with TTL support in `taxomesh/utils/` and apply it to all read-only `TaxomeshService` methods with a 5-second default TTL. All write operations on the service clear the entire read cache.

## Technical Context

**Language/Version**: Python 3.11 (targets 3.11–3.13)
**Primary Dependencies**: Pydantic v2 (domain models), Typer ≥ 0.12 (CLI), Rich ≥ 13.0 (terminal rendering), `time.monotonic` (TTL clock — stdlib)
**Storage**: JsonRepository (JSON file), YAMLRepository (YAML file) — both must persist new Category fields
**Testing**: pytest + pytest-cov (≥ 80% coverage), TDD mandatory
**Target Platform**: Cross-platform CLI (macOS, Linux, Windows)
**Project Type**: Library + CLI
**Constraints**: All existing `from taxomesh.domain.models import X` imports must resolve after refactor. Memoize uses closure-based design (justified Principle XI exception). Write operations invalidate the entire read cache.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Hexagonal Architecture | PASS | Changes stay within domain (models), adapters (CLI, repositories), application (service cache), and utils (cross-cutting). `utils/` has no layer-violating imports. |
| II. Single Public Facade | PASS | `TaxomeshService` gains `@memoize` decorators on existing methods + cache invalidation in write methods — no new public API surface. |
| III. Repository as Protocol | PASS | No protocol changes needed — repositories already persist Category objects via Pydantic. |
| IV. Pydantic Domain Models + mypy Strict | PASS | New fields use Pydantic + `ExternalId` type alias. `memoize` will be typed with `ParamSpec`/`TypeVar` for mypy strict. |
| V. Custom Exception Hierarchy | PASS | No new exceptions needed. |
| VI. DAG Integrity | PASS | No changes to DAG logic. |
| VII. Spec-Driven Development | PASS | Spec and plan exist before implementation. |
| VIII. Quality Gates | PASS | All gates will run: ruff, mypy --strict, pytest --cov. |
| IX. Pluggable REST Views | N/A | No REST changes in this feature. |
| X. Named Constants | PASS | Icon characters, default TTL will use `Final` named constants. |
| XI. Object-Oriented by Default | PASS (exception) | Two justified exceptions: (1) `memoize` decorator uses closure-based design — idiomatic Python pattern; class-based would add unnecessary complexity (documented in spec FR-016). (2) `_cache_registry: list[...] = []` in `memoize.py` is module-level mutable state, required to support `clear_all_caches()` across all decorated functions. A class-based `MemoizeRegistry` singleton would satisfy XI fully but add indirection with no benefit — the registry is an implementation detail of the decorator mechanism and has no reason to be a public class. Both exceptions are documented and intentional. |

## Project Structure

### Documentation (this feature)

```text
specs/011-category-models-cli/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── cli-output.md
└── checklists/
    └── requirements.md  # Pre-existing
```

### Source Code (repository root)

```text
taxomesh/domain/
├── models/              # NEW — replaces models.py
│   ├── __init__.py      # Re-exports all public names
│   ├── base.py          # ModelBase
│   ├── item.py          # Item
│   ├── category.py      # Category (with new enabled + external_id)
│   ├── tag.py           # Tag
│   ├── category_parent_link.py  # CategoryParentLink
│   ├── item_parent_link.py      # ItemParentLink
│   └── item_tag_link.py         # ItemTagLink
├── dag.py               # Unchanged
├── graph.py             # Unchanged
└── types.py             # Unchanged

taxomesh/utils/           # NEW — cross-cutting utilities
├── __init__.py
└── memoize.py           # memoize decorator with TTL + clear_all_caches()

taxomesh/adapters/cli/
└── main.py              # Modified — _add_graph_node() updated

taxomesh/application/
└── service.py           # Modified — @memoize on read-only methods,
                         #   cache invalidation in write methods,
                         #   DEFAULT_CACHE_TTL constant

tests/
├── domain/
│   └── test_models.py   # Updated for new Category fields
├── utils/
│   └── test_memoize.py  # NEW — memoize decorator + cache invalidation tests
└── service/
    ├── test_service_cache.py  # NEW — service-level cache tests
    └── (existing test files)
```

**Structure Decision**: Single project layout. The `models/` package replaces the single `models.py` file. A new `utils/` package is introduced for the `memoize` decorator. Each model class gets its own module. The `__init__.py` re-exports preserve backward compatibility.

## Cache Invalidation Design

The `memoize` decorator exposes a `clear_cache()` function on each wrapped function. Additionally, a module-level registry in `memoize.py` tracks all decorated functions, providing a `clear_all_caches()` function that clears every registered cache in one call.

**Write methods that call `clear_all_caches()`** (13 total):
- `create_category`, `update_category`, `delete_category`
- `create_item`, `update_item`, `delete_item`
- `create_tag`, `update_tag`, `delete_tag`
- `assign_tag`, `remove_tag`
- `add_category_parent`, `place_item_in_category`

Each write method calls `clear_all_caches()` after the write succeeds (not before), ensuring the cache is only cleared when data actually changes.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Closure-based `memoize` (Principle XI exception) | Idiomatic Python decorator pattern; `time.monotonic` + dict cache in closure | Class-based decorator adds boilerplate (`__init__`, `__call__`, `__get__` for descriptor protocol) with no benefit — less readable for a standard decorator use case |
