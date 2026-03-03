# Research: Service Slug Lookup Methods (020-slug-lookup)

## Summary

No external research required. All decisions are resolved from the existing codebase.

---

## Decision 1: Repository layer already exposes slug lookups

**Decision**: Reuse `TaxomeshRepositoryBase.get_category_by_slug(slug: str) -> Category | None`
and `TaxomeshRepositoryBase.get_item_by_slug(slug: str) -> Item | None` — both already
declared in `taxomesh/ports/repository.py` and implemented in all concrete adapters
(`JsonRepository`, `YAMLRepository`, `DjangoRepository`) and the test `InMemoryRepository`.

**Rationale**: The service layer only needs to wrap these nullable calls with not-found
error raising. No new repository method is required.

**Alternatives considered**: Adding a new `get_X_by_slug_or_raise` method at the
repository level — rejected because error raising is an application-layer concern
(see Constitution Principle V and the existing `get_category` / `get_item` pattern).

---

## Decision 2: Memoisation mirrors `get_category` / `get_item`

**Decision**: Decorate both new methods with `@memoize(DEFAULT_CACHE_TTL)` — the same
decorator used on `get_category` and `get_item`.

**Rationale**: Consistent caching across all single-entity reads. Memoised calls are
invalidated by `clear_all_caches()` which is called on every write, keeping the cache
fresh.

**Alternatives considered**: No memoisation — rejected because slug lookup is a hot
path in URL-driven applications and consistency with the UUID-based getters is important.

---

## Decision 3: Error types

**Decision**: Raise `TaxomeshCategoryNotFoundError` for a missing category slug and
`TaxomeshItemNotFoundError` for a missing item slug — exactly matching the types raised
by `get_category` and `get_item` respectively.

**Rationale**: These are the correct leaf exceptions in the existing hierarchy
(Constitution Principle V). Callers can catch at `TaxomeshNotFoundError` if they want
to handle both uniformly.

**Alternatives considered**: Raising a new `TaxomeshSlugNotFoundError` — rejected because
it would fragment the hierarchy unnecessarily and duplicate what the existing errors already
communicate.

---

## Decision 4: Test file placement

**Decision**: Add new test classes to the existing
`tests/service/test_service_slug.py`, which already covers slug create/update behaviour.
No new test file is needed.

**Rationale**: Keeps all slug-related service tests co-located. The file currently tests
write operations; the new classes test the corresponding read operations, making the file
a complete slug test suite.
