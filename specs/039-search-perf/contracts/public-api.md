# Public API Contract: 039-search-perf

**Type**: Python library public interface
**Status**: Unchanged — no breaking changes

---

## Preserved Signatures

The following public method signatures are **unchanged** by this feature. No new required parameters. No removed parameters. No changed return types.

### TaxomeshService.search_items

```python
def search_items(
    self,
    query: str,
    *,
    limit: int = DEFAULT_SEARCH_LIMIT,        # default 20
    category_id: UUID | None = None,
    enabled_only: bool = True,
    fuzzy: bool = True,
    recursive: bool = False,
) -> list[Item]: ...
```

**Behavior contract** (unchanged):
- Returns items ranked by descending score, ties broken by normalized name ascending.
- `limit <= 0` raises `ValueError`.
- Empty/whitespace `query` returns `[]`.
- `category_id` that does not exist raises `TaxomeshCategoryNotFoundError`.

---

### TaxomeshService.search_categories

```python
def search_categories(
    self,
    query: str,
    *,
    limit: int = DEFAULT_SEARCH_LIMIT,        # default 20
    parent_id: UUID | None = None,
    enabled_only: bool = True,
    fuzzy: bool = True,
) -> list[Category]: ...
```

**Behavior contract** (unchanged):
- Returns categories ranked by descending score, ties broken by normalized name ascending.
- The internal root category is always excluded.
- `limit <= 0` raises `ValueError`.
- Empty/whitespace `query` returns `[]`.
- `parent_id` that does not exist raises `TaxomeshCategoryNotFoundError`.

---

### SearchEngine.score_candidate (public method — unchanged)

```python
@staticmethod
def score_candidate(
    query: str,
    name: str,
    slug: str,
    external_id: str,
    *,
    fuzzy: bool = True,
) -> float | None: ...
```

**Behavior contract** (unchanged):
- Accepts raw (un-normalized) `name`, `slug`, `external_id` — normalizes internally.
- Returns a score ≥ 0 if the candidate matches, or `None` if it should be excluded.
- Scores are comparable only within a single query; absolute values are implementation details.

---

### SearchEngine.normalize (public static method — unchanged)

```python
@staticmethod
def normalize(text: str) -> str: ...
```

**Behavior contract** (unchanged):
- Deterministic: same input always produces same output.
- Strips diacritics, lowercases, collapses whitespace, replaces separator characters with spaces.

---

## Internal Changes (not part of public contract)

The following changes are internal and invisible to callers:

- `SearchCandidate` private class added to `search.py`
- `SearchEngine._score_prenorm` private method added
- `TaxomeshService._score_and_rank` refactored internally
- `heapq.nlargest` used instead of `list.sort()` when `limit < len(scored)`

None of these affect the public API surface.
