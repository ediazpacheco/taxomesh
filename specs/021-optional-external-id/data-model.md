# Data Model: 021-optional-external-id

## Overview

Three files change. No new entities are introduced. No API surface changes
(existing callers that pass `external_id` are unaffected).

---

## 1. `taxomesh/domain/constants.py` — new constant

```python
# Default value for Item.external_id — empty string means "no external reference".
DEFAULT_ITEM_EXTERNAL_ID: Final[str] = ""
```

Added alongside the existing `DEFAULT_CATEGORY_EXTERNAL_ID`. Import path for
callers: `from taxomesh.domain.constants import DEFAULT_ITEM_EXTERNAL_ID`.

---

## 2. `taxomesh/domain/models/item.py` — field default added

**Before**:
```python
external_id: Annotated[str, Field(max_length=MAX_EXTERNAL_ID_STR_LENGTH)]
```

**After**:
```python
external_id: Annotated[str, Field(max_length=MAX_EXTERNAL_ID_STR_LENGTH)] = DEFAULT_ITEM_EXTERNAL_ID
```

The `_coerce_external_id` validator is unchanged — it continues to coerce any
non-string value (including `None`) to a string before validation.

---

## 3. `taxomesh/application/service.py` — `create_item` signature

**Before**:
```python
def create_item(
    self,
    name: str,
    external_id: ExternalId,
    metadata: dict[str, Any] | None = None,
    slug: str = "",
) -> Item:
```

**After**:
```python
def create_item(
    self,
    name: str,
    external_id: ExternalId = DEFAULT_ITEM_EXTERNAL_ID,
    metadata: dict[str, Any] | None = None,
    slug: str = "",
) -> Item:
```

`DEFAULT_ITEM_EXTERNAL_ID` is imported from `taxomesh.domain.constants`.
All other method logic is unchanged.

---

## 4. `taxomesh/contrib/django/models.py` — ORM field

**Before**:
```python
external_id = models.CharField(max_length=MAX_EXTERNAL_ID_STR_LENGTH)
```

**After**:
```python
external_id = models.CharField(max_length=MAX_EXTERNAL_ID_STR_LENGTH, blank=True, default="")
```

`blank=True` — Django form validation accepts an empty string.
`default=""` — new rows saved without supplying `external_id` receive an empty string.
The column type (`VARCHAR(256) NOT NULL`) is unchanged.

---

## 5. Migration — `taxomesh/contrib/django/migrations/0002_alter_itemmodel_external_id.py`

An `AlterField` migration that reflects the `blank=True, default=""` change on
`ItemModel.external_id`. No data migration is needed — existing rows retain
their current values.

```python
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("taxomesh_django", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="itemmodel",
            name="external_id",
            field=models.CharField(blank=True, default="", max_length=256),
        ),
    ]
```

---

## 6. `taxomesh/adapters/cli/main.py` — `item add` command

**Before**:
```python
external_id: str = typer.Option(..., "--external-id", help="External identifier (UUID, int, or string)"),
```

**After**:
```python
external_id: str = typer.Option("", "--external-id", help="External identifier (UUID, int, or string); optional"),
```

`typer.Option(...)` (Ellipsis) makes the flag required. Changing to `""` as the default makes
it optional while keeping the same CLI flag name. The body of `item_add` already passes
`external_id` through `_parse_external_id`, which coerces any string — including `""`.

---

## Unchanged surfaces

| Surface | Why unchanged |
|---------|---------------|
| `TaxomeshRepositoryBase` protocol | `save_item` / `list_items_by_external_id` signatures unchanged |
| `JsonRepository` / `YAMLRepository` | Serialise `item.external_id` as-is; empty string round-trips correctly |
| `DjangoRepository` | Reads/writes `external_id` column directly; empty string is a valid value |
| Public `__init__.py` exports | No new symbols exported |
