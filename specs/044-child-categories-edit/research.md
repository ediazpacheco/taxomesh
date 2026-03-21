# Research: Admin Child Categories Editable Inline (044)

## Decision 1: Editable Inline Architecture

**Decision**: Convert `CategoryChildLinkInline` from `_ReadOnlyInlineMixin + TabularInline` to a
fully editable `TaxomeshAdminMixin + TabularInline`, mirroring `CategoryParentLinkInline`.

**Rationale**: `CategoryParentLinkInline` already solves the identical problem from the opposite
direction. It uses `fk_name = "category"` to filter by the child being edited; the child inline
uses `fk_name = "parent_category"` to filter by the parent being edited. Both operate on the same
`CategoryParentLinkModel` table. Reusing the same pattern (form + save_model/delete_model hooks
delegating to `TaxomeshService`) avoids any new infrastructure and keeps both inlines symmetric.

**Alternatives considered**:
- **Separate view/endpoint**: Unnecessary complexity — Django's inline system already handles the
  reverse FK relation cleanly.
- **Override `get_queryset` on the existing read-only inline**: Would still require adding
  permissions and save hooks — essentially replacing the whole class, so a clean new class is
  cleaner.

---

## Decision 2: Form Validation Strategy for Cycle and Duplicate Detection

**Decision**: Introduce `CategoryChildLinkForm(forms.ModelForm)` that calls the service's
`add_category_parent` in a try/except inside `clean()`, catches `TaxomeshCyclicDependencyError`
and `TaxomeshExternalIdConflictError` / `unique_together` DB error, and converts them to
`forms.ValidationError` on the appropriate field.

**Rationale**: `CategoryParentLinkForm` already does this for the parent inline. The child form
applies identical logic — only the field being validated changes (`category` instead of
`parent_category`). No new domain logic is needed; all validation lives in the service/domain layer.

**Alternatives considered**:
- **Inline `validate_unique` override**: Django calls this after `clean()` anyway; hooking into
  `clean()` allows early cycle detection before the DB uniqueness check fires.

---

## Decision 3: Autocomplete Field for Child Selector

**Decision**: `autocomplete_fields = ["category"]` (the child FK field).

**Rationale**: The parent inline uses `autocomplete_fields = ["parent_category"]`. The reverse
applies here — the field exposed for user selection is the child category. `CategoryModelAdmin`
already has `search_fields` configured, so `AutocompleteSelect` works without additional changes.

---

## Decision 4: ROOT Category Exclusion

**Decision**: Exclude the root/sentinel category from the child selector via
`formfield_for_foreignkey()`, matching the exclusion already in `CategoryParentLinkInline`.

**Rationale**: The root sentinel category (`ROOT_CATEGORY_NAME`) is an internal implementation
detail; it must not appear in user-facing selectors in either direction.

---

## Decision 5: No Migration Required

**Decision**: Zero new migrations.

**Rationale**: `CategoryParentLinkModel` already exists with all required fields (`category`,
`parent_category`, `sort_index`). The child inline re-uses the reverse FK relation
(`related_name="child_links"`) already defined on the model. No schema change is needed.

---

## Key Implementation Facts (from codebase)

| Item | Value |
|------|-------|
| Admin file | `taxomesh/contrib/django/admin.py` |
| Model | `CategoryParentLinkModel` |
| FK to child | `category` (ForeignKey → CategoryModel, related_name="parent_links") |
| FK to parent | `parent_category` (ForeignKey → CategoryModel, related_name="child_links") |
| Child inline fk_name | `"parent_category"` (filter records where parent == current category) |
| Parent inline class | `CategoryParentLinkInline` |
| Parent inline form | `CategoryParentLinkForm` |
| Current child inline | `CategoryChildLinkInline(_ReadOnlyInlineMixin, admin.TabularInline)` |
| Service add method | `svc.add_category_parent(category_id, parent_category_id)` |
| Service remove method | `svc.remove_category_parent(category_id, parent_category_id)` |
| Cycle error | `TaxomeshCyclicDependencyError` |
| Test file | `tests/contrib/django/test_admin.py` (class `TestCategoryChildLinkInline`) |
