# Implementation Plan: Unified __str__ + Django Admin Graph Links

**Branch**: `022-unified-str-admin-links` | **Date**: 2026-03-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/022-unified-str-admin-links/spec.md`

## Summary

Make `Category.__str__` and `Item.__str__` the single source of truth for human-readable
representation. The new format conditionally includes `slug:`, `id:`, and `ext_id:` segments.
The Django admin `_flatten_graph` is simplified to call `str()` instead of extracting individual
fields, and the graph template wraps each label in an anchor tag linking to the admin change page.
The CLI already calls `str()`, so it gets the improvement for free.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Pydantic v2 (domain models), Django ≥ 4.2 (admin), Rich ≥ 13.0 (CLI)
**Storage**: N/A — no storage changes
**Testing**: pytest + pytest-cov
**Target Platform**: Python library (multi-platform)
**Project Type**: library + optional Django contrib
**Performance Goals**: N/A — pure behavioral and display change
**Constraints**: mypy --strict, ruff clean, ≥ 80% coverage
**Scale/Scope**: Small, focused — 6 files touched

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Hexagonal Architecture | ✅ PASS | `__str__` lives in `domain/`; admin simplification in adapter layer. No inward dependency violations. |
| IV. Pydantic + mypy strict | ✅ PASS | `__str__` is a regular method on Pydantic models; fully typed, no `Any`. |
| VII. Spec-Driven Development | ✅ PASS | Retroactive spec; the spec now exists before the PR is opened. |
| VIII. Quality Gates | ✅ PASS | 595 tests pass, 92% coverage, ruff clean, mypy clean. |
| X. Named Constants | ✅ PASS | No new magic literals introduced. |
| XI. OOP by Default | ✅ PASS | `__str__` is a method on a class. |

No violations. Complexity Tracking table not required.

## Project Structure

### Documentation (this feature)

```text
specs/022-unified-str-admin-links/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── checklists/
│   └── requirements.md
└── tasks.md             ← /speckit.tasks output
```

### Source Code (repository root)

```text
taxomesh/
├── domain/
│   └── models/
│       ├── category.py      ← __str__ updated
│       └── item.py          ← __str__ updated
├── contrib/
│   └── django/
│       ├── admin.py         ← _flatten_graph simplified
│       └── templates/admin/taxomesh_contrib_django/
│           └── graph.html   ← labels wrapped in <a> links; unused spans/CSS removed

tests/
├── domain/
│   ├── test_models.py       ← __str__ tests added
│   └── test_slug_field.py   ← existing __str__ tests updated to new format
└── adapters/cli/
    └── test_graph_output.py ← 1 test inverted (external_id now shown)
```

**Structure Decision**: Single project layout. All changes are minimal and contained to the
domain layer (models), one adapter (`django/admin.py`), one template, and tests.

## Phases

### Phase 0: Research

No unresolved unknowns. See `research.md` for the single decision recorded.

### Phase 1: Design

**`Category.__str__` contract**:
```
📂 <name> (slug: <slug> - id: <uuid> - ext_id: <external_id>)
```
Each of `slug:` and `ext_id:` segments is omitted when the corresponding field is falsy (`""`).
`id:` is always present.

**`Item.__str__` contract**: identical pattern with `🏷️` prefix and `item_id`.

**`_flatten_graph` contract**: each entry dict contains `depth`, `kind`, `name` (= `str(obj)`),
`uuid` (for admin URL construction), `enabled`. Keys `slug`, `external_id`, and `indent_em`
are removed.

**Django admin graph template**: each label is `<a href="{% url '..._change' entry.uuid %}">`.
Category URL name: `admin:taxomesh_contrib_django_categorymodel_change`.
Item URL name: `admin:taxomesh_contrib_django_itemmodel_change`.

See `data-model.md` for the formal string format specification.
