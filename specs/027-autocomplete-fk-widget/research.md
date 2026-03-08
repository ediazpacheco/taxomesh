# Research: Autocomplete FK Widget for External Admin

## Decision 1 — Widget base class

**Decision**: Subclass `django.contrib.admin.widgets.AutocompleteSelect` (which itself is
`AutocompleteMixin + forms.Select`).

**Rationale**: `AutocompleteSelect` is Django's built-in Select2-powered autocomplete widget.
It handles the AJAX endpoint wiring, the `data-*` attributes, and the JS media declarations
automatically. Subclassing it means we inherit all of that for free and only need to override
`render()` to append the "↗" link.

**Alternatives considered**:
- `autocomplete_fields` class attribute on the external ModelAdmin — does not provide the
  link; requires the external developer to set it manually; no mixin can set it generically
  without knowing the field names.
- `raw_id_fields` — compact but no autocomplete; shows a popup instead of inline search; poor UX.
- Custom full widget from scratch — unnecessary complexity when `AutocompleteSelect` already
  handles everything we need.

---

## Decision 2 — Widget init signature

**Decision**: `TaxomeshLinkedFKWidget.__init__(self, field, admin_site, attrs=None, choices=(), using=None)`
— identical to `AutocompleteSelect.__init__`, with `field` being the **DB ForeignKey field**
(not the form field).

**Rationale**: Confirmed by inspecting the installed Django 6.0.2 source.
`AutocompleteMixin.__init__` stores `self.field = field` where `field` is the DB FK field.
`build_attrs()` reads `self.field.model` (the model that owns the FK) and
`self.field.remote_field.model` (the target model). This is what we use to derive the change
URL generically.

**Alternatives considered**: None — this is imposed by Django's widget contract.

---

## Decision 3 — Link URL derivation

**Decision**: Inside `render()`, derive the change URL from the widget's own `self.field`
attribute:

```
target_model = self.field.remote_field.model
url = reverse(f"admin:{target_model._meta.app_label}_{target_model._meta.model_name}_change",
              args=[value])
```

**Rationale**: Fully generic — works for any related model without hardcoding. The widget
doesn't need to know whether the target is `ItemModel` or `CategoryModel`; it introspects at
render time. This keeps the widget reusable for any FK field pointing to any admin-registered
model, but the mixin restricts usage to taxomesh models.

**Alternatives considered**:
- Pass `target_model` explicitly to `__init__` — unnecessary; `self.field.remote_field.model`
  already has it.
- Hardcode `"taxomesh_contrib_django_itemmodel"` URL name — violates DRY, would break if the
  app label changes.

---

## Decision 4 — Link rendering strategy (server-side vs dynamic JS)

**Decision**: Render the link server-side only. The link shows the change URL for the
currently saved FK value. After the user picks a new value and saves, the link updates.
No additional JavaScript is required.

**Rationale**: The spec requires a link to navigate to the detail page. Server-side rendering
covers the primary use case (viewing/editing an existing record). The user saves, then clicks
the link. Adding JS to dynamically update the link on selection change is scope creep beyond
what was specified.

**Alternatives considered**:
- JS-powered dynamic link — more interactive but requires custom JavaScript, additional
  Media declarations, and more complexity. Not in scope per spec.

---

## Decision 5 — Where the code lives

**Decision**:
- New file `taxomesh/contrib/django/widgets.py` — `TaxomeshLinkedFKWidget`
- Existing file `taxomesh/contrib/django/admin.py` — `TaxomeshLinkedFKMixin`

**Rationale**: Separating the widget into its own module follows the Single Responsibility
Principle and mirrors Django's own `django.contrib.admin.widgets` module. The mixin stays
in `admin.py` to be co-located with other admin mixins (`TaxomeshAdminMixin`,
`ItemCategoryAssignmentMixin`) and keeps the existing import surface intact.

**Alternatives considered**:
- Put everything in `admin.py` — makes the file even larger (already 1188 lines); widget
  is a distinct concern that deserves its own module.
- New `mixins.py` for the mixin — possible but creates an extra module for a single class;
  the existing mixin pattern in `admin.py` is the established convention.

---

## Decision 6 — Mixin hook

**Decision**: Override `formfield_for_foreignkey(self, db_field, request, **kwargs)` in
`TaxomeshLinkedFKMixin`. When `db_field.related_model` is `ItemModel` or `CategoryModel`,
inject `TaxomeshLinkedFKWidget` as the widget before calling `super()`.

**Rationale**: `formfield_for_foreignkey` is the canonical Django hook for customising FK
widgets in admin. It is called once per FK field when the form is constructed. The check
against `related_model` is precise and does not rely on field names, making the mixin
fully agnostic of the external app's field naming.

**Alternatives considered**:
- Override `get_form()` — too coarse-grained; harder to isolate per-field widget changes.
- Declare `autocomplete_fields` on the mixin — requires knowing the field name at class
  definition time; impossible without prior knowledge of the external model.

---

## Decision 7 — search_fields status on target admins

**Finding**: Both admins already have `search_fields` defined:
- `ItemModelAdmin.search_fields = ("name", "external_id", "slug", "item_id")`
- `CategoryModelAdmin.search_fields = ("name", "slug", "category_id")`

**Implication**: No changes needed to either `ItemModelAdmin` or `CategoryModelAdmin`.
The autocomplete AJAX endpoint is automatically registered by Django when `search_fields`
is set and `django.contrib.admin` is in `INSTALLED_APPS`.

---

## Decision 8 — Named constants (Constitution Principle X)

**Decision**: Define `Final` constants for:
- `TAXOMESH_ITEM_ADMIN_CHANGE_URL_NAME: Final[str] = "taxomesh_contrib_django_itemmodel_change"`
  — *not needed* because the URL is derived generically from `_meta` (see Decision 3).
- No additional constants needed beyond what already exists.

**Rationale**: The URL derivation is purely dynamic (`app_label + model_name`), so no
literal URL name constants are required. Any other literals (e.g. the link icon `"↗"`) are
single-use display strings that don't meet the "domain-meaningful / configuration-meaningful"
bar for Named Constants.

---

## Dependency Findings

- Django 6.0.2 is installed (via `.venv`)
- `AutocompleteSelect.__init__(self, field, admin_site, attrs=None, choices=(), using=None)` —
  confirmed by inspection
- No `widgets.py` exists yet in `taxomesh/contrib/django/`
- `taxomesh/contrib/django/__init__.py` currently exports `get_taxomesh_service_with_django()`
  — no changes needed there for this feature
