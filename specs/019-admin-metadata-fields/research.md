# Research: Admin Metadata Fields

**Feature**: 019-admin-metadata-fields
**Date**: 2026-03-01

## Decision 1: Service layer extension for metadata on update

**Decision**: Add `metadata: dict[str, Any] | None = None` to `service.update_category` and
`service.update_item`. When `None`, the field is left unchanged on the existing record.

**Rationale**: The admin's `save_model` methods route all persistence through `TaxomeshService`
(Constitution Principle II). Without a `metadata` parameter on the update methods, edits made to
`metadata` in the admin form would be silently lost — the service re-fetches the record from the
repository and persists only the fields it is aware of. Extending the service methods is the
minimal, architecturally correct fix.

**Alternatives considered**:
- **Bypass service, call `obj.save()` directly for metadata**: Rejected — violates the
  established pattern where all mutations go through the service layer. Introduces a split
  persistence path that could cause consistency issues.
- **Make metadata read-only in admin**: Rejected — FR-004 explicitly requires edit capability.
- **Separate `update_category_metadata` service method**: Rejected — over-engineering. A single
  optional parameter on the existing method is simpler and consistent with how `name`, `slug`,
  and `description` are handled (all optional on update).

## Decision 2: Field position in admin forms

**Decision**: Append `"metadata"` at the end of the existing `fields` tuple for both
`CategoryModelAdmin` and `ItemModelAdmin`.

**Rationale**: FR-006 specifies end placement. Appending is the least disruptive change and
matches the pattern used for other recently-added fields (e.g., `"slug"` was added to the end
when feature 018 landed).

## Decision 3: No custom JSON widget

**Decision**: Use Django's built-in `JSONField` widget (renders as a `<textarea>`).

**Rationale**: Django 3.1+ ships a native JSON form widget that handles serialization,
deserialization, and validation of `JSONField`. It meets all requirements (FR-005: invalid
JSON is rejected; FR-003/FR-004: view and edit). A custom widget would add complexity with no
functional benefit for this scope.

## Confirmed existing state

| Item | Status |
|------|--------|
| `CategoryModel.metadata` field in DB | ✅ exists (`JSONField(blank=True, default=dict)`, migration `0001_initial.py`) |
| `ItemModel.metadata` field in DB | ✅ exists (`JSONField(blank=True, default=dict)`, migration `0001_initial.py`) |
| `service.create_category` accepts `metadata` | ✅ already present |
| `service.create_item` accepts `metadata` | ✅ already present |
| `service.update_category` accepts `metadata` | ❌ missing — must add |
| `service.update_item` accepts `metadata` | ❌ missing — must add |
| `CategoryModelAdmin.save_model` passes `metadata` | ❌ missing — must add |
| `ItemModelAdmin.save_model` passes `metadata` | ❌ missing — must add |
