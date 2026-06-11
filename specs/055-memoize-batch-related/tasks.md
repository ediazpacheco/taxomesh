# Tasks: Memoize Batched Related-Items Lookup

**Input**: Design documents from `/specs/055-memoize-batch-related/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/service-api.md, quickstart.md

**Tests**: Included — TDD is mandatory per the repo constitution/CLAUDE.md; every implementation task is preceded by a failing-test task. All test tasks extend `tests/service/test_service_cache.py` (new `TestBatchRelatedItemsCaching` class plus FR-009 tests), mirroring the existing MagicMock style.

**Organization**: Tasks grouped by user story (US1–US4 from spec.md) so each story is independently implementable and testable.

## Phase 1: Setup

- [X] T001 Verify green baseline: run `pytest -q` and `mypy --strict .` from the repo venv (`uv sync --extra dev --extra django --python 3.12` if missing) — all existing tests must pass before any change

## Phase 2: Foundational

*No foundational tasks — the feature builds entirely on existing infrastructure (`taxomesh/utils/memoize.py`, repository ports). Proceed directly to user stories.*

## Phase 3: User Story 1 — Repeated batched lookups served from read cache (P1) 🎯 MVP

**Goal**: `list_related_items_for_sources` serves repeated identical calls from the TTL read cache, querying the repository once.

**Independent Test**: With a MagicMock repository, two identical calls → `repo.list_item_relation_links_for_sources.assert_called_once()`.

- [X] T002 [US1] Add failing tests in `tests/service/test_service_cache.py` (new `TestBatchRelatedItemsCaching` class, `setup_method` calls `clear_all_caches()`): (a) two identical `list_related_items_for_sources` calls hit `repo.list_item_relation_links_for_sources` once and return the same result; (b) TTL expiry (patch `taxomesh.utils.memoize.time`, advance past `DEFAULT_CACHE_TTL`) forces a second repo call; (c) different `source_item_ids` and different `relation_types` filters are independent cache entries (no false hits); (d) empty `source_item_ids` returns `{}` with zero repo calls. Run the class — new tests MUST fail (method not yet memoized).
- [X] T003 [US1] Implement memoization in `taxomesh/application/service.py`: rewrite `list_related_items_for_sources` body to normalise (`unique_ids = frozenset(source_item_ids)`; early-return `{}` when empty; `normalised_types = tuple(sorted({t.strip().lower() for t in relation_types})) if relation_types else None`) and delegate to a new private `_fetch_related_items_for_sources(self, source_item_ids: frozenset[UUID], *, relation_types: tuple[str, ...] | None, skip_on_error: bool)` decorated `@memoize(DEFAULT_CACHE_TTL)` containing the existing repo-call-onwards body unchanged. Update the public docstring to document the read-cache behaviour (TTL, equivalence normalisation, shared-reference results), keeping Google style.
- [X] T004 [US1] Run `pytest tests/service/test_service_cache.py tests/service/test_service_item_relations.py tests/service/test_service_list_related_resilience.py tests/test_logging.py -q` — all pass (new tests green, no behaviour regressions)

**Checkpoint**: US1 delivers the MVP — the batched method joins the read cache.

## Phase 4: User Story 2 — Equivalent calls share one cache entry (P2)

**Goal**: Argument normalisation makes reordered/duplicated/re-cased/padded variants hit one cache entry; `skip_on_error` variants stay distinct.

**Independent Test**: `relation_types=["a","b"]` then `["B", "a ", "b"]` → one repo call.

- [X] T005 [US2] Add failing-or-passing tests in `tests/service/test_service_cache.py` (`TestBatchRelatedItemsCaching`): (a) relation types reordered / duplicated / re-cased / whitespace-padded share one entry (one repo call across variants); (b) source IDs reordered and duplicated share one entry; (c) `relation_types=None` vs `[]` share one entry; (d) `skip_on_error=True` vs `False` are distinct entries (two repo calls). If any test fails, that is a T003 defect.
- [X] T006 [US2] Fix `taxomesh/application/service.py` normalisation only if T005 exposed gaps (expected: none — normalisation shipped in T003); then run `pytest tests/service/test_service_cache.py -q` — all pass

**Checkpoint**: Cache-key equivalence semantics proven by tests.

## Phase 5: User Story 3 — Writes and explicit clearing invalidate (P2)

**Goal**: `clear_all_caches()` and write operations force re-fetch; raised errors are never cached.

**Independent Test**: Warm cache → `clear_all_caches()` → identical call re-queries repo.

- [X] T007 [US3] Add tests in `tests/service/test_service_cache.py` (`TestBatchRelatedItemsCaching`): (a) warm call + `clear_all_caches()` + identical call → 2 repo calls; (b) warm call + `relate_items(...)` write + identical call → 2 repo calls and result reflects updated repo return; (c) with `skip_on_error=False` and a dangling target (target absent from `repo.get_items_by_ids` return), the call raises `TaxomeshItemNotFoundError` and a subsequent identical call re-queries the repo (errors not cached).
- [X] T008 [US3] Verify invalidation requires no code change (automatic via `_cache_registry` in `taxomesh/utils/memoize.py`); fix only if (c) exposes a gap; run `pytest tests/service/test_service_cache.py -q` — all pass

**Checkpoint**: Invalidation contract proven; US1–US3 complete the core feature.

## Phase 6: User Story 4 — Cold-cache bulk target resolution in list_related_items (P3, FR-009)

**Goal**: `list_related_items` resolves targets with one `get_items_by_ids` bulk call instead of one `get_item` per link, behaviour unchanged.

**Independent Test**: Cold cache, item with 3 outgoing links → `repo.get_items_by_ids` called once, `repo.get_item` not called for targets, order preserved.

- [X] T009 [US4] Add failing tests in `tests/service/test_service_cache.py`: (a) cold `list_related_items` with N links resolves via a single `repo.get_items_by_ids(..., enabled=None)` call and zero per-target `repo.get_item` calls; (b) returned items preserve link order (configure `repo.list_item_relation_links` with out-of-order targets); (c) a target missing from the bulk result raises `TaxomeshItemNotFoundError` with message `Item not found: {id}`; (d) `direction="incoming"` resolves sources the same way. Run — (a) MUST fail before implementation.
- [X] T010 [US4] Implement bulk resolution in `taxomesh/application/service.py::list_related_items` per plan.md §Design 2: build ordered ID list from links (`target_item_id` for outgoing, `source_item_id` for incoming), early-return `[]` when empty, single `self._repo.get_items_by_ids(set(ordered_ids), enabled=None)`, rebuild results in link order, raise `TaxomeshItemNotFoundError(f"Item not found: {needed_id}")` on first missing. Docstring updated if behaviour notes warrant it.
- [X] T011 [US4] Run `pytest tests/service/ tests/test_logging.py -q` — all pass (existing relation/resilience suites prove behaviour parity)

**Checkpoint**: All user stories complete.

## Phase 7: Polish & Release (FR-008)

- [X] T012 [P] Add `## [0.1.0a44]` entry to `CHANGELOG.md` under `### Performance` (style of 0.1.0a42/054 entry): memoized `list_related_items_for_sources` (cache-key normalisation, skip_on_error in key, invalidation) + bulk cold-path target resolution in `list_related_items`; reference feature 055
- [X] T013 [P] Bump version `0.1.0a43` → `0.1.0a44` in `pyproject.toml` AND sync `taxomesh/__init__.py::__version__` (regression guard from 0.1.0a43 notes)
- [X] T014 Run full quality gates from the repo venv: `ruff check .` && `ruff format --check .` && `mypy --strict .` && `pytest --cov=taxomesh --cov-fail-under=80` — all green

## Dependencies & Execution Order

- **Phase 1 → everything**: T001 first.
- **US1 (T002→T003→T004)** blocks US2/US3 test semantics (they exercise the cache added in T003). US2 (T005→T006) and US3 (T007→T008) are independent of each other and may run in either order (or in parallel — different test classes/methods, same file ⇒ sequential edits recommended).
- **US4 (T009→T010→T011)** is fully independent of US1–US3 (different method) and may run any time after T001.
- **Polish**: T012 [P] and T013 [P] touch different files and can run in parallel; T014 last.
- Within every story: test task strictly before implementation task (TDD).

```text
T001 ──► T002 ► T003 ► T004 ──► T005 ► T006 ──► T007 ► T008 ──► T012/T013 ► T014
    └──► T009 ► T010 ► T011 ──────────────────────────────────┘
```

## Implementation Strategy

**MVP first**: Complete Phase 3 (US1) — the batched method joins the read cache; this alone removes the cold-vs-warm trade-off. US2/US3 then *prove* equivalence and invalidation semantics (mostly test work — the T003 design already implements them). US4 is an optional cold-path optimisation kept because it stays simple (research.md D5). Release tasks close FR-008.
