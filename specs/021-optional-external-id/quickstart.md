# Quickstart: 021-optional-external-id

## Before the fix

```python
from taxomesh import TaxomeshService

svc = TaxomeshService()

# This raised a Pydantic ValidationError — external_id was required.
item = svc.create_item(name="My article")
```

## After the fix

```python
from taxomesh import TaxomeshService

svc = TaxomeshService()

# Create an item with no external reference yet.
item = svc.create_item(name="My article")
assert item.external_id == ""

# Later, once the external entity exists, update it.
updated = svc.update_item(item.item_id, external_id="content-42")
assert updated.external_id == "content-42"

# Creating with an explicit external_id still works exactly as before.
item_with_id = svc.create_item(name="Another article", external_id="content-99")
assert item_with_id.external_id == "content-99"
```

## Django admin

After the migration runs, the **External id** field in the Django admin Item
create/edit form is no longer required. Leaving it blank saves the item with
`external_id = ""`. The field can be filled in later at any point.

## CLI

```bash
# Create an item without an external ID
taxomesh item add --name "My article"

# Create an item with an external ID (behaviour unchanged)
taxomesh item add --name "My article" --external-id "content-42"
```
