# Research: Category Fields, Models Refactor, CLI Output & Service Cache

**Feature**: 011-category-models-cli
**Date**: 2026-02-27

## R1: Category Field Additions (enabled + external_id)

**Decision**: Add `enabled: bool = True` and `external_id: ExternalId = ""` to `Category`.

**Rationale**:
- `Item` already has both fields. Adding them to `Category` brings feature parity.
- `enabled` defaults to `True` (same as `Item`).
- `external_id` reuses the existing `ExternalId` type alias (`UUID | str | int`) from `taxomesh/domain/types.py`.
- `external_id` defaults to `""` (empty string) — unlike `Item` where it's required. This is per spec clarification: categories don't require an external identifier.
- Backward compatibility: existing stores without these fields on categories will get defaults via Pydantic model defaults when deserialized.

**Alternatives considered**:
- Making `external_id` required on Category → Rejected: breaks backward compatibility and categories don't need external IDs.
- Using `None` as default for `external_id` → Rejected: `Item` uses `ExternalId` (not `ExternalId | None`), and empty string is consistent with the spec clarification.

## R2: Models Directory Refactor

**Decision**: Convert `models.py` into a `models/` package with one module per class.

**Rationale**:
- Python package `__init__.py` re-exports allow all existing imports (`from taxomesh.domain.models import X`) to keep working without changes.
- Each model class in its own module improves file-level navigation and review.
- The shared base class `ModelBase` goes in `base.py` and is importable from the package.

**Alternatives considered**:
- Keep `models.py` and just add fields → Rejected: user explicitly requested the refactor.
- Split into two files (base + everything else) → Rejected: user requested one module per class.

**Implementation approach**:
1. Create `models/` directory with `__init__.py`
2. Move each class to its own module
3. Import all classes in `__init__.py` for re-export
4. Delete old `models.py`
5. Verify all imports resolve

## R3: CLI Colored Icons for Enabled State

**Decision**: Replace `enabled=True`/`enabled=False` text with Unicode icon + Rich color markup.

**Rationale**:
- Rich ≥ 13.0 handles terminal color capability detection automatically (degrades gracefully).
- Unicode checkmark (`✓`) and cross (`✗`) are widely supported across modern terminals.
- Green for enabled, red for disabled — intuitive color coding.

**Implementation approach**:
- Define named constants for icon characters (per Principle X).
- Update `_add_graph_node()` in `taxomesh/adapters/cli/main.py`.
- Remove `enabled=<value>` text entirely, replace with `[green]✓[/green]` or `[red]✗[/red]`.

**Alternatives considered**:
- Using emoji (✅/❌) → Not chosen: may render with varying widths across terminals.
- Using ASCII only (`[+]`/`[-]`) → Not chosen: less visually distinct than Unicode.

## R4: External ID Display for Categories

**Decision**: Show `external_id` for categories in graph output, same treatment as items.

**Rationale**:
- Items already display `external_id` in yellow.
- Categories with non-empty `external_id` should show it too.
- Empty `external_id` (legacy or new without ID) is omitted — no blank space.

**Implementation approach**:
- In `_add_graph_node()`, add category `external_id` to the category branch label when non-empty.
- Use same yellow styling as items for consistency.

## R5: Memoize Decorator with TTL

**Decision**: Closure-based `memoize(ttl)` decorator in `taxomesh/utils/memoize.py` with a module-level cache registry for bulk invalidation.

**Rationale**:
- Closure-based decorators are the idiomatic Python pattern. A class-based approach would require `__init__`, `__call__`, and `__get__` (descriptor protocol for bound methods) — more boilerplate for no benefit.
- `time.monotonic()` for the TTL clock — monotonic avoids issues with system clock adjustments.
- Cache key: `(args, tuple(sorted(kwargs.items())))` — standard approach for hashable arguments.
- Unhashable arguments: catch `TypeError` and skip caching (call function directly).
- Each decorated function gets its own cache dict in its closure — no shared state between methods.

**Cache invalidation design**:
- The `memoize` module maintains a registry (`list[Callable]`) of `clear_cache` functions — one per decorated function.
- `clear_all_caches()` iterates the registry and calls each `clear_cache()`.
- Each write method on `TaxomeshService` calls `clear_all_caches()` after the write succeeds.
- This is a full cache clear (not selective) — simple, correct, and the 5-second TTL already limits cache duration.

**Implementation approach**:
- `memoize(ttl: float)` returns a decorator that wraps the function.
- Cache stores `{key: (result, timestamp)}` in a closure-scoped dict.
- On call: if key exists and `monotonic() - timestamp < ttl`, return cached result.
- Otherwise: call function, store `(result, monotonic())`, return result.
- Wrapper function gets a `clear_cache` attribute (function that clears the closure dict).
- Module-level `_cache_registry: list[Callable[[], None]]` tracks all `clear_cache` functions.
- Module-level `clear_all_caches()` calls each registered `clear_cache`.
- Type signature uses `ParamSpec` + `TypeVar` for full mypy strict compatibility.
- Applied to `TaxomeshService` read-only methods: `get_category`, `list_categories`, `get_item`, `list_items`, `list_tags`, `get_graph`.
- Default TTL: `DEFAULT_CACHE_TTL: Final[int] = 5` as a module-level constant in `service.py`.

**Alternatives considered**:
- `functools.lru_cache` → Rejected: no TTL support. Items would be cached forever.
- `cachetools.TTLCache` → Rejected: adds external dependency for a simple use case.
- Class-based decorator → Rejected: more boilerplate, less Pythonic (see FR-016 justification).
- Selective cache invalidation (only clear related caches) → Rejected: adds complexity for minimal benefit with a 5-second TTL.

**Testing approach**:
- Unit tests for `memoize` decorator itself (cache hit, TTL expiry, different args, unhashable args, `clear_cache`, `clear_all_caches`).
- Service-level tests: mock the repository, call read-only methods twice, assert repository called once. Call write method, call read again, assert repository called. Use `time.monotonic` patching or short TTL + `time.sleep` for expiry tests.

## R6: `self` Handling in Memoize for Instance Methods

**Decision**: The `memoize` decorator will include `self` in the cache key by default.

**Rationale**:
- When applied to instance methods, `self` is part of `*args`. Different `TaxomeshService` instances will have independent cache entries automatically.
- This is the correct behavior: two service instances pointing to different repositories should not share cache.
- No special `self`-stripping logic needed — the standard `(args, kwargs)` key works correctly.

**Alternatives considered**:
- Stripping `self` from cache key → Rejected: would cause cross-instance cache sharing, which is incorrect.
- Using `id(self)` instead of `self` → Not needed: `TaxomeshService` is a plain class (hashable by identity).
