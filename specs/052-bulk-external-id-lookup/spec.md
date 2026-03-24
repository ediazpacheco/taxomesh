# Feature Specification: Bulk Lookup by External ID (Items & Categories)

**Feature Branch**: `052-bulk-external-id-lookup`
**Created**: 2026-03-23
**Status**: Draft
**Input**: User description: "Implement a bulk lookup API in Taxomesh for resolving items and categories by external_id."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resolve Multiple Items in One Call (Priority: P1)

A calling application has a list of external identifiers and needs to retrieve the corresponding
`Item` domain objects in a single operation. Rather than issuing N separate single-item lookups
(which causes N+1 query patterns), the caller passes all identifiers at once and receives a
dictionary mapping each found identifier to its `Item`.

**Why this priority**: Eliminates the N+1 pattern that motivated this feature. Delivering this
story alone provides the canonical fix for downstream consumers such as LetrasTango's `/videos/`
rebuild.

**Independent Test**: Call the new method with a list of known external IDs and verify that
all matching items are returned keyed by their external ID, without issuing redundant per-item
queries.

**Acceptance Scenarios**:

1. **Given** a repository containing items A, B, and C with distinct external IDs, **When**
   `get_items_by_external_ids(["id-a", "id-b", "id-c"])` is called, **Then** a dict with three
   entries is returned, keyed by each external ID.

2. **Given** a mix of known and unknown external IDs, **When** the method is called with
   `["id-a", "id-unknown"]`, **Then** only the entry for `"id-a"` is in the result; no error
   is raised for `"id-unknown"`.

3. **Given** duplicate external IDs in the input, **When** the method is called with
   `["id-a", "id-a", "id-a"]`, **Then** a single result entry for `"id-a"` is returned;
   no error is raised.

4. **Given** an input that contains blank strings or whitespace-only values, **When** the method
   is called, **Then** those entries are silently ignored and do not appear in the result.

5. **Given** an empty input iterable, **When** the method is called, **Then** an empty dict is
   returned immediately.

---

### User Story 2 - Filter Item Results by Enabled State (Priority: P2)

A caller that only serves active content wants to resolve external IDs but receive only items
that are currently enabled (or disabled). The optional `enabled` keyword argument mirrors the
existing `list_items()` contract.

**Why this priority**: Required for correctness when the caller needs to exclude disabled items
from results — e.g., LetrasTango hiding unpublished authors. Lower priority than P1 because the
un-filtered case already delivers significant value.

**Independent Test**: Populate the repository with enabled and disabled items sharing known
external IDs; call the method with each value of `enabled` (True, False, None) and verify the
correct subset is returned.

**Acceptance Scenarios**:

1. **Given** item X (enabled) and item Y (disabled), both with known external IDs, **When**
   `get_items_by_external_ids([...], enabled=True)` is called, **Then** only item X appears
   in the result.

2. **Given** the same items, **When** `enabled=False`, **Then** only item Y appears.

3. **Given** the same items, **When** `enabled=None` (the default), **Then** both items appear
   in the result regardless of their enabled state.

---

### User Story 3 - Resolve Multiple Categories in One Call (Priority: P3)

A calling application needs to resolve multiple categories by external ID in a single bulk
operation, symmetrical to the item bulk lookup. The root category is always excluded from
results, consistent with `get_category_by_external_id`.

**Why this priority**: Symmetric to US1/US2 for the category domain. Callers that tag items
with category external IDs have the same N+1 problem. Lower priority than item lookup because
the immediate motivating use case (LetrasTango `/videos/`) is item-based.

**Independent Test**: Create several categories with distinct external IDs; call
`get_categories_by_external_ids([...])` and verify all matching non-root categories are
returned keyed by external ID.

**Acceptance Scenarios**:

1. **Given** categories A, B, and C with distinct external IDs, **When**
   `get_categories_by_external_ids(["id-a", "id-b", "id-c"])` is called, **Then** a dict
   with three entries is returned.

2. **Given** the root category has an external ID, **When** that ID is included in the input,
   **Then** the root category is excluded from the result (never returned).

3. **Given** a disabled category and an enabled category both with known external IDs, **When**
   `get_categories_by_external_ids([...], enabled=True)` is called, **Then** only the enabled
   category appears in the result.

4. **Given** the same categories, **When** `enabled=None` (default), **Then** both appear.

5. **Given** missing, blank, or duplicate IDs, **When** the method is called, **Then** the
   same silent-omission and deduplication behaviour as US1 applies.

---

### Edge Cases

- What happens when an external_id is not found? → Silently omitted from the result; no error raised.
- What happens when a matching item or category is disabled and `enabled=None`? → Included in the result.
- What happens when a matching item or category is disabled and `enabled=True`? → Excluded from the result (absent, not an error).
- What happens when all supplied IDs are missing? → Empty dict returned; no error raised.
- What happens when all supplied IDs are blank? → Empty dict returned; no error raised.
- What happens when the input iterable is a generator (consumed once)? → Method must handle
  any `Iterable[str]`, including single-pass iterables.
- What happens when `external_id` values have leading/trailing whitespace? → Each value is
  normalized with `str(value).strip()` before lookup.
- What happens when the root category's external ID is supplied to `get_categories_by_external_ids`?
  → Root category is excluded; result is absent for that ID.

## Requirements *(mandatory)*

### Functional Requirements

#### Item bulk lookup

- **FR-001**: The library MUST expose a method `get_items_by_external_ids` on the service layer
  that accepts an iterable of strings and returns a `dict[str, Item]`.

- **FR-002**: The method MUST accept an optional `enabled` keyword-only argument
  (`bool | None`, default `None` — return all matching regardless of enabled state) to filter
  results by the item's enabled flag.

- **FR-003**: The method MUST normalize each input value by applying `str(value).strip()` before
  matching.

- **FR-004**: The method MUST silently ignore blank strings (empty or whitespace-only after
  normalization); they MUST NOT appear as keys in the result.

- **FR-005**: The method MUST deduplicate input IDs before querying; each unique ID is looked
  up at most once.

- **FR-006**: The method MUST NOT raise for missing, unknown, or disabled IDs; absent or
  filtered-out IDs are simply omitted from the result.

- **FR-007**: The method MUST be implemented as a true bulk operation (single query or single
  data-structure scan), NOT as a loop over `get_item_by_external_id`.

- **FR-008**: The repository port (`TaxomeshRepositoryBase`) MUST declare a corresponding
  `get_items_by_external_ids` abstract method so all adapters implement it consistently.

- **FR-009**: All file-backed adapters (JSON, YAML) MUST implement the bulk method by scanning
  their in-memory store once per call.

- **FR-010**: The Django adapter MUST implement the bulk method using a single ORM query
  (e.g., `external_id__in`).

- **FR-011**: The service layer MUST include a brief docstring documenting the method's
  purpose, parameters, and return value.

- **FR-012**: Tests MUST cover: all IDs present, some IDs missing, all IDs missing, duplicate
  IDs, blank/whitespace IDs, `enabled=True`, `enabled=False`, `enabled=None`.

#### Category bulk lookup

- **FR-013**: The library MUST expose a symmetric method `get_categories_by_external_ids` on
  the service layer that accepts an iterable of strings and returns a `dict[str, Category]`.

- **FR-014**: `get_categories_by_external_ids` MUST apply the same normalization, deduplication,
  blank-skipping, and enabled-filtering behaviour as `get_items_by_external_ids`.

- **FR-015**: The root category MUST always be excluded from the result of
  `get_categories_by_external_ids`, even when its external_id appears in the input.

- **FR-016**: The repository port MUST declare a corresponding `get_categories_by_external_ids`
  abstract method so all adapters implement it consistently.

- **FR-017**: All adapters (JSON, YAML, Django) MUST implement `get_categories_by_external_ids`
  using the same bulk strategy as `get_items_by_external_ids` for their backend.

- **FR-018**: Tests MUST cover the same cases as FR-012 plus root-category exclusion.

### Key Entities

- **Item**: A domain object representing a tagged entity in the taxonomy. Has an `external_id`
  (`str | None`) field that acts as a 1:1 unique identifier assigned by the calling application.
  The `enabled` flag controls whether the item is active.

- **Category**: A node in the taxonomy DAG. Has an `external_id` (`str | None`) field with the
  same 1:1 unique semantics as Item. The root category is a special sentinel and is always
  excluded from bulk category results.

- **ExternalId (input set)**: The set of caller-supplied string identifiers. After normalization
  and deduplication, this set drives the lookup; the result maps each found ID back to its
  domain object.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A caller resolving 100 items by external ID issues exactly one data-store query
  regardless of how many IDs are supplied.

- **SC-002**: A caller resolving 100 categories by external ID issues exactly one data-store
  query regardless of how many IDs are supplied.

- **SC-003**: Both methods return a result for every supplied ID that exists (and passes the
  enabled filter) in the store, with zero false negatives.

- **SC-004**: Neither method raises an exception for any combination of missing, blank,
  duplicate, or disabled IDs.

- **SC-005**: All test categories (present, missing, duplicate, blank, enabled filter, root
  exclusion) pass in each adapter's test suite (JSON, YAML, Django).

- **SC-006**: Existing callers of `get_item_by_external_id` and `get_category_by_external_id`
  (single-item/category lookup) are unaffected; no breaking changes are introduced.

## Assumptions

- The default value for `enabled` is `None` (return all items/categories regardless of enabled
  state). This differs from `list_items()` / `list_categories()` which default to `True`.
  Rationale: a bulk lookup by explicit IDs is a targeted resolution operation, not a browsable
  list; callers opt in to filtering by passing `enabled=True` explicitly.
- No new migration is required; `external_id` already has a database index from spec 032.
- The root category exclusion in `get_categories_by_external_ids` mirrors the existing
  behaviour of `get_category_by_external_id` in `TaxomeshService`.
