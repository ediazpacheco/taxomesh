# Data Model: Autocomplete FK Widget for External Admin

This feature introduces no new domain entities, no new database tables, and no
migration. It is a purely presentational adapter-layer addition.

## New Classes

### `TaxomeshLinkedFKWidget`

**Module**: `taxomesh/contrib/django/widgets.py`
**Inherits from**: `django.contrib.admin.widgets.AutocompleteSelect`

| Attribute / Method | Type | Description |
|---|---|---|
| `field` | DB ForeignKey field | Inherited from `AutocompleteMixin`. Used to derive target model metadata. |
| `admin_site` | `AdminSite` | Inherited. Used to build the autocomplete AJAX URL. |
| `render(name, value, attrs)` | `→ str` | Overrides parent to append a "↗" link when `value` is set. |

**Behaviour**:
- When `value` is falsy (no selection): renders identical to `AutocompleteSelect`.
- When `value` is set: renders `AutocompleteSelect` output + a `<a href="...">↗</a>` link
  pointing to the Django admin change page for the selected instance.
- The change URL is derived generically from `self.field.remote_field.model._meta`; no
  model names are hardcoded.

---

### `TaxomeshLinkedFKMixin`

**Module**: `taxomesh/contrib/django/admin.py`
**Inherits from**: nothing (pure mixin; combined with `admin.ModelAdmin` by consumer)

| Method | Signature | Description |
|---|---|---|
| `formfield_for_foreignkey` | `(db_field, request, **kwargs) → FormField` | Injects `TaxomeshLinkedFKWidget` for FK fields whose `related_model` is `ItemModel` or `CategoryModel`. |

**Behaviour**:
- For each FK field on the external model, checks `db_field.related_model`.
- If `ItemModel` or `CategoryModel`: replaces the default widget with
  `TaxomeshLinkedFKWidget(db_field, self.admin_site, using=kwargs.pop("using", None))`.
- All other FK fields pass through unchanged to `super().formfield_for_foreignkey()`.
- Safe to use when the external model has no taxomesh FK fields (no-op).

---

## Relationships (unchanged)

```
External model (consumer app)
    FK → ItemModel          ← TaxomeshLinkedFKWidget renders compact selector + link
    FK → CategoryModel      ← TaxomeshLinkedFKWidget renders compact selector + link

ItemModel
    admin registered via ItemModelAdmin (search_fields already set — no change)

CategoryModel
    admin registered via CategoryModelAdmin (search_fields already set — no change)
```

## Validation Rules

- `TaxomeshLinkedFKWidget.render()` MUST NOT raise when `value` is `None`, `""`, or `[]`.
- The "↗" link is only rendered when `value` is a non-empty, non-null scalar.
- The change URL is constructed via `django.urls.reverse`; if the URL cannot be resolved
  (e.g. the admin is not registered), the exception is caught and the link is silently
  omitted — consistent with the existing `_resolve_linked_url` pattern in `admin.py`.
