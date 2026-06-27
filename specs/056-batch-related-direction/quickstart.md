# Quickstart: Direction-Aware Batched Related-Items Traversal

## What changed

`TaxomeshService.list_related_items_for_sources` now accepts a `direction`
parameter so you can batch-resolve related items in either direction (or both)
without looping single-item calls.

## Usage

```python
from taxomesh import TaxomeshService

service = TaxomeshService()

ids = [item_a.item_id, item_b.item_id, item_c.item_id]

# Outgoing (default — unchanged behavior): "what do these items point to?"
out = service.list_related_items_for_sources(ids)

# Incoming (new): "what points at these items?" — two repository calls, no N+1
inc = service.list_related_items_for_sources(ids, direction="incoming")

# Both (new): union of outgoing + incoming, grouped the same way
both = service.list_related_items_for_sources(ids, direction="both")

# Filter by relation type (case-insensitive), in any direction
covers_in = service.list_related_items_for_sources(
    ids, relation_types=["COVERS"], direction="incoming"
)
```

## Result shape

```python
# { queried_item_id: { relation_type: [related Item, ...] } }
{
    item_a.item_id: {"covers": [item_x, item_y]},
    item_b.item_id: {"performed_by": [item_z]},
    # item_c absent — it had no matching links in this direction
}
```

## Before (the N+1 you no longer need)

```python
# Old incoming pattern: one query pair per item
result = {}
for item_id in ids:
    result[item_id] = service.list_related_items(item_id, direction="incoming")
```

## Verify

```bash
# Behavioral parity across backends + anti-N+1 query-count guards
pytest tests/service/test_service_item_relations.py \
       tests/service/test_service_no_full_scan.py \
       tests/service/test_service_cache.py \
       tests/service/test_service_list_related_resilience.py

# Full gates
ruff check . && ruff format --check . && mypy --strict . \
  && pytest --cov=taxomesh --cov-fail-under=80
```
