# Quickstart: Batch resolution for the placement read paths

**Feature**: `060-batch-placement-reads` | **Date**: 2026-09-09

## Environment

The venv must be built for Python 3.12 or 3.13 with the django extra, or the
Django-parametrised tests cannot run:

```bash
uv sync --extra dev --extra django --python 3.12
```

## Seeing the defect before fixing it

The gate is the deliverable, so start by watching the current code fail it:

```python
from django.test.utils import CaptureQueriesContext
from django.db import connection

with CaptureQueriesContext(connection) as ctx:
    svc.list_items(category_id=big_category_id)
print(len(ctx.captured_queries))   # today: 2 + one per placement
```

The same call with no filter costs a single query over a *larger* result set —
that contrast is the defect, and it is what the new tests pin down.

## What "done" looks like

```python
# 200 placements and 5 placements must cost the SAME number of queries
assert queries_for(placements=5) == queries_for(placements=200) == 3
```

Expected constants, all to be confirmed empirically rather than trusted from
this table (see research.md R3):

| Call | Queries |
| --- | --- |
| `list_items(category_id=X)` non-empty | 3 |
| `list_items(category_id=X)` empty | 2 |
| `list_categories(parent_id=P)` non-empty | 3 |
| `list_categories(parent_id=None)` non-empty | 2 |
| `list_categories_by_item(id)` non-empty | 3 |
| `list_categories_by_item(id)` empty | 2 |

Measure cold — clear the TTL cache first, or the second measurement reads from
memory and the gate proves nothing (FR-021):

```python
from taxomesh.utils.memoize import clear_all_caches
clear_all_caches()
```

## Running the suite

```bash
# the two new modules
pytest tests/service/test_batch_placement_reads.py \
       tests/contrib/django/test_django_placement_queries.py -q

# cross-backend parity — runs each test four times (in_memory, json, yaml, django)
pytest tests/service/ -q

# full gates, as CI runs them
ruff check . && ruff format --check . && mypy --strict . \
  && pytest --cov=taxomesh --cov-fail-under=80
```

**Ordering caveat**: the Django-parametrised service tests need
`tests/service/test_parity_fixture.py` collected in the same run, or they fail
with "no such table". Run `pytest tests/service/` rather than a single file when
the `service` fixture is involved.

## Three traps, from research.md

1. **Do not delete the `sorted(links, key=lambda lnk: lnk.sort_index)` call.**
   It looks redundant once links arrive ordered. It is not — for
   `list_categories_by_item` the stable re-sort over a category-ordered list is
   what produces today's `(sort_index, category_id)` output. Deleting it changes
   tie order. (R1)

2. **Do not push `enabled` into the batch resolve.** Call it with
   `enabled=None` and filter afterwards. A disabled row and a deleted row are
   both "absent from the map", and FR-012 raises on absent — so pushing the
   filter down makes every disabled endpoint raise. (R2)

3. **Do not assert "single-row retrieval called zero times" uniformly.** The
   existence check is a single-row retrieval and it stays (FR-013). For
   `list_categories(parent_id=…)` the correct figure is exactly one, because the
   check and the resolve concern the same entity type. (R4)

## Manual smoke check

```python
from taxomesh.application.service import TaxomeshService

svc = TaxomeshService()
cat = svc.create_category("Jazz", slug="jazz")
for n in range(5):
    item = svc.create_item(name=f"Album {n}")
    svc.place_item_in_category(item.item_id, cat.category_id, sort_index=n)

items = svc.list_items(category_id=cat.category_id)
assert [i.name for i in items] == [f"Album {n}" for n in range(5)]   # sort_index order
assert svc.list_categories_by_item(items[0].item_id)[0].name == "Jazz"
```

`sort_index=n` is deliberate: `place_item_in_category` defaults it to `0`, so
placing five items without it leaves five ties, and the order then falls out of
the `item_id` tie-break rather than insertion order. That is correct behaviour,
but it makes a poor smoke check.
