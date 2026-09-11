# Implementation Plan: Memoize priming for batch reads

**Branch**: `061-memoize-priming` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/061-memoize-priming/spec.md`

## Summary

Release 060 replaced per-row resolution with batch reads in three service methods. The
per-row calls went through the memoized accessors `get_category` / `get_item`; the batch
reads call the repository directly and bypass that layer, so a row resolved as a
**result** no longer primes the entry a later call needs when that row is passed as an
**argument**.

The fix is to give `memoize` an insert path and have the two **category** methods prime
`get_category` with rows they have already fetched. Nothing about the batch reads
themselves changes, so 060's exact-constant gates hold: a single cold call still costs 3
storage reads, because priming writes to a dict rather than reading from storage.

`list_items(category_id=…)` has the identical bypass but is deliberately excluded. It
buys nothing measured — nothing on the item path regressed — and it is expensive and
exposed: 108 MB measured against 0.17 MB for categories, reachable through a public
unauthenticated endpoint on at least one real deployment. See the spec's "Why categories
only".

## Technical Context

**Language/Version**: Python 3.13 (`requires-python = ">=3.13"`, ruff `target-version = "py313"`)
**Primary Dependencies**: None new — stdlib `time` and `typing` only. Pydantic v2 and the existing `taxomesh/utils/memoize.py` are already present.
**Storage**: N/A — pure in-process cache behaviour. No stored-data change, no migration.
**Testing**: pytest, with `CaptureQueriesContext` on the Django backend for exact read counts and a repository call spy for the file/in-memory backends
**Target Platform**: Library consumed by Python applications; Django backend optional
**Project Type**: Single library
**Performance Goals**: A 75-node, 3-level walk costs 102 storage reads, against 177 today and 151 before release 060. An individual lookup of a category just returned by either category method costs 0.
**Constraints**: 060's exact-constant gates must pass with their constants unmodified and no test edited. Priming is bounded by the category count (93 / 0.17 MB measured); the item path is excluded by FR-007 and a test asserts it stays excluded.
**Scale/Scope**: Two service methods, one utility function. No public signature changes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Notes |
|---|---|---|
| I. Hexagonal architecture | ✅ Pass | Changes are confined to `application/` and `utils/`. No new imports cross a layer boundary; the service already calls both the repository batch reads and its own memoized accessors. |
| II. `TaxomeshService` single facade | ✅ Pass | No new public entry point. The three methods keep their signatures and return types. |
| III. Repository as Protocol | ✅ Pass | `TaxomeshRepositoryBase` is untouched. No port change, so no downstream `mypy --strict` break for custom repositories — unlike 060. |
| IV. Pydantic + mypy strict | ⚠️ Justified | The priming entry point takes the decorated function's own arguments, which are only expressible generically. Resolved in research.md R2 using `Concatenate[R, P]` rather than `Any`; if that proves unworkable, any `Any` must carry an inline justification per the principle. |
| V. Exception hierarchy | ✅ Pass | No new error path. FR-004 requires that priming never suppresses the existing not-found error, which is asserted by test. |
| VI. DAG integrity | ✅ Pass | Not touched. |
| VII. Spec-driven | ✅ Pass | Spec and this plan precede implementation; TDD ordering enforced in tasks.md. |
| VIII. Quality gates | ✅ Pass | ruff, ruff format, `mypy --strict`, pytest ≥ 80% all required before PR. |
| IX. Framework-agnostic handlers | ✅ Pass | Not touched. |
| X. Named constants | ✅ Pass | No new literals. FR-007 excludes the item path outright rather than thresholding it, so there is deliberately no constant to name. |
| XI. Object-oriented by default | ⚠️ Justified | See below. |

**Principle XI justification.** `memoize` is an existing module-level decorator holding
its cache in a closure and registering clear-functions in a module-level
`_cache_registry` list. This feature adds a second attribute (`prime`) beside the
existing `clear_cache` attribute, following the established pattern exactly. Converting
the utility to a class is a real improvement — it would remove the module-level mutable
registry the principle disfavours — but it would touch all nine memoized reads and needs
gates of its own. Per the project's task-scope rule ("do NOT refactor beyond what was
asked"), it stays out of scope here and is recorded in research.md R4 as follow-up.

## Project Structure

### Documentation (this feature)

```text
specs/061-memoize-priming/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── memoize-priming.md
├── checklists/
│   └── requirements.md  # From /speckit.specify
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (repository root)

```text
taxomesh/
├── utils/
│   └── memoize.py                 # MODIFIED — add the insert path
└── application/
    └── service.py                 # MODIFIED — two methods prime get_category
                                   #   list_categories(parent_id=…)     → get_category
                                   #   list_categories_by_item(item_id) → get_category
                                   #   list_items(category_id=…)        → UNCHANGED (FR-007)

tests/
├── unit/
│   └── test_memoize.py            # MODIFIED — insert path, TTL, invalidation, unhashable
├── service/
│   ├── test_memoize_priming.py    # NEW — read counts across a repeated-access pattern
│   ├── test_batch_placement_reads.py   # UNCHANGED — 060's gates must still pass
│   └── test_service_cache.py      # UNCHANGED
└── adapters/django/
    └── test_django_placement_queries.py  # UNCHANGED — 060's Django gates
```

**Structure Decision**: Single library, existing layout. Two production files change and
one new test module is added. The two files carrying 060's regression gates are listed
explicitly as unchanged, because FR-005 requires they pass unmodified — if either needs
editing, the change is wrong.

## Phase 0 — Research

See [research.md](./research.md). Open questions carried in:

- **R1** — the cache key shape the accessors use, and how priming must reproduce it
- **R2** — how to type the insert path under `mypy --strict` without `Any`
- **R3** — how to assert a read count of zero across all four backends
- **R4** — why cache eviction is deliberately not bundled

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md) — the cached entry, and what priming adds
- [contracts/memoize-priming.md](./contracts/memoize-priming.md) — the insert path's contract
- [quickstart.md](./quickstart.md) — what a consumer observes, and the memory cost

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Principle XI — module-level cache state extended rather than encapsulated in a class | The insert path has to live where the cache lives, and the cache is a closure inside an existing module-level decorator. Adding `prime` beside `clear_cache` matches the established pattern. | Refactoring `memoize` into a class would touch all nine memoized reads and require its own regression gates. The project's task-scope rule forbids refactoring beyond the ask, and bundling it would put the measured fix behind unrelated risk. Recorded as follow-up in research.md R4. |
| Principle IV — generic typing at the insert path | The insert path accepts whatever arguments the decorated function accepts, which cannot be spelled concretely. | A concrete signature per call site would mean a separate priming helper for `get_category` and `get_item`, duplicating the key construction that `memoize` already owns — a DRY violation and a second place for the key shape to drift. `Concatenate[R, P]` expresses it without `Any`. |
