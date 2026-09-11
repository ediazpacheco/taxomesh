# Tasks: Memoize priming for batch category reads

**Feature**: `061-memoize-priming` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

**TDD is mandatory** for this project — every implementation task below is preceded by
the test task that must fail first. No implementation task may be started before its
paired test is written and observed failing.

---

## Phase 1: Setup

- [ ] T001 Confirm the working tree is clean and the branch is `061-memoize-priming`, then record the baseline: run `uv run pytest -q` and note the passing count, so any later change in that number is attributable.

---

## Phase 2: Foundational — the cache insert path

**Blocks every user story.** Nothing in Phase 3+ can be written until `prime` exists.

- [ ] T002 Write failing unit tests for the insert path in `tests/utils/test_memoize.py`: priming a memoized function makes the next matching call a hit; the primed value is returned verbatim; priming a *non*-memoized function is a silent no-op rather than an error.
- [ ] T003 Write failing unit tests for insert-path edge cases in `tests/utils/test_memoize.py`: priming with unhashable arguments is a no-op and does not raise; priming twice for the same key is idempotent in effect and refreshes the timestamp; a primed entry expires on TTL exactly as a normally written one; `clear_all_caches()` clears a primed entry.
- [ ] T004 Implement `prime(func, value, /, *args, **kwargs) -> None` in `taxomesh/utils/memoize.py` per [contracts/memoize-priming.md](./contracts/memoize-priming.md). Reuse the wrapper's own key construction — extract it to a shared closure rather than duplicating it (research.md R1). Keep `memoize`'s return type as `Callable[P, R]`; do **not** widen it to a Protocol (research.md R2 — that breaks method binding).
- [ ] T005 Verify `uv run mypy --strict taxomesh/utils/memoize.py` passes with no `Any` and no new `type: ignore` beyond the one already present on `clear_cache`. If `Any` proves unavoidable, it MUST carry an inline justification per Constitution Principle IV.

**Checkpoint**: `prime` exists, is typed, and is unit-tested. T002–T003 now pass.

---

## Phase 3: User Story 1 — a second read does not re-fetch a category (Priority: P1)

**Goal**: Reading categories through either category batch method leaves them cached, so
a later lookup — including the next step of a tree walk — costs nothing.

**Independent test**: Perform a category batch read, then look up a returned category
individually, and assert zero storage reads.

- [ ] T006 [P] [US1] Write a failing test in `tests/service/test_memoize_priming.py`: after `list_categories(parent_id=…)`, fetching a returned child by id costs zero repository reads (spy at the repository boundary).
- [ ] T007 [P] [US1] Write a failing test in `tests/service/test_memoize_priming.py`: after `list_categories_by_item(item_id)`, fetching a returned category by id costs zero repository reads.
- [ ] T008 [US1] Write a failing test in `tests/service/test_memoize_priming.py` asserting the headline property: a tree walk pays exactly **one** category validation — its own root, which nothing returns as a child — regardless of tree size. Assert at two sizes (a 12-node/3-deep and an 84-node/4-deep tree) so the constant is shown to be size-invariant, which is the real claim; a per-node cost would make it track the node count. Assert **exact** values, not upper bounds (FR-006).
- [ ] T009 [US1] Implement priming in `list_categories(parent_id=…)` in `taxomesh/application/service.py` — prime `get_category` from the `get_categories_by_ids` batch already fetched, before the enabled filter is applied so the cached value stays unfiltered (FR-003, User Story 3 scenario 4).
- [ ] T010 [US1] Implement priming in `list_categories_by_item(item_id)` in `taxomesh/application/service.py`, same shape as T009.
- [ ] T011 [US1] Run `uv run pytest tests/service/test_memoize_priming.py -q` — T006–T008 pass.

**Checkpoint**: The measured regression is fixed. This alone is the MVP.

---

## Phase 4: User Story 2 — release 060 is untouched (Priority: P1)

**Goal**: 060's exact-constant gates pass with their constants unmodified.

**Independent test**: Run 060's gate files unmodified.

- [ ] T012 [US2] Run `uv run pytest tests/service/test_batch_placement_reads.py tests/adapters/django/test_django_placement_queries.py tests/service/test_service_cache.py -q` and confirm every gate passes. **No test in these files may be edited.** If any fails, the implementation is wrong — fix the implementation, not the gate.
- [ ] T013 [US2] Add a test in `tests/service/test_memoize_priming.py` asserting that a single **cold** call to each of the two primed methods costs exactly 3 repository reads, matching 060 — priming writes to memory and must add no read (FR-005).

**Checkpoint**: The fix cannot have re-introduced what 060 removed.

---

## Phase 5: User Story 3 — cached values stay correct (Priority: P1)

**Goal**: A primed entry is indistinguishable from a normally cached one.

**Independent test**: Prime, mutate the underlying row, assert the next read reflects the mutation.

- [ ] T014 [P] [US3] Write a test in `tests/service/test_memoize_priming.py`: after priming, updating a category invalidates the primed entry, and the next read returns the updated row rather than the primed one.
- [ ] T015 [P] [US3] Write a test in `tests/service/test_memoize_priming.py`: a category absent from the batch is not primed, and a later individual lookup still raises `TaxomeshCategoryNotFoundError` with the same message as today (FR-004).
- [ ] T016 [P] [US3] Write a test in `tests/service/test_memoize_priming.py`: with `enabled=True`, a *disabled* category returned by the unfiltered batch is primed with its true value, so a later direct `get_category` returns it rather than raising or returning a filtered view (FR-003).
- [ ] T017 [US3] Parametrise the User Story 1 and 3 tests across all four backends — JSON, YAML, Django, and the in-memory fixture — reusing the existing parity fixtures in `tests/service/conftest.py` (FR-008).

**Checkpoint**: Correctness is closed by test, not by assumption.

---

## Phase 6: User Story 4 — the item path is left alone (Priority: P2)

**Goal**: `list_items(category_id=…)` acquires no item cache, so the 108 MB worst case
cannot reappear unnoticed.

**Independent test**: List a large category's items, assert the per-item cache is empty.

- [ ] T018 [US4] Write a test in `tests/service/test_memoize_priming.py`: after `list_items(category_id=…)` over a multi-item fixture, no `get_item` entry exists — a subsequent `get_item` on a returned item costs exactly one repository read (FR-007, SC-006).
- [ ] T019 [US4] Confirm `list_items` in `taxomesh/application/service.py` is genuinely unmodified by this feature — `git diff` on that method must be empty.

**Checkpoint**: The exclusion is a gate, not a comment. Adding item priming later fails this test, which is the intent.

---

## Phase 7: Polish & cross-cutting

- [ ] T020 [P] Document the behaviour in `docs/` per FR-009: which reads prime, that the item path deliberately does not and why (memory + public-endpoint exposure), the TTL, and that every write clears everything. Any runnable example must pass `tests/docs/test_doc_examples.py`; tag illustrative fragments `python notest`.
- [ ] T021 [P] Add the `[Unreleased]` CHANGELOG entry in `CHANGELOG.md`: the lost-priming mechanism, the 151 → 177 → 102 measurements with their provenance, and the categories-only decision with the 0.17 MB vs 108 MB figures behind it.
- [ ] T022 Run the four quality gates: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy --strict .`, `uv run pytest`. All must pass, coverage at or above 80%.
- [ ] T023 Re-read [quickstart.md](./quickstart.md) against the implementation and correct any statement that no longer matches.
- [ ] T024 Run `/speckit.analyze` and fix until it returns zero deviations. Re-run after every fix, per the project workflow.

---

## Dependencies

```
Phase 1 (T001)
   └── Phase 2 (T002 → T003 → T004 → T005)      BLOCKS EVERYTHING
          ├── Phase 3 US1 (T006,T007 [P] → T008 → T009 → T010 → T011)   ← MVP
          │      └── Phase 4 US2 (T012 → T013)
          │      └── Phase 5 US3 (T014,T015,T016 [P] → T017)
          └── Phase 6 US4 (T018 → T019)          independent of US1–US3
                 └── Phase 7 (T020,T021 [P] → T022 → T023 → T024)
```

**Story independence**: US4 is independent of US1–US3 — it asserts an *absence* and can
be written and passing before priming exists. US2 and US3 both depend on US1 being
implemented, since they constrain its behaviour.

## Parallel opportunities

- **T006 + T007** — different test functions, same new file; write together.
- **T014 + T015 + T016** — three independent correctness tests.
- **T020 + T021** — docs and changelog, different files.

## Implementation strategy

**MVP is Phase 2 + Phase 3.** That delivers the measured fix — the walk goes 177 → 102 —
and is independently shippable. Phases 4–6 are the guardrails that make it safe to ship:
Phase 4 proves 060 is intact, Phase 5 proves correctness, Phase 6 proves the expensive
path stayed excluded. None are optional before a release, but they can be developed and
reviewed as separate increments.

**Do not skip Phase 6.** It is the only thing standing between this feature and the
108 MB footprint the spec rejected — an absent test would let a later contributor add
item priming as an "obvious symmetry" with no signal that it was considered and refused.
