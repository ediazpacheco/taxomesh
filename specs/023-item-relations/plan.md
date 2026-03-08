# Implementation Plan: Item-to-Item Relations (ItemRelationLink)

**Branch**: `023-item-relations` | **Date**: 2026-03-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/023-item-relations/spec.md`

## Summary

Add a directed, typed item-to-item relation system to taxomesh. A new `ItemRelationLink`
domain model captures `(source_item_id, target_item_id, relation_type)` as the composite
key with optional `sort_index` and `metadata`. The feature extends the repository protocol
and `TaxomeshService`, is persisted in JSON/YAML/Django backends, exposed via CLI command
group `taxomesh relation`, and surfaced in Django admin. Relations cascade when an item is
deleted.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Pydantic v2, Typer ≥ 0.12, Rich ≥ 13.0, Django ≥ 4.2 (optional contrib)
**Storage**: JSON file (`JsonRepository`), YAML file (`YAMLRepository`), Django ORM (`DjangoRepository`)
**Testing**: pytest + pytest-cov (≥ 80% coverage required)
**Target Platform**: Library — any POSIX/Windows Python 3.11+ environment
**Project Type**: Library (with optional CLI and Django contrib)
**Performance Goals**: No specific targets — standard library-call latency acceptable
**Constraints**: mypy strict, ruff clean, no magic literals, OO by default, line length 119
**Scale/Scope**: Adds one new domain model, three new repository methods, four new service
methods, one new CLI command group (4 subcommands), one new Django ORM model, and admin
inline updates

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I — Hexagonal Architecture | ✅ PASS | `ItemRelationLink` in `domain/models/`; protocol methods in `ports/`; service in `application/`; all adapters implement inward |
| II — TaxomeshService is Single Facade | ✅ PASS | Four new methods added to `TaxomeshService`; no other public entry point |
| III — Repository as Protocol | ✅ PASS | Three new methods added to `TaxomeshRepositoryBase`; all three backends implement them |
| IV — Pydantic + mypy strict | ✅ PASS | `ItemRelationLink` is a Pydantic `BaseModel`; `relation_type` has `max_length`; `direction` typed as `Literal["outgoing", "incoming"]` |
| V — Custom Exception Hierarchy | ✅ PASS | New `TaxomeshRelationError(TaxomeshValidationError)` covers self-relation and empty-type errors |
| VI — DAG Integrity | N/A | Item relations are not DAG-constrained; no cycle detection required |
| VII — Spec-Driven Development | ✅ PASS | Spec exists at `specs/023-item-relations/spec.md` |
| VIII — Quality Gates | ✅ MUST VERIFY | ruff, mypy --strict, pytest ≥ 80% coverage — all gates must pass before merge |
| IX — Pluggable REST Views | N/A | No REST API surface for relations in this spec |
| X — Named Constants | ✅ PASS | `DIRECTION_OUTGOING`, `DIRECTION_INCOMING`, `RELATION_TYPE_MAX_LENGTH` defined as `Final` constants; no magic literals |
| XI — OO by Default | ✅ PASS | All new logic encapsulated in classes; no module-level stateful functions |

**Post-design re-check**: No violations detected. Complexity Tracking table not required.

## Project Structure

### Documentation (this feature)

```text
specs/023-item-relations/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── python-api.md
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
taxomesh/
├── __init__.py                                    # MODIFY — export TaxomeshRelationError
├── exceptions.py                                  # MODIFY — add TaxomeshRelationError
├── domain/
│   ├── constants.py                               # MODIFY — add DIRECTION_*, RELATION_TYPE_MAX_LENGTH
│   └── models/
│       ├── __init__.py                            # MODIFY — export ItemRelationLink
│       └── item_relation_link.py                  # NEW — ItemRelationLink domain model
├── ports/
│   └── repository.py                              # MODIFY — add 3 new protocol methods
├── application/
│   └── service.py                                 # MODIFY — add 4 new methods + cascade in delete_item
├── adapters/
│   ├── repositories/
│   │   ├── json_repository.py                     # MODIFY — add _item_relation_links + 3 methods + cascade
│   │   ├── yaml_repository.py                     # MODIFY — same pattern as JSON
│   │   └── django_repository.py                   # MODIFY — implement 3 new methods (cascade via DB FK)
│   └── cli/
│       └── main.py                                # MODIFY — add relation_app Typer group + 4 commands
└── contrib/
    └── django/
        ├── models.py                              # MODIFY — add ItemRelationLinkModel
        ├── admin.py                               # MODIFY — add ItemRelationLinkModelAdmin + inlines
        └── migrations/
            └── 0003_item_relation_link.py         # NEW — Django migration

tests/
├── unit/
│   └── test_item_relation_link_model.py           # NEW — domain model validation unit tests
└── integration/
    ├── test_service_item_relations.py             # NEW — service API integration tests
    ├── test_json_repository_relations.py          # NEW — JSON backend relation tests
    ├── test_yaml_repository_relations.py          # NEW — YAML backend relation tests
    ├── test_django_repository_relations.py        # NEW — Django backend relation tests
    └── test_cli_relations.py                      # NEW — CLI command tests

README.md                                          # MODIFY — document ItemRelationLink
```

**Structure Decision**: Single project layout. No new top-level directories. All code follows
existing module placement conventions.
