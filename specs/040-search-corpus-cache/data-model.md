# Data Model: Search Corpus Cache (040)

**Branch**: `040-search-corpus-cache`
**Date**: 2026-03-16

---

## Overview

This feature introduces **no new domain entities** and **no repository schema changes**. All changes are confined to the service layer (`application/service.py`) and are entirely internal.

The two key internal structures are:

1. **`SearchCandidate[_T]`** — already exists in `search.py`; no changes required.
2. **Search corpus caches** — two new private instance attributes on `TaxomeshService`.

---

## Existing: `SearchCandidate[_T]` (`taxomesh/application/search.py`)

No changes. This class is the unit of the corpus cache. Documented here for clarity.

```
SearchCandidate[_T]
  obj: _T                  # Original domain object (Item | Category)
  norm_name: str           # Normalized name (accent-stripped, lowercased, collapsed)
  norm_slug: str           # Normalized slug
  norm_ext: str            # Normalized external_id ("" if not set)
```

**Immutability contract**: `SearchCandidate` instances are built once at corpus construction time and never mutated. The corpus list is replaced entirely on invalidation.

---

## New Internal State on `TaxomeshService`

Two private nullable attributes are added to the `TaxomeshService` instance:

```
TaxomeshService (additions only)
  _item_corpus: list[SearchCandidate[Item]] | None
    Default: None (unbuilt)
    Built by: _get_item_corpus()  (lazy, on first unfiltered item search)
    Invalidated by: all item write operations (create, update, delete)

  _category_corpus: list[SearchCandidate[Category]] | None
    Default: None (unbuilt)
    Built by: _get_category_corpus()  (lazy, on first unfiltered category search)
    Invalidated by: all category write operations (create, update, delete)
```

---

## Corpus Build Logic

### Item Corpus

```
Input:  self.list_items()   →  list[Item]   (memoized repository read)
Output: list[SearchCandidate[Item]]

For each item in list_items():
    SearchCandidate(
        obj      = item,
        norm_name = SearchEngine.normalize(item.name),
        norm_slug = SearchEngine.normalize(item.slug),
        norm_ext  = SearchEngine.normalize(item.external_id) if item.external_id else "",
    )
```

### Category Corpus

```
Input:  all categories except internal root   (loaded via service memoized path)
Output: list[SearchCandidate[Category]]

For each category in all_categories (root excluded):
    SearchCandidate(
        obj       = category,
        norm_name = SearchEngine.normalize(category.name),
        norm_slug = SearchEngine.normalize(category.slug),
        norm_ext  = SearchEngine.normalize(category.external_id) if category.external_id else "",
    )
```

---

## Corpus Invalidation Matrix

| Write Operation                    | Invalidates _item_corpus | Invalidates _category_corpus |
|------------------------------------|--------------------------|------------------------------|
| `create_item()`                    | ✅                        | —                            |
| `update_item()`                    | ✅                        | —                            |
| `delete_item()`                    | ✅                        | —                            |
| `create_category()`                | —                        | ✅                            |
| `update_category()`                | —                        | ✅                            |
| `delete_category()`                | —                        | ✅                            |
| `place_item_in_category()`         | —                        | —                            |
| `remove_item_from_category()`      | —                        | —                            |
| `reparent_item()`                  | —                        | —                            |
| `add_category_parent()`            | —                        | —                            |
| `remove_category_parent()`         | —                        | —                            |
| `reparent_category()`              | —                        | —                            |
| `create_tag()` / `update_tag()` / `delete_tag()` | —         | —                            |
| `assign_tag()` / `remove_tag()`    | —                        | —                            |
| `relate_items()` / `remove_item_relation()` | —             | —                            |
| `reorder_subcategories()`          | —                        | —                            |
| `reorder_items_in_category()`      | —                        | —                            |

**Rationale**: Corpus candidates are keyed on entity-level fields only (`name`, `slug`, `external_id`). Placement, linking, and ordering operations change structural relationships, not entity fields. The global corpus for unfiltered search remains valid after these operations.

---

## Call Flow After This Feature

### Unfiltered Item Search (hot path, warm corpus)

```
search_items(query, category_id=None)
  │
  ├─ norm_q = SearchEngine.normalize(query)
  │
  ├─ corpus = _get_item_corpus()          ← returns _item_corpus (pre-built, no I/O)
  │
  ├─ filter enabled_only from corpus
  │
  └─ _score_corpus(norm_q, corpus, fuzzy, limit)
       │
       └─ for each SearchCandidate[Item]:
            score = SearchEngine._score_prenorm(norm_q, cand.norm_name, cand.norm_slug, cand.norm_ext)
            (no normalize() call — fields already normalized)
```

### Filtered Item Search (category_id != None — unchanged)

```
search_items(query, category_id=X)
  │
  ├─ candidates = _load_item_candidates(category_id=X, recursive=...)  ← fresh load from service
  │
  └─ _score_and_rank(norm_q, candidates, ...)   ← builds SearchCandidate wrappers inline (unchanged)
```

### Unfiltered Category Search (hot path, warm corpus)

```
search_categories(query, parent_id=None)
  │
  ├─ norm_q = SearchEngine.normalize(query)
  │
  ├─ corpus = _get_category_corpus()      ← returns _category_corpus (pre-built, no I/O)
  │
  └─ _score_corpus(norm_q, corpus, fuzzy, limit)
```

---

## No Repository Changes

The `TaxomeshRepositoryBase` protocol is not modified. All three supported backends (JSON, YAML, Django) are unaffected at the repository layer.
