# Implementation Plan: Remove Redundant Item Relation Link Models Inline

**Branch**: `048-remove-item-relations-inline` | **Date**: 2026-03-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/048-remove-item-relations-inline/spec.md`

## Summary

Remove `IncomingRelationInline` from the Django admin item change page. The inline currently
renders a read-only "Item relation link models" section (incoming relations where the item is
the target). This is redundant — outgoing relations are already managed via "Items related with"
(`OutgoingRelationInline`), and incoming relations are visible from the related item's own page.
The change deletes the inline class and removes it from `ItemModelAdmin.inlines`. Two existing
tests are updated; one regression test is added.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Django ≥ 4.2 (admin inline framework)
**Storage**: N/A — no model or migration changes
**Testing**: pytest + pytest-django
**Target Platform**: Django admin (web)
**Project Type**: Library with optional Django contrib
**Performance Goals**: N/A
**Constraints**: N/A
**Scale/Scope**: Single class removed from one file; two test edits + one new test

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I — Hexagonal Architecture | ✅ Pass | Change is in `contrib/django/admin.py` (adapter layer); no domain or application layer touched |
| II — TaxomeshService is single facade | ✅ Pass | No service changes |
| III — Repository as Protocol | ✅ Pass | No repository changes |
| IV — Pydantic models + mypy strict | ✅ Pass | No domain model changes |
| V — Custom exception hierarchy | ✅ Pass | No exception changes |
| VI — DAG integrity | ✅ Pass | No category/DAG logic changes |
| VII — Spec-Driven Development | ✅ Pass | Spec exists |
| VIII — Quality gates | ✅ Pass | Deletion + test update; all gates trivially satisfied |
| IX — Framework-agnostic HTTP handlers | ✅ Pass | Not applicable |
| X — Named constants | ✅ Pass | No magic literals introduced |
| XI — OO by default | ✅ Pass | Deleting a class is consistent; no new module-level functions |

**No violations. No complexity justification required.**

## Project Structure

### Documentation (this feature)

```text
specs/048-remove-item-relations-inline/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
└── tasks.md             ← Phase 2 output (/speckit.tasks)
```

### Source Code (affected files only)

```text
taxomesh/contrib/django/
└── admin.py             ← delete IncomingRelationInline class + remove from ItemModelAdmin.inlines

tests/contrib/django/
└── test_admin_relations.py  ← update 2 tests, add 1 regression test
```

## Implementation Steps

### Step 1 — Update tests (TDD: write/update tests first)

File: `tests/contrib/django/test_admin_relations.py`

1. **Replace** `test_incoming_inline_registered_on_item_admin` with
   `test_incoming_inline_not_registered_on_item_admin`:
   - Instantiate `ItemModelAdmin`
   - Call `get_inline_instances(mock_request)`
   - Assert that no inline instance targets `ItemRelationLinkModel` with `fk_name == "target_item"`

2. **Delete** `test_incoming_inline_is_read_only` — tests a class that will no longer exist.

Expected state after Step 1: two tests reference `IncomingRelationInline` (will fail until Step 2 removes the class from the inline list and deletes it).

### Step 2 — Remove IncomingRelationInline from admin

File: `taxomesh/contrib/django/admin.py`

1. **Delete** the `IncomingRelationInline` class (lines ~1391–1397).
2. **Remove** `IncomingRelationInline` from `ItemModelAdmin.inlines` (line ~1413).

Expected state after Step 2: all tests pass; no incoming-relation inline visible on item change page.

### Step 3 — Quality gates

```bash
ruff check .
ruff format --check .
mypy --strict .
pytest --cov=taxomesh --cov-fail-under=80
```

All gates must pass before proposing a commit.
