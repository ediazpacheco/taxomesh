# Research: Remove Redundant Item Relation Link Models Inline

**Feature**: 048-remove-item-relations-inline
**Date**: 2026-03-22

## Summary

No external research required. All decisions are derivable from reading the existing code.

---

## Finding 1: What "Item relation link models" actually is

**Decision**: The section labeled "Item relation link models" on the item change page is rendered by `IncomingRelationInline` — a `TabularInline` registered on `ItemModelAdmin` with `fk_name = "target_item"`. Because the class does not set `verbose_name` or `verbose_name_plural`, Django auto-generates the label from the model's class name (`ItemRelationLinkModel` → "item relation link model" / "item relation link models").

**Rationale**: Confirmed by reading `admin.py` lines 1391–1397 and cross-referencing with `ItemModelAdmin.inlines` at line 1413.

**Alternatives considered**: None — this is a factual finding, not a design choice.

---

## Finding 2: Scope of the deletion

**Decision**: Delete the `IncomingRelationInline` class entirely (not just remove it from `inlines`). It becomes dead code the moment it is removed from the `inlines` list.

**Rationale**: YAGNI. No other code references the class. Keeping dead classes violates the project's KISS principle.

**Alternatives considered**: Keeping the class but removing it from `inlines` — rejected because it leaves unreachable dead code.

---

## Finding 3: Test impact

**Decision**: Two existing tests reference `IncomingRelationInline` and must be updated:
- `test_incoming_inline_registered_on_item_admin` — asserts the inline IS registered; must become an assertion that it is NOT.
- `test_incoming_inline_is_read_only` — tests a class that will no longer exist; must be deleted.

A replacement test (`test_incoming_inline_not_registered_on_item_admin`) verifies that no inline on `ItemModelAdmin` targets `ItemRelationLinkModel` via `fk_name = "target_item"`.

**Rationale**: The spec's SC-001 requires that the incoming-relation section is absent. Tests must enforce this.

**Alternatives considered**: Deleting both tests without replacement — rejected because the spec requires verifiable absence; a regression test is needed.
