# Implementation Plan: Category priming and read-through after 060

**Branch**: `061-memoize-priming` | **Date**: 2026-09-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/061-memoize-priming/spec.md`

Regenerated 2026-09-12 for the narrowed, re-scoped spec. The 2026-09-10 plan described a
priming-only design behind a module-level helper; commit `238cd12` implemented it and is
**superseded**, to be replaced in new commits rather than rewritten out of history.

## Summary

Release 060 replaced per-row resolution with batch reads in three service methods. The
per-row calls went through the memoized accessors `get_category` / `get_item`; the batch
reads call the repository directly and bypass that layer. Two things were lost, and only
the first was visible without measuring:

1. A row resolved as a **result** no longer primes the entry a later call needs when that
   row is passed as an **argument**. On a tree walk every child becomes the next call's
   `parent_id`, so every validation became a miss.
2. **The batch ignores the cache even when every row it needs is already in it.** Priming
   alone does not touch this, and measurement (research.md R6) shows priming alone is still
   *above* `0.1.0a49` on two patterns — 8 vs 7, and 120 vs 85 on the
   `list_categories_by_item`-per-item shape the consumer measured and rejected.

So this release ships **both**: the two category methods prime `get_category` with rows
they fetch, and they resolve rows through `get_category`'s cache first, reading only the
misses. That is at or below `0.1.0a49` on every category pattern measured, and a single
cold call still costs exactly 3.

`list_items(category_id=…)` has the identical bypass and is deliberately excluded (FR-007).
The residual is bounded and stated: at most one read per `list_items(category_id=…)` call.

The caching utility becomes a pair of descriptor classes so that insert and lookup are
typed methods on the decorated callable rather than a module-level helper reaching into a
closure with `getattr` and `cast`.

## Technical Context

**Language/Version**: Python 3.13 (`requires-python = ">=3.13"`, ruff `target-version = "py313"`)
**Primary Dependencies**: None new — stdlib `time` and `typing` only
**Storage**: N/A — pure in-process cache behaviour. No stored-data change, no migration.
**Testing**: pytest, with `CaptureQueriesContext` on Django and a repository call spy on the file/in-memory backends (research.md R3)
**Target Platform**: Library consumed by Python applications; Django backend optional
**Performance Goals**: The consumer-shaped 75-node walk costs **103** storage reads, against 177 on `0.1.0a50` and 150 on `0.1.0a49`. A batch needing only cached rows costs 0. A single cold call to each batched method still costs exactly 3.
**Constraints**: 060's exact-constant gates must pass with their constants unmodified and no test edited. `get_item` must never be primed, and a test must fail if it is.
**Scale/Scope**: One utility module rewritten, two service methods changed. No public method added or changed; the decorator's return type changes from a plain callable to a typed callable object.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — verdicts below are the post-design ones.*

| Principle | Verdict | Notes |
|---|---|---|
| I. Hexagonal architecture | ✅ Pass | Changes confined to `application/` and `utils/`. No new cross-layer import. |
| II. `TaxomeshService` single facade | ✅ Pass | No new public entry point; the subtree read that would have added one left the feature on 2026-09-12. |
| III. Repository as Protocol | ✅ Pass | `TaxomeshRepositoryBase` untouched. No port change, so no downstream `mypy --strict` break for custom repositories — unlike 060. |
| IV. Pydantic + mypy strict | ⚠️ Justified | One gradual `MemoizedFunction[..., R]` on a private attribute. No `Any`, no `cast`, no `type: ignore` anywhere. See Complexity Tracking and research.md R2. |
| V. Exception hierarchy | ✅ Pass | No new error path. FR-005 requires priming never changes a not-found error or its message; asserted by test. |
| VI. DAG integrity | ✅ Pass | Not touched. |
| VII. Spec-driven | ✅ Pass | Spec, clarifications and this plan precede implementation; TDD ordering enforced in tasks.md. |
| VIII. Quality gates | ✅ Pass | ruff, ruff format, `mypy --strict`, pytest ≥ 80% required before PR. |
| IX. Framework-agnostic handlers | ✅ Pass | Not touched. |
| X. Named constants | ✅ Pass | No new literals. FR-007 excludes the item path outright rather than thresholding it, so there is deliberately no constant to name. |
| XI. Object-oriented by default | ⚠️ Justified | The redesign *satisfies* the principle for the cache itself — closure state becomes a class. The module-level `_cache_registry` and `clear_all_caches()` stay by the user's decision. See Complexity Tracking. |

## Project Structure

### Documentation (this feature)

```text
specs/061-memoize-priming/
├── plan.md              # This file
├── research.md          # Phase 0 — R1–R4 carried forward, R5–R8 fold in the measurements
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── memoize-cache.md # Phase 1 — the cache's contract
├── checklists/
│   └── requirements.md  # From /speckit.specify, re-validated 2026-09-12
├── measurements/        # Provenance harnesses; excluded from ruff and mypy
└── tasks.md             # Phase 2 (/speckit.tasks)
```

### Source Code (repository root)

```text
taxomesh/
├── utils/
│   └── memoize.py          # REWRITTEN — MemoizedFunction / MemoizedMethod / Miss;
│                           #   prime + cached; the module-level prime() helper is removed
└── application/
    └── service.py          # MODIFIED — _prime_category_cache becomes _resolve_categories
                            #   list_categories(parent_id=…)     → prime + read through
                            #   list_categories_by_item(item_id) → prime + read through
                            #   list_items(category_id=…)        → UNCHANGED (FR-007)

tests/
├── utils/
│   └── test_memoize.py                    # MODIFIED — prime, cached, TTL, unhashable,
│                                          #   every decorated shape, introspection
├── service/
│   ├── test_memoize_priming.py            # REWRITTEN — exact read counts per pattern
│   ├── test_batch_placement_reads.py      # UNCHANGED — 060's gates
│   ├── test_service_cache.py              # UNCHANGED
│   └── test_parity_*.py                   # UNCHANGED — behaviour parity
└── contrib/django/
    └── test_django_placement_queries.py   # UNCHANGED — 060's Django gates
```

**Structure Decision**: Single library, existing layout. Two production files change. The
files carrying 060's regression gates are listed explicitly as unchanged, because FR-006
requires they pass unmodified — **if either needs editing, the change is wrong.**

## Phase 0 — Research

See [research.md](./research.md).

- **R1** — the cache key shape, and how priming must reproduce it
- **R2** — typing insert and lookup under `mypy --strict` without `Any`; keeps the Protocol
  dead end, records why a class with `__get__` is a different mechanism that works, and
  where precision stops on `MemoizedMethod`'s owner
- **R3** — asserting exact read counts across all four backends
- **R4** — why eviction is not bundled, and why invalidation stays as it is
- **R5** — the consumer's own walk (external provenance; not reproducible here)
- **R6** — read counts per access pattern, re-run 2026-09-12, every figure reproduced
- **R7** — retained memory, re-run 2026-09-12
- **R8** — the read ladder; now provenance the API refactor inherits

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md) — the cached entry, and the two new ways to touch it
- [contracts/memoize-cache.md](./contracts/memoize-cache.md) — the cache's contract
- [quickstart.md](./quickstart.md) — what a consumer observes, and what it costs

### The service change, in one shape

Both category methods route their batch through one private resolver. `list_items` does
not, and that asymmetry is the feature:

```python
def _resolve_categories(self, category_ids: set[UUID]) -> dict[UUID, Category]:
    """Resolve rows through get_category's cache first; fetch only the misses, in one read."""
    found: dict[UUID, Category] = {}
    missing: set[UUID] = set()
    for category_id in category_ids:
        hit = self.get_category.cached(category_id)
        if isinstance(hit, Miss):
            missing.add(category_id)
        else:
            found[category_id] = hit
    if missing:
        fetched = self._repo.get_categories_by_ids(missing, enabled=None)
        for category_id, category in fetched.items():
            self.get_category.prime(category, category_id)
        found.update(fetched)
    return found
```

Four properties this has to preserve, each with its own gate:

1. **Cold cost is unchanged.** Every id misses, so there is exactly one
   `get_categories_by_ids` call — what 060's gates fix at 3 for the whole method.
2. **All-cached costs nothing.** `missing` is empty, so no repository call is made at all.
3. **Not-found parity.** A row absent from storage is in `missing`, comes back absent from
   `fetched`, and is therefore absent from `found` — so the caller's existing
   `TaxomeshCategoryNotFoundError` raise fires on the same row with the same message.
4. **Priming is unfiltered and fetch-only.** The batch reads with `enabled=None`, so a
   primed row is the true row; and only rows in `fetched` are primed, so a read-through hit
   never refreshes a timestamp (Clarifications 2026-09-12, FR-002/FR-004).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| **Principle IV** — one gradual `MemoizedFunction[..., R]` as `MemoizedMethod`'s private owner attribute | `__get__`'s body is checked once and generically, so constructing a precisely-typed bound view from it is not expressible. Measured: mypy rejects it with `Overloaded function implementation cannot produce return type of signature 2` plus an `arg-type` error (research.md R2). | Making `MemoizedMethod` generic in the instance type `S` requires a `cast` in `__get__` to compile — which Principle IV and the project's elegance rule both forbid — and buys nothing: `S` appears in no caller-visible signature, so it would be a phantom parameter. The gradual form is confined to one private attribute; `__call__`, `prime`, `cached` and `clear_cache` are all precise in `P` and `R`, so nothing gradual reaches a call site. Not `Any`: `...` is the ParamSpec analogue of a gradual type, and no `Any`, `cast` or `type: ignore` appears in the design. |
| **Principle XI** — the module-level `_cache_registry` and `clear_all_caches()` stay | Every write path in the service calls `clear_all_caches()`. The user decided to leave invalidation exactly as it is (spec Clarifications, 2026-09-11). | Encapsulating the registry is tempting now that the cache is a class, but it is a behaviour surface this feature has no gate for, and the project's task-scope rule forbids refactoring beyond the ask. Note the redesign *reduces* the violation rather than extending it: the per-callable cache moves from closure state into a class. Recorded as follow-up in research.md R4. |
