# Data Model: Fuzzy Search APIs (033-fuzzy-search)

## No New Persistent Entities

This feature is purely additive at the service layer. No new domain models, database tables, or
repository methods are introduced. No migrations are required.

---

## New Module: `taxomesh/application/search.py`

### Constants (module-level, `Final`)

| Constant | Type | Value | Purpose |
|----------|------|-------|---------|
| `BOOST_EXACT` | `Final[int]` | 1000 | Score added for exact normalized match on name or slug |
| `BOOST_PREFIX_NAME` | `Final[int]` | 500 | Score added when name starts with query |
| `BOOST_PREFIX_SLUG` | `Final[int]` | 400 | Score added when slug starts with query |
| `BOOST_WORD_PREFIX` | `Final[int]` | 300 | Score added when any word of name starts with query |
| `BOOST_SUBSTRING_NAME` | `Final[int]` | 200 | Score added when query is substring of name |
| `BOOST_SUBSTRING_SLUG` | `Final[int]` | 150 | Score added when query is substring of slug |
| `BOOST_SUBSTRING_EXT` | `Final[int]` | 50 | Score added when query is substring of external_id (only when non-empty) |
| `FUZZY_THRESHOLD` | `Final[int]` | 70 | Minimum RapidFuzz score for a purely-fuzzy candidate to be included |

### Class: `SearchEngine`

Stateless scoring engine. Can be instantiated with no arguments.

#### Public Methods

**`SearchEngine.normalize(text: str) -> str`** *(staticmethod)*

Normalize a string for comparison:
- NFD decompose → strip combining marks (accent removal)
- Convert punctuation (apostrophes, dashes, periods, underscores) to spaces
- Lowercase
- Collapse multiple whitespace into single space
- Strip leading/trailing whitespace

Examples:
- `"Agustín"` → `"agustin"`
- `"D'Arienzo"` → `"d arienzo"`
- `"gallo-ciego"` → `"gallo ciego"`
- `"  Piazola  "` → `"piazola"`

**`SearchEngine.score_candidate(query: str, name: str, slug: str, external_id: str) -> float | None`**

Compute a match score for one candidate against the normalized query.

- `query`: Already normalized query string.
- `name`, `slug`, `external_id`: Raw field values from the domain entity (normalized internally).
- Returns `None` if the candidate does not meet inclusion criteria (below threshold with no non-fuzzy signals).
- Returns a `float` score ≥ 0 if the candidate should be included in results.

Scoring logic:
1. Normalize name, slug, and external_id.
2. Compute boost signals (exact, prefix, word-prefix, substring) — sum into `boost`.
3. If `fuzzy=True` (passed via constructor or parameter — see below), compute RapidFuzz scores.
4. If `boost > 0`: include candidate (score = boost + fuzzy_additive).
5. If `boost == 0` and max RapidFuzz score ≥ `FUZZY_THRESHOLD`: include (score = fuzzy_additive).
6. Otherwise: return `None`.

> **Note**: The `fuzzy` flag will be threaded through via a parameter to `score_candidate` rather than constructor state, since `SearchEngine` is stateless.

---

## Modified File: `taxomesh/application/service.py`

### New Public Methods

**`TaxomeshService.search_items`**

```
search_items(
    self,
    query: str,
    *,
    limit: int = 20,
    category_id: UUID | None = None,
    enabled_only: bool = True,
    fuzzy: bool = True,
    recursive: bool = False,
) -> list[Item]
```

Candidate loading:
- `category_id=None`, `recursive=False` → `self._repo.list_items()`
- `category_id=X`, `recursive=False` → `self.list_items(category_id=X)` (validates existence)
- `category_id=X`, `recursive=True` → BFS over `list_category_parent_links()` to collect all descendant category IDs; union of `self.list_items(category_id=cid)` for each; deduplicate by `item_id`

**`TaxomeshService.search_categories`**

```
search_categories(
    self,
    query: str,
    *,
    limit: int = 20,
    parent_id: UUID | None = None,
    enabled_only: bool = True,
    fuzzy: bool = True,
) -> list[Category]
```

Candidate loading:
- `parent_id=None` → `self._repo.list_categories()`, filter out root (`category_id == self._root_id`)
- `parent_id=X` → `self.list_categories(parent_id=X)` (validates existence)

### New Private Helper (on `TaxomeshService`)

**`TaxomeshService._collect_descendant_ids(category_id: UUID) -> set[UUID]`**

BFS over `self._repo.list_category_parent_links()` to return the set of all descendant category IDs
(not including the starting `category_id` itself). Used only when `recursive=True`.

---

## Modified File: `pyproject.toml`

Add to `[project] dependencies`:
```
"rapidfuzz>=3.0",
```

---

## New Test File: `tests/service/test_service_search.py`

Uses the existing `InMemoryRepository` fixture from `tests/service/conftest.py`.
No new fixture infrastructure needed.

Test coverage targets (from spec SC-005):
- 14 item-search cases
- 8 category-search cases
- 3 ranking-behavior cases

Total: ≥ 25 test functions.
