# Research: Item-to-Categories Lookup (045)

**Branch**: `045-item-categories-lookup` | **Date**: 2026-03-21

---

## Decision 1: Implementation pattern in TaxomeshService

**Decision**: Mirror the existing `list_items(category_id=...)` pattern exactly, applied in the inverse direction.

**Rationale**:
- `list_items(category_id=...)` (service.py:460) already implements the category→items traversal using `list_item_parent_links()` + filter + sort. The new method is the exact dual: item→categories.
- Reusing the same structural pattern ensures behavioural consistency, is easy to review, and needs no new infrastructure.
- `list_item_parent_links()` is confirmed present in `TaxomeshRepositoryBase` (ports/repository.py:231) and in all four backends (JsonRepository, YAMLRepository, DjangoRepository, InMemoryRepository).

```python
@memoize(DEFAULT_CACHE_TTL)
def list_categories_by_item(self, item_id: UUID) -> list[Category]:
    self.get_item(item_id)          # raises TaxomeshItemNotFoundError if missing
    links = sorted(
        [lnk for lnk in self._repo.list_item_parent_links() if lnk.item_id == item_id],
        key=lambda lnk: lnk.sort_index,
    )
    return [self.get_category(lnk.category_id) for lnk in links]
```

**Alternatives considered**:
- Adding a `get_categories_for_item(item_id)` method to the repository protocol — rejected: the protocol already exposes `list_item_parent_links()`, and adding a higher-level method violates the principle that orchestration belongs in the service layer, not in adapters.
- Filtering inside the repository — rejected: same reason; adding business logic to adapters violates Principle I.

---

## Decision 2: Repository protocol changes

**Decision**: No changes to `TaxomeshRepositoryBase` or any repository implementation.

**Rationale** (confirmed by code inspection):
- `list_item_parent_links()` exists in `taxomesh/ports/repository.py` at line 231 with return type `list[ItemParentLink]`.
- All backends implement it: `JsonRepository`, `YAMLRepository`, `DjangoRepository`, and `InMemoryRepository` (test fixture in `tests/service/conftest.py`).
- No new protocol methods needed.

---

## Decision 3: Cache invalidation

**Decision**: No changes to cache invalidation. The existing `clear_all_caches()` calls in all write methods automatically cover the new memoized method.

**Rationale** (confirmed by code inspection):
- `place_item_in_category` calls `clear_all_caches()` at service.py:771.
- `remove_item_from_category` calls `clear_all_caches()` at service.py:1232.
- `reorder_items_in_category` calls `clear_all_caches()` at service.py:1214.
- `clear_all_caches()` is a global clear: it iterates the registry of all `@memoize`-decorated functions and clears every one. A new `@memoize(DEFAULT_CACHE_TTL)` method is registered automatically when first called. No manual registration is needed.

---

## Decision 4: Test file location

**Decision**: New dedicated file `tests/service/test_service_list_categories_by_item.py`.

**Rationale**:
- `tests/service/` is the established home for service-layer tests.
- A dedicated file is preferred over appending to `test_service_items.py` because the new feature has its own focused scope and 5+ test cases; keeping them separate avoids growing the items test file unnecessarily.
- Pattern matches `test_service_external_id_clear.py` from spec 043 — a dedicated file for a focused new feature.
- The shared `service` fixture from `tests/service/conftest.py` (InMemoryRepository-backed) is used for most cases; `json_service` and `yaml_service` may be used for backend parity tests.

---

## Decision 5: Placement of new method in service.py

**Decision**: Add `list_categories_by_item` immediately after `list_items` (service.py:480), in the Item Operations section.

**Rationale**:
- `list_items` is the forward traversal (category→items). `list_categories_by_item` is its inverse (item→categories). Placing them adjacent communicates their relationship and makes it easy to cross-reference.
- No functional difference to placement elsewhere; this is purely for readability.

---

## Decision 6: README update location

**Decision**: Add a new subsection "Resolving which categories an item belongs to" in the README between the quick-start example and the "Resolving items and categories by external_id" section.

**Rationale**:
- The quick-start example already shows `place_item_in_category` — the new lookup is the natural follow-on question ("I placed an item, now how do I query it?").
- This mirrors the existing pattern of documenting each public operation in a dedicated subsection with a minimal code example.

---

## Summary: What changes

| Component | Change |
|-----------|--------|
| `taxomesh/application/service.py` | Add `list_categories_by_item` method (~15 lines) |
| `tests/service/test_service_list_categories_by_item.py` | New test file (~60 lines, 7+ test cases) |
| `README.md` | New subsection documenting `list_categories_by_item` |
| `CHANGELOG.md` | New entry under `[Unreleased]` describing the feature |
| All repositories | No change |
| Repository protocol | No change |
| Domain models | No change |
| Cache infrastructure | No change |
