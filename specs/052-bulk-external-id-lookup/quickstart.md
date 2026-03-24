# Quickstart: Bulk Lookup by External ID (052)

## Who is this for?

Library consumers that resolve many items or categories by external ID in a single
operation — for example, rebuilding a page by looking up a list of author IDs or
genre categories stored in a third-party system.

---

## The Problem: N+1

```python
# ❌ Before — N+1 pattern (items)
items = {}
for ext_id in author_ids:
    item = service.get_item_by_external_id(ext_id)
    if item:
        items[ext_id] = item

# ❌ Before — N+1 pattern (categories)
cats = {}
for ext_id in genre_ids:
    cat = service.get_category_by_external_id(ext_id)
    if cat:
        cats[ext_id] = cat
```

Each call issues a separate query. For 100 IDs, that is 100 queries.

---

## The Fix: Single Bulk Call

```python
# ✅ After — one query total (items)
items = service.get_items_by_external_ids(author_ids)
# items: dict[str, Item]  keyed by external_id

# ✅ After — one query total (categories)
cats = service.get_categories_by_external_ids(genre_ids)
# cats: dict[str, Category]  keyed by external_id
```

---

## Enabled Filtering

Both methods accept an optional `enabled` keyword argument:

```python
# Only enabled items/categories (e.g. published authors)
items = service.get_items_by_external_ids(author_ids, enabled=True)
cats  = service.get_categories_by_external_ids(genre_ids, enabled=True)

# Only disabled
items = service.get_items_by_external_ids(author_ids, enabled=False)

# All regardless of enabled state (default)
items = service.get_items_by_external_ids(author_ids)          # enabled=None
items = service.get_items_by_external_ids(author_ids, enabled=None)
```

---

## Missing, Blank, and Duplicate IDs

Both methods handle messy input gracefully — no exceptions raised:

```python
ids = ["author-1", "author-1", " author-2 ", "", "  ", "no-such-id"]

items = service.get_items_by_external_ids(ids)
# - Duplicates removed
# - Blank/whitespace IDs ignored
# - Values stripped ("  author-2 " → "author-2")
# - "no-such-id" simply absent from result
# → {"author-1": Item(...), "author-2": Item(...)}  if both exist
```

---

## Root Category Exclusion

`get_categories_by_external_ids` always excludes the root category, even if its
external_id is in the input — consistent with `get_category_by_external_id`:

```python
cats = service.get_categories_by_external_ids([root_ext_id, "genre-1"])
# root_ext_id → absent from result
# → {"genre-1": Category(...)}  if it exists
```

---

## Disabled Items in Results

The default is `enabled=None` — disabled items/categories **are included** unless
you explicitly filter:

```python
# Item X is disabled, external_id = "x"

result = service.get_items_by_external_ids(["x"])
# → {"x": Item(enabled=False, ...)}  ← included by default

result = service.get_items_by_external_ids(["x"], enabled=True)
# → {}  ← excluded when enabled=True
```
