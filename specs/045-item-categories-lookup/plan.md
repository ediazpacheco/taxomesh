# Implementation Plan: Item-to-Categories Lookup

**Branch**: `045-item-categories-lookup` | **Date**: 2026-03-21 | **Spec**: [spec.md](spec.md)

## Summary

Add `TaxomeshService.list_categories_by_item(item_id: UUID) -> list[Category]` — the inverse of the existing `list_items(category_id=...)` traversal. The method reads item-to-category placement links from the repository, filters by `item_id`, sorts by `sort_index` ascending, and maps each link to its `Category`. It raises `TaxomeshItemNotFoundError` on unknown items, returns `[]` for unplaced items, includes disabled categories, and is memoized with the standard TTL. No repository, protocol, or domain-model changes are required.

---

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Pydantic v2 (domain models), stdlib `uuid`, `typing.Final`
**Storage**: All backends unchanged — `list_item_parent_links()` confirmed present in JsonRepository, YAMLRepository, DjangoRepository, and InMemoryRepository
**Testing**: pytest + conftest.py `service` fixture (parametrized over InMemoryRepository, JsonRepository, YAMLRepository, DjangoRepository)
**Target Platform**: Library (no server, no HTTP)
**Performance Goals**: Same as existing read methods — cached at `DEFAULT_CACHE_TTL` (5 s)
**Constraints**: mypy `--strict`; ruff line-length 119; no new runtime dependencies
**Scale/Scope**: Single service method + test file + documentation updates

---

## Constitution Check

### Pre-implementation gate

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Hexagonal Architecture** | ✅ Pass | New method in application layer only; no adapter imports at module level |
| **II. TaxomeshService as single facade** | ✅ Pass | Method added to `TaxomeshService`; no alternative entry point |
| **III. Repository as Protocol** | ✅ Pass | Uses only `list_item_parent_links()` already in the protocol; no new protocol methods |
| **IV. Pydantic + mypy strict** | ✅ Pass | Return type `list[Category]`; input `UUID`; no `Any` required |
| **V. Exception hierarchy** | ✅ Pass | Raises `TaxomeshItemNotFoundError` (existing) for missing item |
| **VI. DAG integrity** | ✅ Pass | Read-only method; no graph modification |
| **VIII. Quality gates** | ✅ Pass | New tests required; existing gates must continue to pass |
| **X. Named constants** | ✅ Pass | Uses `DEFAULT_CACHE_TTL` (already defined); no new magic literals |
| **XI. OO by default** | ✅ Pass | Method added to existing class |

No violations. No complexity tracking needed.

---

## Project Structure

### Documentation (this feature)

```text
specs/045-item-categories-lookup/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── contracts/
│   └── service-api.md   # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (affected files only)

```text
taxomesh/
└── application/
    └── service.py                          # Add list_categories_by_item method

tests/
└── service/
    └── test_service_list_categories_by_item.py   # New test file

README.md                                  # Add new subsection
CHANGELOG.md                               # Add [Unreleased] entry
```

---

## Phase 0: Research

See [research.md](research.md) — all unknowns resolved.

**Key findings**:
- `list_item_parent_links()` confirmed in protocol and all backends — no protocol changes needed.
- `clear_all_caches()` is a global clear; new `@memoize` methods are automatically covered.
- Implementation is a direct dual of `list_items(category_id=...)`.
- New test file: `tests/service/test_service_list_categories_by_item.py`.

---

## Phase 1: Design

See [data-model.md](data-model.md) and [contracts/service-api.md](contracts/service-api.md).

---

## Phase 2: Implementation

### Task overview

| Task | File | Type | Depends on |
|------|------|------|------------|
| T-01 | `tests/service/test_service_list_categories_by_item.py` | Test (failing) | — |
| T-02 | `taxomesh/application/service.py` | Implementation | T-01 |
| T-03 | `README.md` | Documentation | T-02 |
| T-04 | `CHANGELOG.md` | Documentation | T-02 |

---

### T-01: Write failing tests

**File**: `tests/service/test_service_list_categories_by_item.py` (new)
**Fixture**: `service` (from `conftest.py` — InMemoryRepository-backed)

Test cases required (per spec SC-006):

| Test ID | Scenario | Expected |
|---------|----------|----------|
| `test_empty_when_item_has_no_placements` | Item created, never placed | Returns `[]` |
| `test_single_category` | Item placed in one category | Returns list with that category |
| `test_multiple_categories_ordered_by_sort_index` | Item placed in 3 categories with sort_index 5, 1, 3 | Returns `[sort=1, sort=3, sort=5]` |
| `test_nonexistent_item_raises` | `uuid4()` never created | Raises `TaxomeshItemNotFoundError` |
| `test_disabled_category_included` | Item placed in a category; category then disabled | Disabled category still in result |
| `test_removed_placement_not_returned` | Item placed then removed from category | Category not in result after removal |
| `test_cache_invalidated_after_place` | Result cached; then `place_item_in_category` called | New result reflects updated placement |

All 7 tests must be **red** before T-02 begins (TDD gate).

---

### T-02: Implement `list_categories_by_item`

**File**: `taxomesh/application/service.py`
**Location**: After `list_items` (currently at line ~480), in the Item Operations section

```python
@memoize(DEFAULT_CACHE_TTL)
def list_categories_by_item(self, item_id: UUID) -> list[Category]:
    """Return the categories in which the given item has an active placement.

    Categories are returned in ascending sort_index order (the order defined
    by item-to-category placement links). This is a structural graph read —
    disabled categories are included; filtering by enabled state is the
    caller's responsibility.

    Args:
        item_id: The library-assigned UUID of the item.

    Returns:
        List of Category objects ordered by ItemParentLink.sort_index ascending.
        Returns an empty list when the item has no placements.

    Raises:
        TaxomeshItemNotFoundError: If no item with the given item_id exists.

    Example::

        cats = svc.list_categories_by_item(album.item_id)
        # [Category(name="Jazz", ...), Category(name="Music", ...)]
        # — ordered by sort_index assigned at placement time
    """
    self.get_item(item_id)
    links = sorted(
        [lnk for lnk in self._repo.list_item_parent_links() if lnk.item_id == item_id],
        key=lambda lnk: lnk.sort_index,
    )
    return [self.get_category(lnk.category_id) for lnk in links]
```

**Quality gate after T-02**:
```bash
pytest tests/service/test_service_list_categories_by_item.py   # all 7 green
ruff check taxomesh/application/service.py
ruff format --check taxomesh/application/service.py
mypy --strict taxomesh/application/service.py
```

---

### T-03: Update README

**File**: `README.md`
**Location**: After the quick-start code block (after line ~114), before the "Resolving items and categories by external_id" section

Add subsection:

```markdown
### Resolving which categories an item belongs to

`list_categories_by_item()` is the inverse of `list_items(category_id=...)` — it answers
*"which categories does this item belong to?"*, ordered by sort position:

\`\`\`python
cats = svc.list_categories_by_item(album.item_id)
# [Category(name="Jazz", ...), Category(name="Vinyl", ...)]
# — ordered by the sort_index set when the item was placed
\`\`\`

If the item has no placements, an empty list is returned. Disabled categories
are included; filtering by `enabled` state is the caller's responsibility.
Raises `TaxomeshItemNotFoundError` when the item does not exist.
```

---

### T-04: Update CHANGELOG

**File**: `CHANGELOG.md`
**Location**: Under `## [Unreleased]`

Add:

```markdown
### Added

#### `TaxomeshService.list_categories_by_item`

New public method `list_categories_by_item(item_id: UUID) -> list[Category]` exposes the
item→categories traversal direction that was previously missing from the service API.

- Returns all categories in which the item has an active placement link.
- Ordered by `ItemParentLink.sort_index` ascending.
- Raises `TaxomeshItemNotFoundError` if the item does not exist.
- Returns `[]` if the item has no placements.
- Disabled categories are included (structural read; filtering is the caller's
  responsibility).
- Result is memoized at `DEFAULT_CACHE_TTL`; automatically invalidated by
  `place_item_in_category`, `remove_item_from_category`, and
  `reorder_items_in_category`.
- No repository or domain-model changes required.
```

---

## Final Quality Gate

Before proposing a commit:

```bash
ruff check .
ruff format --check .
mypy --strict .
pytest --cov=taxomesh --cov-fail-under=80
```

All gates must be green.

---

## Risk Register

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| mypy type error on lambda in sorted() | Low | Mirror exact pattern from `list_items` which already passes |
| Cache test proves flaky (TTL timing) | Low | Test via `place_item_in_category` flush, not time-based sleep |
| InMemoryRepository missing `list_item_parent_links()` | None | Confirmed present in conftest.py |
