# Implementation Plan: Autocomplete FK Widget for External Admin

**Branch**: `027-autocomplete-fk-widget` | **Date**: 2026-03-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/027-autocomplete-fk-widget/spec.md`

## Summary

Provide external Django app admins with a compact, filterable autocomplete selector (Select2)
and a "↗" navigation link for FK fields pointing to taxomesh's `ItemModel` or `CategoryModel`.
Two components are exposed: `TaxomeshLinkedFKWidget` (a widget subclassing Django's built-in
`AutocompleteSelect`) and `TaxomeshLinkedFKMixin` (a `ModelAdmin` mixin that auto-applies the
widget to all taxomesh FK fields on the external model via `formfield_for_foreignkey`).

Both `ItemModelAdmin` and `CategoryModelAdmin` already have `search_fields` defined, so no
changes to those admins are required. The feature is purely additive and lives entirely in
the adapter layer (`taxomesh/contrib/django/`).

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Django 6.0.2, `django.contrib.admin.widgets.AutocompleteSelect`
**Storage**: N/A — no new models, no migrations
**Testing**: pytest + Django test client
**Target Platform**: Django admin (any supported database backend)
**Project Type**: library (adapter layer addition)
**Performance Goals**: Autocomplete AJAX response within 1 second under normal load (already
guaranteed by Django's built-in autocomplete endpoint + existing `search_fields` indexes)
**Constraints**: Must not modify `ItemModelAdmin` or `CategoryModelAdmin`; no new settings
required; no JS files added (Django's existing `autocomplete.js` is sufficient)
**Scale/Scope**: 2 new classes, 1 new file, ~100 lines of production code

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Hexagonal architecture | ✅ PASS | Change is in `adapters/` (contrib/django). No domain or application layer touched. |
| II. Single public facade | ✅ PASS | `TaxomeshService` is not modified. |
| III. Repository as Protocol | ✅ PASS | No repository changes. |
| IV. Pydantic models + mypy strict | ✅ PASS | New classes must carry full type annotations. |
| V. Exception hierarchy | ✅ PASS | Error in link URL derivation is caught silently (consistent with `_resolve_linked_url` pattern); no new exception types needed. |
| VI. DAG integrity | ✅ PASS | No DAG logic involved. |
| VII. Spec-driven | ✅ PASS | This plan is the spec artifact. |
| VIII. Quality gates | ✅ PASS | ruff + mypy + pytest ≥ 80% cov must pass. |
| IX. Pluggable REST views | ✅ PASS | No REST view changes. |
| X. Named constants | ✅ PASS | URL derivation is fully dynamic (no magic literal URL names). |
| XI. OO by default | ✅ PASS | `TaxomeshLinkedFKWidget` (class) + `TaxomeshLinkedFKMixin` (class). |

**No violations. No Complexity Tracking table needed.**

## Project Structure

### Documentation (this feature)

```text
specs/027-autocomplete-fk-widget/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── contracts/
│   └── external-admin-usage.md   # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
taxomesh/contrib/django/
├── widgets.py            # NEW — TaxomeshLinkedFKWidget
└── admin.py              # MODIFIED — TaxomeshLinkedFKMixin added

tests/contrib/django/
└── test_admin_linked_fk.py   # NEW — unit tests for widget and mixin
```

**Structure Decision**: Single-project layout. No new packages. The widget gets its own
module (`widgets.py`) following the SRP and mirroring Django's own `django.contrib.admin.widgets`.
The mixin stays in `admin.py` alongside the existing `TaxomeshAdminMixin` and
`ItemCategoryAssignmentMixin`.

## Implementation Design

### `TaxomeshLinkedFKWidget` — `taxomesh/contrib/django/widgets.py`

```
TaxomeshLinkedFKWidget(AutocompleteSelect)
  __init__(field, admin_site, attrs=None, choices=(), using=None)
      → calls super().__init__; no additional state needed

  render(name, value, attrs=None) → str
      1. output = super().render(name, value, attrs)
      2. if value is falsy → return output (no link)
      3. target_model = self.field.remote_field.model
      4. url = reverse(f"admin:{target_model._meta.app_label}_{target_model._meta.model_name}_change",
                       args=[value])
         (wrapped in try/except NoReverseMatch → return output without link)
      5. link = format_html('<a href="{}" title="Ver en admin" style="margin-left:4px">↗</a>', url)
      6. return mark_safe(output + link)
```

**Type annotations** (mypy strict):
```python
def render(
    self,
    name: str,
    value: object,
    attrs: dict[str, Any] | None = None,
) -> str:
```

### `TaxomeshLinkedFKMixin` — `taxomesh/contrib/django/admin.py`

```
TaxomeshLinkedFKMixin
  formfield_for_foreignkey(db_field, request, **kwargs) → FormField
      1. if db_field.related_model in (ItemModel, CategoryModel):
             kwargs["widget"] = TaxomeshLinkedFKWidget(
                 field=db_field,
                 admin_site=self.admin_site,
                 using=kwargs.pop("using", None),
             )
      2. return super().formfield_for_foreignkey(db_field, request, **kwargs)
```

**Type annotations** (mypy strict):
```python
def formfield_for_foreignkey(
    self,
    db_field: Any,
    request: HttpRequest,
    **kwargs: Any,
) -> Any:
```

### Test strategy — `tests/contrib/django/test_admin_linked_fk.py`

| Test | What it verifies |
|---|---|
| `test_widget_render_no_value` | `render()` with `value=None` returns no link |
| `test_widget_render_with_value` | `render()` with a valid pk returns HTML containing "↗" link to correct change URL |
| `test_widget_render_invalid_url` | `render()` with value that has no admin URL returns output without link (no exception) |
| `test_mixin_item_fk_uses_widget` | `formfield_for_foreignkey` returns a field with `TaxomeshLinkedFKWidget` for an Item FK |
| `test_mixin_category_fk_uses_widget` | Same for Category FK |
| `test_mixin_unrelated_fk_unchanged` | FK to an unrelated model passes through the default widget unchanged |
| `test_mixin_no_taxomesh_fks` | No error when the model has no taxomesh FK fields |

## Phase 0 Research Output

See [research.md](research.md). All NEEDS CLARIFICATION items resolved. No blockers.

## Phase 1 Design Output

See [data-model.md](data-model.md) and [contracts/external-admin-usage.md](contracts/external-admin-usage.md).
