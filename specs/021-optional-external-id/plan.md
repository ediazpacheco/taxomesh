# Implementation Plan: Optional Item external_id

**Branch**: `021-optional-external-id` | **Date**: 2026-03-02 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/021-optional-external-id/spec.md`

## Summary

`Item.external_id` is an escape hatch for linking an item to an external entity. It should be
optional: items can exist without any external reference. Currently the field is required in the
domain model, the service facade, the CLI command, and the Django ORM model, which prevents
creating items via the admin (or programmatically) before the external entity exists.

The fix adds `DEFAULT_ITEM_EXTERNAL_ID = ""` as a named constant and propagates the default
through all four layers. A Django migration reflects the ORM change. No storage format changes
and no API renames are required.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Pydantic v2 (domain models), Django ≥ 4.2 (ORM + admin), Typer ≥ 0.12 (CLI)
**Storage**: Django ORM (`ItemModel`) — migration required; JSON/YAML repositories — no change
**Testing**: pytest, pytest-cov
**Target Platform**: Library (importable) + Django contrib app + CLI
**Project Type**: Library
**Performance Goals**: N/A — field-default change; no performance impact
**Constraints**: Migration must apply cleanly on both empty and populated databases
**Scale/Scope**: Five files changed; one migration generated

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I — Hexagonal Architecture | ✅ Pass | All changes stay within their own layer; no cross-layer imports added |
| II — TaxomeshService is the single facade | ✅ Pass | `create_item` signature relaxed; no new entry points |
| III — Repository as Protocol | ✅ Pass | Protocol unchanged |
| IV — Pydantic + mypy strict | ✅ Pass | Adding a field default is valid Pydantic; `mypy --strict` will pass |
| V — Custom exception hierarchy | ✅ Pass | No new exceptions; no silent failures introduced |
| VI — DAG integrity | ✅ Pass | Not applicable |
| VII — Spec-driven development | ✅ Pass | Spec written before implementation |
| VIII — Quality gates | ✅ Pass | Tests + migration required; CI must stay green |
| IX — Pluggable REST views | ✅ Pass | Not applicable |
| X — Named constants | ✅ Pass | `DEFAULT_ITEM_EXTERNAL_ID` constant defined; no magic literal |
| XI — OO by default | ✅ Pass | No structural changes to classes |

**No violations. No Complexity Tracking required.**

## Project Structure

### Documentation (this feature)

```text
specs/021-optional-external-id/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
└── tasks.md             ← Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
taxomesh/
├── domain/
│   ├── constants.py                   # + DEFAULT_ITEM_EXTERNAL_ID
│   └── models/
│       └── item.py                    # external_id default added
├── application/
│   └── service.py                     # create_item external_id default added
├── adapters/
│   └── cli/
│       └── main.py                    # item add --external-id made optional
└── contrib/
    └── django/
        ├── models.py                  # ItemModel.external_id: blank=True, default=""
        └── migrations/
            └── 0002_alter_itemmodel_external_id.py   # new migration

tests/
├── unit/
│   └── test_item_model.py             # new: test Item constructed without external_id
└── integration/
    └── test_service_create_item.py    # new: test create_item without external_id
```

**Structure Decision**: Single-project layout (existing); no new packages or directories.

## Implementation Phases

### Phase 0 — Complete (research.md)

All unknowns resolved. See [research.md](research.md).

Key decisions:
- R-001: Fix all four layers atomically (domain model, service, CLI, Django ORM + migration)
- R-002: Introduce `DEFAULT_ITEM_EXTERNAL_ID: Final[str] = ""`
- R-003: Make `create_item(external_id=...)` optional in the service
- R-004: `AlterField` migration; column stays `VARCHAR NOT NULL`

### Phase 1 — Complete (data-model.md, quickstart.md)

See [data-model.md](data-model.md) and [quickstart.md](quickstart.md).

Five files change, in dependency order:

| # | File | Change |
|---|------|--------|
| 1 | `domain/constants.py` | Add `DEFAULT_ITEM_EXTERNAL_ID: Final[str] = ""` |
| 2 | `domain/models/item.py` | `external_id` field gets `= DEFAULT_ITEM_EXTERNAL_ID` |
| 3 | `application/service.py` | `create_item` gets `external_id: ExternalId = DEFAULT_ITEM_EXTERNAL_ID` |
| 4 | `adapters/cli/main.py` | `--external-id` option default changes from `...` to `""` |
| 5 | `contrib/django/models.py` | `ItemModel.external_id` gets `blank=True, default=""` |
| 6 | `contrib/django/migrations/0002_…` | `AlterField` migration (new file) |

No contracts directory — no public API surface changes (no new methods, no changed return types).
