# Feature Specification: Autocomplete FK Widget for External Admin

**Feature Branch**: `027-autocomplete-fk-widget`
**Created**: 2026-03-08
**Status**: Draft
**Input**: User description: "Provide a compact, filterable autocomplete widget with a navigation link for ForeignKey fields pointing to taxomesh's ItemModel and CategoryModel in external app admins."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Compact filterable selector for Item FK field (Priority: P1)

An external app developer has a Django model (e.g. `Content`) with a ForeignKey to taxomesh's
`ItemModel`. In the Django admin change page, the current widget renders a full dropdown listing
every item with verbose labels — it is slow to scroll and impossible to filter. The developer
wants to replace it with a compact, searchable selector that also shows a direct link to the
selected item's taxomesh admin change page.

**Why this priority**: This is the primary pain point described by the user and the core value
of the feature. Everything else is secondary.

**Independent Test**: Can be fully tested by opening a `Content` change page in the Django admin
and verifying the Item FK field renders as a compact Select2 autocomplete with a working "↗" link.

**Acceptance Scenarios**:

1. **Given** an external app admin with a FK field pointing to `ItemModel`, **When** the developer
   configures the taxomesh-provided widget or mixin on that field, **Then** the field renders as a
   compact autocomplete selector (not a full dropdown list).
2. **Given** the compact selector is rendered, **When** the admin user types part of an item name,
   slug, or external_id, **Then** matching items appear as filtered suggestions.
3. **Given** an item is selected in the field, **When** the page is displayed, **Then** a "↗" link
   appears next to the field that navigates to the selected item's taxomesh admin change page.
4. **Given** no item is selected, **When** the page is displayed, **Then** no "↗" link is shown.

---

### User Story 2 — Compact filterable selector for Category FK field (Priority: P2)

The same external app has a ForeignKey to taxomesh's `CategoryModel`. The developer wants the
same compact + filterable + linked behaviour for the Category FK field.

**Why this priority**: Same UX problem as US1 but for Category. Both models are needed but the
Item case is more common.

**Independent Test**: Can be fully tested by opening a `Content` change page and verifying the
Category FK field renders as a compact Select2 autocomplete with a working "↗" link to the
category's taxomesh admin change page.

**Acceptance Scenarios**:

1. **Given** an external app admin with a FK field pointing to `CategoryModel`, **When** the
   developer applies the taxomesh-provided widget or mixin, **Then** the Category field renders
   as a compact autocomplete selector.
2. **Given** the compact selector is rendered, **When** the admin user types part of a category
   name or slug, **Then** matching categories appear as filtered suggestions.
3. **Given** a category is selected, **When** the page is displayed, **Then** a "↗" link appears
   that navigates to the selected category's taxomesh admin change page.

---

### User Story 3 — Drop-in mixin for external ModelAdmin (Priority: P3)

The developer wants a single mixin class from taxomesh that they can add to their `ModelAdmin`
to automatically apply compact+linked behaviour to all FK fields pointing to `ItemModel` and/or
`CategoryModel`, without manually configuring each field.

**Why this priority**: Developer experience improvement on top of P1/P2. Lower priority because
the widget/field approach in P1/P2 already delivers the value.

**Independent Test**: Can be fully tested by verifying that adding the mixin to a `ModelAdmin`
class (without any per-field configuration) results in autocomplete + link behaviour for all
taxomesh FK fields present on the model.

**Acceptance Scenarios**:

1. **Given** a `ModelAdmin` inherits the taxomesh mixin, **When** the change page is rendered,
   **Then** all ForeignKey fields pointing to `ItemModel` are rendered as compact autocomplete
   with "↗" links.
2. **Given** a `ModelAdmin` inherits the taxomesh mixin, **When** the change page is rendered,
   **Then** all ForeignKey fields pointing to `CategoryModel` are rendered as compact autocomplete
   with "↗" links.
3. **Given** a `ModelAdmin` inherits the mixin but has no FK fields to taxomesh models,
   **When** the change page is rendered, **Then** no error is raised and all other fields render
   normally.

---

### Edge Cases

- What happens when the selected Item or Category has been deleted from taxomesh — does the "↗"
  link still render, and does it produce a 404 or is it simply hidden?
- What happens when the autocomplete AJAX request returns zero results for a given search term?
- What happens when the external app's `ModelAdmin` also explicitly sets `autocomplete_fields`
  or `raw_id_fields` for the same FK field — does the taxomesh configuration coexist or override?
- What happens when `django.contrib.admin` is not in `INSTALLED_APPS`?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The library MUST expose a widget (or form field) that renders a FK field pointing
  to `ItemModel` as a compact, filterable autocomplete selector.
- **FR-002**: The library MUST expose a widget (or form field) that renders a FK field pointing
  to `CategoryModel` as a compact, filterable autocomplete selector.
- **FR-003**: When an `ItemModel` instance is selected, the widget MUST display a "↗" navigation
  link that points to the taxomesh Django admin change page for that item.
- **FR-004**: When a `CategoryModel` instance is selected, the widget MUST display a "↗"
  navigation link that points to the taxomesh Django admin change page for that category.
- **FR-005**: When no instance is selected, no navigation link MUST be rendered.
- **FR-006**: The library MUST expose a `ModelAdmin` mixin that automatically applies the compact
  autocomplete + link behaviour to all FK fields pointing to `ItemModel` or `CategoryModel`
  found on the external model — without requiring per-field manual configuration.
- **FR-007**: The library MUST NOT require knowledge of the external app's model names, app
  labels, or field names — it must remain fully agnostic of the consuming application.
- **FR-008**: Search/filter in the autocomplete MUST work against at minimum: name and slug for
  both models; additionally external_id and item_id for `ItemModel`.
- **FR-009**: The feature MUST be usable independently of the `TAXOMESH_LINKED_MODEL` and
  `TAXOMESH_CATEGORY_LINKED_MODEL` settings (those go in the opposite direction).
- **FR-010**: The navigation link MUST open in the same browser tab (standard Django admin
  behaviour).

### Key Entities

- **ItemModel**: taxomesh Django ORM model for taxonomy items; already has `search_fields`
  defined in its `ModelAdmin`, enabling autocomplete support.
- **CategoryModel**: taxomesh Django ORM model for taxonomy categories; already has
  `search_fields` defined in its `ModelAdmin`, enabling autocomplete support.
- **External Model**: any Django model in a consuming app that holds a ForeignKey to `ItemModel`
  and/or `CategoryModel`. The library must not import or reference it directly.
- **TaxomeshLinkedFKWidget** *(provisional name)*: the widget exposed by the library that
  combines autocomplete selection with a "↗" admin change link.
- **TaxomeshLinkedFKMixin** *(provisional name)*: the `ModelAdmin` mixin that auto-applies the
  widget to all taxomesh FK fields on the external model.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An external app developer can enable compact autocomplete + link for a taxomesh FK
  field in fewer than 5 lines of configuration change (mixin inheritance or per-field widget
  override).
- **SC-002**: The autocomplete suggestion list appears within 1 second of the user starting to
  type, under normal load conditions.
- **SC-003**: The "↗" link navigates to the correct taxomesh admin change page with 100%
  accuracy for any valid selected instance.
- **SC-004**: Zero errors are raised when the mixin is applied to a `ModelAdmin` whose model has
  no FK fields pointing to taxomesh models.
- **SC-005**: All existing taxomesh admin tests continue to pass after the feature is introduced —
  no regressions.
- **SC-006**: The feature is usable without any additional required settings keys beyond what
  Django admin already requires.
