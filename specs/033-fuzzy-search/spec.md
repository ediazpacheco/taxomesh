# Feature Specification: Fuzzy Search APIs

**Feature Branch**: `033-fuzzy-search`
**Created**: 2026-03-15
**Status**: Draft
**Input**: User description: "Add broad, typo-tolerant search to taxomesh at the TaxomeshService layer"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Typo-Tolerant Item Search (Priority: P1)

A developer building an app (e.g. a tango lyrics catalog) calls `search_items("piazola")` and
receives results for items whose names are variations of "Piazzolla", without needing to know the
correct spelling. The search normalizes both the query and the candidate data before comparing, so
accent and punctuation differences are invisible to the caller.

**Why this priority**: This is the core value proposition. Without typo tolerance, the feature
provides no advantage over the existing `list_items()` + client-side filter pattern.

**Independent Test**: Can be fully tested by calling `search_items()` with a misspelled query
against a known item set and asserting the intended item appears in the results.

**Acceptance Scenarios**:

1. **Given** an item named "Piazzolla" exists, **When** `search_items("piazola")` is called, **Then** the item appears in results.
2. **Given** an item named "Gallo Ciego" exists, **When** `search_items("gayo ciego")` is called, **Then** the item appears in results.
3. **Given** an item named "Agustín Magaldi" exists, **When** `search_items("agustin magaldi")` is called, **Then** the item appears in results (accent-insensitive).
4. **Given** an item named "D'Arienzo" exists, **When** `search_items("d arienzo")` is called, **Then** the item appears in results (punctuation-insensitive).

---

### User Story 2 - Ranked Results Favor Closer Matches (Priority: P2)

A developer calls `search_items("gallo ciego")` and expects to receive "Gallo Ciego" ranked above
"Gallo" and other partial matches. Exact and near-exact matches appear first; distant fuzzy
matches appear later or not at all.

**Why this priority**: Ranking determines whether the feature is actually useful in practice. A
flat, unranked list forces the consuming app to re-sort, defeating the purpose of the service API.

**Independent Test**: Can be tested by asserting that the first result for an exact-match query is
the exact match, not a partial one.

**Acceptance Scenarios**:

1. **Given** both "Gallo Ciego" and "Gallo" exist as items, **When** `search_items("gallo ciego")` is called, **Then** "Gallo Ciego" appears before "Gallo" in the result list.
2. **Given** "Troilo" exists and "Trola" exists, **When** `search_items("troilo")` is called, **Then** "Troilo" appears before "Trola".
3. **Given** an exact-name match exists, **When** a search matches it exactly, **Then** it is the first result.

---

### User Story 3 - Typo-Tolerant Category Search (Priority: P2)

A developer calls `search_categories("orkesta tipika")` and receives categories matching
"Orquesta Típica", tolerating both typos and accent differences.

**Why this priority**: Category search has identical recall requirements to item search.
It can be tested and delivered independently once the underlying search primitives exist.

**Independent Test**: Can be tested by calling `search_categories()` with misspelled/accentless
queries against a known category set.

**Acceptance Scenarios**:

1. **Given** a category named "Orquesta Típica" exists, **When** `search_categories("orkesta tipika")` is called, **Then** the category appears in results.
2. **Given** a category named "Tango Romántico" exists, **When** `search_categories("tango romantico")` is called, **Then** the category appears in results.

---

### User Story 4 - Scoped Search With Filters (Priority: P3)

A developer can narrow `search_items()` to items belonging to a specific category, or narrow
`search_categories()` to direct children of a specific parent. An optional `recursive` flag on
`search_items()` extends the candidate set to include items in all descendant categories. If the
filter references a non-existent category, a clear error is raised.

**Why this priority**: Scoped search improves precision in apps with many items. It is additive
and does not block the core P1/P2 scenarios.

**Independent Test**: Can be tested independently by calling `search_items(query, category_id=X)`
and asserting only items directly in category X are returned; and separately with `recursive=True`
to assert items from descendant categories are also included.

**Acceptance Scenarios**:

1. **Given** items in categories A and B, **When** `search_items("tango", category_id=A)` is called (default `recursive=False`), **Then** only items directly linked to category A are returned.
2. **Given** category A has a child category C with items, **When** `search_items("tango", category_id=A, recursive=True)` is called, **Then** items from both A and C (and any further descendants) are returned.
3. **Given** a non-existent `category_id` is passed, **When** `search_items()` is called, **Then** `TaxomeshCategoryNotFoundError` is raised.
4. **Given** a non-existent `parent_id` is passed to `search_categories()`, **When** called, **Then** `TaxomeshCategoryNotFoundError` is raised.

---

### User Story 5 - Empty Query and Limit Behavior (Priority: P3)

A developer passing an empty query or a zero/negative limit receives predictable, documented
behavior. Empty queries return an empty list; `limit <= 0` raises a clear error.

**Why this priority**: Edge case handling prevents confusing failures in consuming apps.

**Independent Test**: Can be tested in isolation by calling `search_items("")` and asserting `[]`,
and calling `search_items("x", limit=0)` and asserting `ValueError`.

**Acceptance Scenarios**:

1. **Given** any item set, **When** `search_items("")` is called, **Then** `[]` is returned.
2. **Given** any item set, **When** `search_items("   ")` (whitespace-only) is called, **Then** `[]` is returned.
3. **Given** any item set, **When** `search_items("tango", limit=0)` is called, **Then** `ValueError` is raised.
4. **Given** any item set, **When** `search_items("tango", limit=-1)` is called, **Then** `ValueError` is raised.
5. **Given** 50 matching items, **When** `search_items("tango", limit=10)` is called, **Then** exactly 10 results are returned.

---

### Edge Cases

- What happens when the query matches nothing? Returns `[]`; no error raised.
- What if `enabled_only=True` and all matches are disabled? Returns `[]`.
- What if `enabled_only=False`? Disabled items/categories are included in results.
- What if `limit` exceeds the total number of matches? Returns all matches (fewer than `limit`).
- What if both name and slug match? The item/category appears once, scored from the best signal.
- What if `recursive=True` and category X has no descendants? Behaves identically to `recursive=False` (only direct members considered).
- What if `recursive=True` but `category_id` is not provided? `recursive` is ignored; all items are candidates.
- What if an item or category has `external_id=""` (the empty-string default)? That field is silently skipped; name and slug are still matched normally.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The service MUST expose a `search_items()` operation that accepts a text query and returns a ranked list of matching items.
- **FR-002**: The service MUST expose a `search_categories()` operation that accepts a text query and returns a ranked list of matching categories.
- **FR-003**: Both search operations MUST normalize the query and all candidate fields before comparing: lowercasing, stripping leading/trailing whitespace, collapsing repeated spaces, removing diacritics/accents, and converting punctuation (apostrophes, dashes) to spaces.
- **FR-004**: Both search operations MUST support typo-tolerant matching so that one- or two-character errors in a typical query still return the intended result.
- **FR-005**: Results MUST be sorted in descending order of match quality: exact matches first, prefix matches next, substring matches after that, and fuzzy matches last. Within the same score tier, ties are broken alphabetically by normalized name.
- **FR-006**: Both operations MUST accept a `limit` parameter (default: 20) that caps the number of results returned.
- **FR-007**: Passing `limit <= 0` MUST raise a `ValueError`.
- **FR-008**: An empty or whitespace-only query MUST return an empty list immediately, without loading or scoring any candidates.
- **FR-009**: `search_items()` MUST accept an optional `category_id` parameter that restricts the candidate set to items directly linked to that category. A `recursive` boolean parameter (default: `False`) extends the candidate set to items in all descendant categories when `True`.
- **FR-010**: `search_categories()` MUST accept an optional `parent_id` parameter that restricts the candidate set to direct children of that parent category.
- **FR-011**: If `category_id` or `parent_id` references a non-existent category, `TaxomeshCategoryNotFoundError` MUST be raised.
- **FR-012**: Both operations MUST accept an `enabled_only` parameter (default: `True`). When `True`, disabled items or categories MUST be excluded from the candidate set before scoring.
- **FR-013**: Both operations MUST accept a `fuzzy` parameter (default: `True`). When `False`, fuzzy similarity scoring is skipped; exact, prefix, and substring matching still apply.
- **FR-014**: `search_items()` MUST match candidates against item name, slug, and external_id. When `external_id` equals the empty-string default (`""`), that field is silently skipped; matching proceeds against name and slug only.
- **FR-015**: `search_categories()` MUST match candidates against category name, slug, and external_id. When `external_id` equals the empty-string default (`""`), that field is silently skipped; matching proceeds against name and slug only.
- **FR-016**: Both operations MUST be implemented entirely at the service layer; no repository interface changes are required.
- **FR-017**: Existing service methods (`list_items`, `list_categories`, `get_item_by_slug`, etc.) MUST remain unchanged in signature and behavior.
- **FR-018**: Both methods MUST be documented with docstrings that describe parameters, return value, normalization behavior, ranking heuristics, and raised exceptions.
- **FR-019**: The library MUST declare `rapidfuzz` as a runtime dependency.

### Key Entities

- **Item**: A content entity with a name, slug, optional external_id, and enabled/disabled status. Searched by name, slug, and external_id.
- **Category**: A taxonomy node with a name, slug, optional external_id, and enabled/disabled status. Searched by name, slug, and external_id.
- **Search query**: A raw text string provided by the caller. Normalized internally before any matching occurs.
- **Normalized text**: The canonical form of a string after lowercasing, accent removal, punctuation-to-space conversion, and whitespace collapse.
- **Match score**: An internal numeric value representing how closely a candidate matches the query. Determines result order; not exposed publicly.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A single-character typo in a query returns the intended item or category in the top 5 results for any realistic catalog entry (verified by the typo-tolerance test cases in the test plan).
- **SC-002**: Accent-stripped queries (e.g. "agustin" for "Agustín") return the intended result as the top-ranked item in 100% of tested cases.
- **SC-003**: Exact name matches are always ranked first when present in the candidate set.
- **SC-004**: An empty or whitespace-only query returns immediately with an empty list, regardless of catalog size.
- **SC-005**: The search test suite covers at least: 14 item-search cases, 8 category-search cases, and 3 ranking-behavior cases as listed in the original feature description's Test Plan.
- **SC-006**: All pre-existing service tests pass unmodified after this feature is delivered.
- **SC-007**: All quality gates pass: linting, formatting, strict type checking, and test coverage at or above 80%.

## Clarifications

### Session 2026-03-15

- Q: Does `search_items(category_id=X)` restrict to direct members only or include items in descendant categories? → A: Add a `recursive: bool = False` parameter. Default `False` returns direct members only; `True` traverses the full descendant subtree.
- Q: When `external_id` is `None` on an item or category, how should search handle it? → A: Skip silently — `external_id` equal to the empty-string default (`""`) is excluded from the match candidate fields; name and slug are still matched.

## Assumptions

- Catalog sizes in v1 target use cases are small enough that loading all candidates via `list_items()` / `list_categories()` before scoring is acceptable. No streaming or pagination is required at the service layer.
- The fuzzy similarity threshold (approximately 70 out of 100) is a starting point and may be tuned after observing real-world query behavior.
- `rapidfuzz` is a stable, actively maintained library appropriate for a production runtime dependency.
- `external_id` on items and categories is a short string; substring matching against it is lower priority than name/slug matching but is included for completeness.
- The `fuzzy=False` mode disables similarity scoring but still applies exact, prefix, and substring matching. It is not a strict-exact-only mode.
- No changes to the public `__init__.py` exports are required beyond what `TaxomeshService` already exposes.
