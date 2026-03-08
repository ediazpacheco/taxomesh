# Research: Unified __str__ + Django Admin Graph Links

**Feature**: 022-unified-str-admin-links
**Date**: 2026-03-08

## Decision Log

### Decision 1: Django admin change-page URL naming convention

**Decision**: Use the standard Django reverse name pattern `admin:<app_label>_<model_name>_change`.

**Rationale**: Django auto-generates URL names following this convention for every registered
`ModelAdmin`. For `taxomesh.contrib.django`, the app_label is `taxomesh_contrib_django`,
category PK field is `category_id` (UUID, `primary_key=True`), and item PK field is `item_id`
(UUID, `primary_key=True`). Therefore:
- Category change URL: `admin:taxomesh_contrib_django_categorymodel_change`
- Item change URL: `admin:taxomesh_contrib_django_itemmodel_change`

**Alternatives considered**: Hardcoding URL paths (`/admin/taxomesh_contrib_django/categorymodel/<uuid>/change/`).
Rejected because `{% url %}` tag is the Django-idiomatic approach and automatically respects
`FORCE_SCRIPT_NAME` / custom admin prefixes.

**Verification**: Confirmed from `taxomesh/contrib/django/models.py` that `CategoryModel` and
`ItemModel` use `primary_key=True` on their UUID fields (`category_id` and `item_id`).

---

No other NEEDS CLARIFICATION items were present. All design decisions were unambiguous.
