# Contract: External Admin Usage

This document defines the public interface taxomesh exposes to external app developers
for the autocomplete FK widget feature.

---

## Option A — Drop-in Mixin (recommended)

```python
# myapp/admin.py
from django.contrib import admin
from taxomesh.contrib.django.admin import TaxomeshLinkedFKMixin

from .models import Content

@admin.register(Content)
class ContentAdmin(TaxomeshLinkedFKMixin, admin.ModelAdmin):
    # No per-field configuration needed.
    # All FK fields pointing to ItemModel or CategoryModel are automatically
    # rendered as compact autocomplete selectors with "↗" links.
    fields = ["title", "type", "item", "category", "relevance"]
```

**Requirements**:
- `django.contrib.admin` must be in `INSTALLED_APPS`.
- `taxomesh.contrib.django` must be in `INSTALLED_APPS`.
- The external model's FK field(s) must point to `ItemModel` and/or `CategoryModel`.

---

## Option B — Per-field Widget Override

```python
# myapp/admin.py
from django import forms
from django.contrib import admin
from taxomesh.contrib.django.widgets import TaxomeshLinkedFKWidget
from taxomesh.contrib.django.models import ItemModel

from .models import Content

class ContentForm(forms.ModelForm):
    class Meta:
        model = Content
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Replace widget for a specific FK field
        self.fields["item"].widget = TaxomeshLinkedFKWidget(
            field=Content._meta.get_field("item"),
            admin_site=admin.site,
        )

@admin.register(Content)
class ContentAdmin(admin.ModelAdmin):
    form = ContentForm
```

---

## Rendered behaviour

For any FK field using `TaxomeshLinkedFKWidget`:

- **Empty / new record**: compact Select2 search box only; no link rendered.
- **Existing record with a value**: compact Select2 search box + a "↗" link.
  Clicking the link opens the taxomesh admin change page for the selected
  Item or Category in the same tab.
- **After selecting a new value and saving**: link updates to point to the
  newly saved instance.

---

## Import paths

| Symbol | Import path |
|---|---|
| `TaxomeshLinkedFKMixin` | `taxomesh.contrib.django.admin` |
| `TaxomeshLinkedFKWidget` | `taxomesh.contrib.django.widgets` |
