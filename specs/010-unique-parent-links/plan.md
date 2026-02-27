# Implementation Plan: Unique Parent Link Constraint

**Branch**: `010-unique-parent-links` | **Date**: 2026-02-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/010-unique-parent-links/spec.md`

## Summary

Fix duplicate category-parent links by adding upsert semantics to
`save_category_parent_link()` in all repository implementations (JSON, YAML,
InMemory). The fix mirrors the existing `save_item_parent_link()` pattern:
match on composite key `(category_id, parent_category_id)`, update `sort_index`
in-place if found, otherwise append. Protocol docstring and service-level
docstrings updated to formalize idempotency.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Pydantic v2 (domain models)
**Storage**: JSON file (`JsonRepository`), YAML file (`YAMLRepository`), in-memory (test fixture)
**Testing**: pytest + pytest-cov
**Target Platform**: Cross-platform (library)
**Project Type**: Library + CLI
**Performance Goals**: N/A — correctness fix, no performance-sensitive path
**Constraints**: N/A
**Scale/Scope**: 3 repository implementations + 1 protocol docstring + 2 service docstrings

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Hexagonal Architecture | PASS | Changes are within adapters (repositories) and application (service docstring). No cross-layer violations. |
| II. Single Public Facade | PASS | No changes to `TaxomeshService` API surface — only docstring clarification. |
| III. Repository as Protocol | PASS | Protocol docstring updated; structural typing unaffected. |
| IV. Pydantic Models + mypy strict | PASS | No model changes. Existing `CategoryParentLink` model used as-is. |
| V. Custom Exceptions | PASS | No new exceptions; upsert is silent (per spec). |
| VI. DAG Integrity | PASS | `check_no_cycle()` continues to run before upsert. No change to cycle detection. |
| VII. Spec-Driven | PASS | Spec written at `specs/010-unique-parent-links/spec.md`. |
| VIII. Quality Gates | PASS | Will run ruff, mypy, pytest before merge. |
| IX. Pluggable REST Views | N/A | No API changes. |
| X. Named Constants | PASS | No new magic literals. |
| XI. Object-Oriented | PASS | Changes within existing classes. |

**Gate result**: PASS — no violations.

## Project Structure

### Documentation (this feature)

```text
specs/010-unique-parent-links/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── repository-protocol.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (files modified)

```text
taxomesh/
├── ports/
│   └── repository.py              # Protocol docstring update (save_category_parent_link)
├── adapters/
│   └── repositories/
│       ├── json_repository.py     # Upsert logic in save_category_parent_link()
│       └── yaml_repository.py     # Upsert logic in save_category_parent_link()
└── application/
    └── service.py                 # Docstring updates (add_category_parent, place_item_in_category)

tests/
└── service/
    └── conftest.py                # InMemoryRepository: upsert in save_category_parent_link()
```

**Structure Decision**: Existing hexagonal layout. No new files or directories
in source tree — only modifications to existing files.

## Complexity Tracking

> No violations to justify — all gates pass.
