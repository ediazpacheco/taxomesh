# Research: External ID Clear Support (043)

**Branch**: `043-clear-external-id` | **Date**: 2026-03-21

---

## Decision 1: Sentinel representation

**Decision**: Use a private singleton class `_UnsetType` with a module-level named constant `_UNSET: Final[_UnsetType]`.

**Rationale**:
- A bare `object()` is not mypy `--strict` safe as a typed sentinel. `str | None | object` collapses to `object` in the type system, losing safety.
- A named class (`_UnsetType`) produces a proper union `str | None | _UnsetType` that mypy understands.
- Principle X (Named Constants) requires `Final[T]`-annotated named constants — `_UNSET: Final[_UnsetType] = _UnsetType()` satisfies this.
- Principle XI (OO by Default) is satisfied: the sentinel is a class, not a bare module-level value.
- The sentinel is private (underscore prefix) — it is not exported and does not appear in the public API contract.

**Alternatives considered**:
- `_UNSET = object()` — rejected: not typed, fails mypy `--strict` in a union.
- `typing.Literal["__unset__"]` — rejected: Literal strings are part of the public domain of str; would conflict if a caller ever passes the same string.
- `enum.Enum` sentinel — rejected: unnecessary weight for a single sentinel value.
- Overloads (`@overload`) — considered: would give cleaner return types but adds significant boilerplate for a two-line logic change. Deferred as YAGNI.

---

## Decision 2: Type annotation in `update_item` / `update_category` signature

**Decision**: `external_id: str | None | _UnsetType = _UNSET`

**Rationale**:
- This is the only mypy `--strict`-compatible annotation that distinguishes all three states as distinct types.
- The isinstance guard `if not isinstance(external_id, _UnsetType)` narrows the type to `str | None` inside the branch, which is exactly the domain model field type — no cast needed.

**Alternatives considered**:
- Keep `external_id: str | None = None` and add a separate boolean `clear_external_id: bool = False` — rejected: two parameters for one semantic concern is a worse API; callers must understand their interaction.
- Use `external_id: str | None = None` with a default of `""` meaning "unchanged" — rejected: `""` is already semantically "cleared" for slug; using it for external_id would be inconsistent and confusing.

---

## Decision 3: Repository layer changes

**Decision**: No repository changes required.

**Rationale** (from code inspection):
- `JsonRepository.save_item/save_category`: uses Pydantic `model_dump(mode="json")` which serialises `None` as JSON `null`. Round-trip through `model_validate()` restores `None` correctly. ✅
- `YAMLRepository.save_item/save_category`: same Pydantic serialisation path; `yaml.safe_dump` renders `null` correctly. ✅
- `DjangoRepository.save_item/save_category`: Django ORM `CharField(null=True, unique=True)` accepts `None` → SQL `NULL`. The DB `UNIQUE` constraint allows multiple `NULL` values (SQL standard). ✅
- `_external_id.check_external_id_unique()` already short-circuits with no-op when `external_id is None`. ✅

All backends can already persist a cleared `external_id`. The bug is entirely in the service layer.

---

## Decision 4: Cache invalidation

**Decision**: No changes to cache invalidation. The existing `clear_all_caches()` call at the end of both `update_item` and `update_category` already invalidates all memoized caches, including `get_item_by_external_id` and `get_category_by_external_id`.

**Rationale**: `clear_all_caches()` iterates the global cache registry and clears every registered TTL cache. Both lookup methods are decorated with `@memoize(DEFAULT_CACHE_TTL)` and registered automatically. The call already happens unconditionally after every write — no additional work is needed.

---

## Decision 5: Test file location

**Decision**: `tests/service/test_service_external_id_clear.py` (new file)

**Rationale**:
- `tests/service/` is the established home for service-layer tests (see `test_service_items.py`, `test_service_categories.py`, `test_service_cache.py`).
- A dedicated file keeps the new scenarios cleanly separated from the existing `tests/test_service_external_id.py` (which tests the lookup methods, not the update semantics).
- The `tests/service/conftest.py` provides the shared fixtures (`json_service`, `yaml_service`) that these tests will use.

---

## Summary: What changes

| Component | Change | Reason |
|-----------|--------|--------|
| `taxomesh/application/service.py` | Add `_UnsetType` class + `_UNSET` constant | Sentinel for three-state `external_id` |
| `taxomesh/application/service.py` | Change `update_item` signature + logic | Support clear vs. no-op |
| `taxomesh/application/service.py` | Change `update_category` signature + logic | Support clear vs. no-op |
| `taxomesh/application/service.py` | Update docstrings for both methods | FR-010 |
| `tests/service/test_service_external_id_clear.py` | New test file with 8 scenarios | SC-001–SC-005 |
| All repositories | No change | Already support None correctly |
| Domain models | No change | `str | None` already defined |
| Cache infrastructure | No change | `clear_all_caches()` already called |
