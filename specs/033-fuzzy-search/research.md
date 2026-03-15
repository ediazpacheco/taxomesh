# Research: Fuzzy Search APIs (033-fuzzy-search)

## Decision 1: Normalization Implementation

**Decision**: Use Python stdlib `unicodedata` for accent removal + manual punctuation stripping. No external dependency needed.

**Rationale**: `unicodedata.normalize('NFD', text)` decomposes accented characters into base + combining marks. Filtering out characters where `unicodedata.combining(c) != 0` removes the combining marks, leaving the base character. This covers all Latin accents (é → e, ñ → n, etc.) without needing a third-party library.

Punctuation (apostrophes, dashes, periods, etc.) is replaced with a single space using a simple `re.sub('[^\w\s]', ' ', text)` approach after NFD decomposition.

**Alternatives considered**:
- `Unidecode` (third-party) — handles more edge cases (Cyrillic, etc.) but unnecessary for the target use case (Latin-script tango names).
- Manual mapping tables — fragile and high maintenance.

---

## Decision 2: Fuzzy Scoring Library

**Decision**: Use `rapidfuzz>=3.0` as a required runtime dependency.

**Rationale**: `rapidfuzz` is significantly faster than `difflib` (10-100x), uses the same Levenshtein-based algorithms, and provides `fuzz.ratio`, `fuzz.partial_ratio`, and `fuzz.token_set_ratio` in a single package. It is actively maintained, has zero dependencies, and is appropriate as a production runtime dependency for a Python library.

**Alternatives considered**:
- `difflib.SequenceMatcher` — stdlib, but ~50x slower and no token-set matching.
- `thefuzz` (formerly `fuzzywuzzy`) — wraps `python-Levenshtein`; more complex install.

---

## Decision 3: Scoring Formula

**Decision**: Additive score with tiered boosts for deterministic ranking.

**Score components** (constants to be defined in the search module):

| Signal | Boost value | Condition |
|--------|-------------|-----------|
| `BOOST_EXACT` | 1000 | `norm_query == norm_name` or `norm_query == norm_slug` |
| `BOOST_PREFIX_NAME` | 500 | `norm_name.startswith(norm_query)` |
| `BOOST_PREFIX_SLUG` | 400 | `norm_slug.startswith(norm_query)` |
| `BOOST_WORD_PREFIX` | 300 | any word in `norm_name.split()` starts with `norm_query` |
| `BOOST_SUBSTRING_NAME` | 200 | `norm_query in norm_name` |
| `BOOST_SUBSTRING_SLUG` | 150 | `norm_query in norm_slug` |
| `BOOST_SUBSTRING_EXT` | 50 | `norm_query in norm_ext_id` (only when `ext_id != ""`) |
| Fuzzy additive | fuzz scores / 100.0 | `fuzz.ratio + fuzz.partial_ratio + fuzz.token_set_ratio` summed and divided |

**Fuzzy threshold**: A candidate with no boost (score == 0 from non-fuzzy signals) is included only if its best RapidFuzz score (max of ratio, partial_ratio, token_set_ratio against name and slug) is ≥ 70. This threshold is defined as a named constant `FUZZY_THRESHOLD: Final[int] = 70`.

**Tie-breaking**: Sort key is `(-score, norm_name)` — highest score first, then alphabetical by normalized name.

---

## Decision 4: Search Logic Location

**Decision**: New module `taxomesh/application/search.py` for the scoring engine; `TaxomeshService` delegates to it.

**Rationale**: Adding ~200 lines of scoring logic directly to `service.py` would make it unwieldy. A separate module keeps concerns separated while remaining in the `application/` layer. This aligns with Principle XI (class-based design) and KISS.

**Design**: A `SearchEngine` class with:
- `normalize(text: str) -> str` — public staticmethod for normalization
- `score_candidate(query: str, name: str, slug: str, external_id: str) -> float | None` — returns `None` if below threshold, float score otherwise
- Scoring constants defined at module level as `Final[int]` (Principle X)

`TaxomeshService` instantiates and calls `SearchEngine` from inside the two new public methods. No import at module level required for `rapidfuzz` in `service.py` — it is imported at the top of `search.py`.

---

## Decision 5: Candidate Loading Strategy for `category_id` filter

**Decision**: Use `self.list_items(category_id=X)` for direct-member search (already exists). For `recursive=True`, build a descendant set via BFS over `self._repo.list_category_parent_links()`, collect items from each category, and deduplicate by `item_id`.

**Rationale**: `list_items(category_id=X)` already validates existence and raises `TaxomeshCategoryNotFoundError` when needed. Reusing it is DRY. The BFS traversal pattern mirrors the existing `dag.py` approach.

**Deduplication**: An item placed in both category X and child category C should appear only once in results. Deduplication by `item_id` is applied before scoring.

---

## Decision 6: Candidate Loading for `search_categories(parent_id=None)`

**Decision**: When `parent_id=None`, load all categories via `self._repo.list_categories()` and filter out the root category (`category.category_id == self._root_id`). Do NOT use `self.list_categories()` (which returns root-level categories only when `parent_id=None`).

**Rationale**: `TaxomeshService.list_categories(parent_id=None)` returns roots of the user-visible tree, not all categories. A search across all categories requires iterating the full repository list.

---

## Decision 7: `enabled` Filtering Timing

**Decision**: Apply `enabled_only` filter after loading candidates, before scoring.

**Rationale**: The repository has no `enabled` filter parameter. Filtering in Python after load is consistent with the service-layer-only approach and avoids adding repository interface changes.

---

## Decision 8: `external_id` Sentinel Handling

**Decision**: Skip external_id matching when `external_id == ""` (the sentinel for "no external id").

**Rationale**: Both `Item.external_id` and `Category.external_id` use `""` (empty string) as their default sentinel value (see `DEFAULT_ITEM_EXTERNAL_ID` and `DEFAULT_CATEGORY_EXTERNAL_ID` in `taxomesh/domain/constants.py`). The field is never `None` at runtime due to Pydantic validators that coerce `None → ""`. Matching an empty string would be meaningless and should be skipped.
