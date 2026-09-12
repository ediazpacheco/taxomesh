# Tasks: Category priming and read-through after 060

**Feature**: `061-memoize-priming` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Regenerated 2026-09-12 for the narrowed, re-scoped spec. The previous list described a
priming-only design behind a module-level helper; commit `238cd12` implemented it and is
**superseded** — its code is replaced by the tasks below, in new commits, not by rewriting
history.

**TDD is mandatory** for this project — every implementation task below is preceded by the
test task that must fail first. No implementation task may be started before its paired
test is written and observed failing.

**Story numbering follows the spec**: US1, US2, US3, US5, US6. There is no US4 — the
subtree read left this feature on 2026-09-12 and surviving identifiers were deliberately
not renumbered.

**The constants below are measured, not guessed.** Every number comes from research.md R6,
re-run 2026-09-12 and reproduced exactly. If an implementation produces a different number,
the implementation is wrong — do not adjust the constant.

---

## Phase 1: Setup

- [X] T001 Record the baseline in the 3.13 venv (`uv sync --extra dev --extra django --python 3.13`): run `uv run pytest -q` and note the passing count and coverage, so any later change is attributable. Confirm the branch is `061-memoize-priming`.
- [X] T002 Rebuild the measurement variants so the constants can be re-checked at any point: follow `specs/061-memoize-priming/measurements/README.md` to create the version directories and run `make_variants.py`, then run `reads.py` for `a49`, `a50` and `readthrough`. Confirm the `readthrough` column matches research.md R6. This is a read-only check; it writes nothing into the repository.

---

## Phase 2: Foundational — the cache becomes a pair of descriptor classes

**Blocks every user story.** Nothing in Phase 3+ can be written until `prime` and `cached`
exist. Contract: [contracts/memoize-cache.md](./contracts/memoize-cache.md).

- [X] T003 Write failing unit tests for the call path in `tests/utils/test_memoize.py`: a decorated plain function and a decorated method both cache as they do today; two calls with the same arguments invoke the underlying function once; `clear_cache()` and `clear_all_caches()` both empty it. These must pass before and after the rewrite — they are the parity net.
- [X] T004 Write failing unit tests for `prime` in `tests/utils/test_memoize.py`: priming makes the next matching call a hit; the primed value is returned verbatim; priming a method through an instance keys on that instance, so a second instance still misses (research.md R1); priming with unhashable arguments is a silent no-op that never raises; priming twice for the same key overwrites rather than raising.
- [X] T005 Write failing unit tests for `cached` in `tests/utils/test_memoize.py`: it returns the fresh value for a cached key and `MISS` otherwise; it reports an **expired** entry as a miss; it reports a miss for unhashable arguments without raising; and — the invariant FR-003 turns on — **it never writes**: calling `cached` on a fresh entry leaves its timestamp unchanged, so the entry still expires at the same moment it would have. Use a monkeypatched `time.monotonic` rather than sleeping.
- [X] T006 Write failing unit tests in `tests/utils/test_memoize.py` for the `Miss` sentinel: it is a singleton (`Miss() is Miss()`), and a memoized function whose return type is itself `None` or falsy is still distinguishable from a miss (FR-001).
- [X] T007 Rewrite `taxomesh/utils/memoize.py` per the contract: add `Miss` plus `MISS`, `MemoizedFunction[**P, R]` (owns the cache, `__call__`/`prime`/`cached`/`clear_cache`, and the two `__get__` overloads) and `MemoizedMethod[**P, R]` (prepends its bound instance). `memoize(ttl)` returns `MemoizedFunction[P, R]`. **Remove the module-level `prime()` helper** added in `238cd12` along with `_PRIME_ATTR` and `_Primer` — NFR-005 forbids a new module-level function with side effects, and it was never released. Keep `clear_all_caches()` and the module-level registry exactly as they are (research.md R4, plan Complexity Tracking). Copy the shape from `measurements/unified_proto.py`, which type-checks clean.
- [X] T008 Make `MemoizedFunction` carry the decorated callable's identity, per NFR-003: `__name__`, `__qualname__`, `__module__`, `__doc__` and `__wrapped__`. `functools.wraps` does not apply to a class instance — set them explicitly in `__init__`, and let `inspect.signature` follow `__wrapped__` rather than hand-building `__signature__`.
- [X] T009 Verify `uv run mypy --strict taxomesh/utils/memoize.py` passes with **no `Any`, no `cast`, no `type: ignore`** — including the `# type: ignore[attr-defined]` that the old `wrapper.clear_cache` assignment needed, which the class design removes. The single gradual `MemoizedFunction[..., R]` on `MemoizedMethod`'s owner attribute is expected and must carry the inline comment justifying it (plan Complexity Tracking, research.md R2).
- [X] T010 Confirm the decorator is textually unchanged at all 16 `@memoize(DEFAULT_CACHE_TTL)` sites in `taxomesh/application/service.py`: `git diff` must show no change to any decoration line.

**Checkpoint**: `prime` and `cached` exist, are typed, and are unit-tested. T003–T006 pass, `mypy --strict` is clean, and the whole suite still passes because no call site has changed yet.

---

## Phase 3: User Story 1 — a category already in memory is not read again (Priority: P1)

**Goal**: The two category batch reads prime `get_category` with rows they fetch, and
resolve rows through that cache first, reading only the misses.

**Independent test**: Warm the cache with a category read, then perform a read that needs
only those rows, and assert it costs zero row reads.

- [X] T011 [US1] Add a generic read-counting proxy to `tests/service/conftest.py` that wraps **any** repository — not a subclass of `InMemoryRepository` like `RecordingRepository` in `tests/service/test_service_no_full_scan.py` — delegating every attribute and counting calls whose name starts with `get_`/`list_`, excluding `get_config_summary`. One repository call counts as one storage read (research.md R3, R6). This is what lets one set of constants hold on all four backends.
- [X] T012 [P] [US1] Write a failing test in `tests/service/test_memoize_priming.py`: after `list_categories(parent_id=…)`, fetching a returned child by id costs **0** reads (US1 scenario 1).
- [X] T013 [P] [US1] Write a failing test in `tests/service/test_memoize_priming.py`: after `list_categories_by_item(item_id)`, fetching a returned category by id costs **0** reads (US1 scenario 2).
- [X] T014 [P] [US1] Write a failing test in `tests/service/test_memoize_priming.py`: a batch read whose rows are **all** already cached reads **0** category rows, and one with a mix reads only the uncached ones, in a single batch call (US1 scenarios 3–4, FR-003).
- [X] T015 [US1] Write failing exact-count walk tests in `tests/service/test_memoize_priming.py` at two sizes and two depths: a 12-node depth-2 tree costs **18**, an 84-node depth-3 tree costs **107**. Build the trees with the same shapes `measurements/reads.py` uses. Assert **exact equality**, not bounds (FR-010) — a per-node cost would track the node count, which is the thing being gated.
- [X] T016 [US1] Write a failing exact-count test in `tests/service/test_memoize_priming.py` for the consumer-shaped tree (75 nodes, 3 levels, `consumer_shape()` in `measurements/reads.py`): **103**. Assert in the test's docstring why it is 103 and not 0 — the walk's own root is nobody's child, so nothing primes it and its one validation is a genuine read (SC-001).
- [X] T017 [P] [US1] Write failing exact-count tests in `tests/service/test_memoize_priming.py` for the three remaining category patterns: multi-parent walk over shared children **9**; fetch children by id then list them **7**; `list_categories_by_item` over 40 items sharing 5 categories **84**. Each must also assert it is at or below the `0.1.0a49` value recorded in research.md R6 (12, 7, 85) — that comparison is the spec's actual goal (SC-002).
- [X] T018 [US1] Implement `_resolve_categories(self, category_ids: set[UUID]) -> dict[UUID, Category]` in `taxomesh/application/service.py`, replacing `_prime_category_cache`: consult `self.get_category.cached(cid)` for each id, collect the misses, fetch **only** those in one `get_categories_by_ids(..., enabled=None)` call, prime each fetched row, and merge. Prime only fetched rows — a read-through hit must not be re-primed (FR-002, Clarifications 2026-09-12). When nothing is missing, make no repository call at all. See plan.md "The service change, in one shape".
- [X] T019 [US1] Route `list_categories(parent_id=…)` in `taxomesh/application/service.py` through `_resolve_categories`, replacing the direct `get_categories_by_ids` call and the `_prime_category_cache` call. The enabled filter stays where it is, **after** resolution, so a primed row is the true unfiltered row.
- [X] T020 [US1] Route `list_categories_by_item(item_id)` in `taxomesh/application/service.py` through `_resolve_categories`, same shape as T019.
- [X] T021 [US1] Run `uv run pytest tests/service/test_memoize_priming.py -q` — T012–T017 pass.

**Checkpoint**: The measured regression is fixed on every category pattern. This plus Phase 2 is the MVP.

---

## Phase 4: User Story 2 — release 060's gains and gates are untouched (Priority: P1)

**Goal**: 060's exact-constant gates pass with their constants unmodified.

**Independent test**: Run 060's gate files and the full suite unmodified.

- [X] T022 [US2] Run `uv run pytest tests/service/test_batch_placement_reads.py tests/contrib/django/test_django_placement_queries.py tests/service/test_service_cache.py tests/service/test_service_no_full_scan.py -q` and confirm every gate passes. **No test in these files may be edited.** If any fails, the implementation is wrong — fix the implementation, not the gate (FR-006).
- [X] T023 [US2] Confirm by `git diff` that none of the files in T022 has been modified by this feature. An empty diff is the deliverable.
- [X] T024 [US2] Add exact-count tests in `tests/service/test_memoize_priming.py` for a single **cold** call to each of the three batched methods: `list_items(category_id=…)` **3**, `list_categories(parent_id=…)` **3**, `list_categories_by_item(item_id)` **3** — every id misses, so read-through makes exactly one batch call and adds nothing (SC-003).

**Checkpoint**: The fix cannot have re-introduced what 060 removed.

---

## Phase 5: User Story 3 — cached values stay correct (Priority: P1)

**Goal**: A primed entry is indistinguishable from one the accessor itself would have
stored, and a value served by read-through is exactly what a direct read returns.

**Independent test**: Prime an entry, mutate the underlying row, assert the next read
reflects the mutation.

- [X] T025 [P] [US3] Write a test in `tests/service/test_memoize_priming.py`: after a batch read primes a category, updating that category invalidates the primed entry and the next read returns the updated row (US3 scenario 1, FR-004).
- [X] T026 [P] [US3] Write a test in `tests/service/test_memoize_priming.py`: when a primed entry's lifetime expires, it is treated as absent by **both** the accessor and read-through — the next batch re-fetches it (US3 scenario 2). Monkeypatch `time.monotonic`; do not sleep.
- [X] T027 [P] [US3] Write a test in `tests/service/test_memoize_priming.py`: a category absent from the batch is not primed, and a later individual lookup still raises `TaxomeshCategoryNotFoundError` with the **same message** as today (US3 scenario 3, FR-005). Assert the message string, not just the type.
- [X] T028 [P] [US3] Write a test in `tests/service/test_memoize_priming.py`: with `enabled=True`, a **disabled** category returned by the unfiltered batch is primed with its true value, so a later direct `get_category` returns it rather than raising (US3 scenario 4).
- [X] T029 [P] [US3] Write a test in `tests/service/test_memoize_priming.py` for tie-breaks: children with equal `sort_index` come back from `list_categories(parent_id=…)` in the same relative order with read-through as without, on every backend (Edge Cases). Compare against the order obtained with the cache cleared before each call.
- [X] T030 [US3] Parametrise the US1 and US3 tests across all four backends using the existing `service` fixture in `tests/service/conftest.py` (`in_memory`, `json`, `yaml`, `django`), wrapping each with the T011 proxy so one set of constants holds everywhere (FR-011). Note the known ordering quirk: the django-param service tests need `test_parity_fixture.py` to have run first.

**Checkpoint**: Correctness is closed by test, not by assumption, on all four backends.

---

## Phase 6: User Story 5 — the item path is left alone, and its cost is stated (Priority: P2)

**Goal**: `list_items(category_id=…)` acquires no item cache entries, so the measured
memory cost cannot reappear unnoticed.

**Independent test**: List a category's items, then assert the per-item accessor's `cached`
lookup reports a miss for every one of them.

- [X] T031 [US5] Write a test in `tests/service/test_memoize_priming.py`: after `list_items(category_id=…)`, `svc.get_item.cached(item_id)` returns `MISS` for **every** listed item. Observe it through `cached` — not an entry count, not the cache's internals (FR-007, SC-006, Clarifications 2026-09-12).
- [X] T032 [US5] Write a test in `tests/service/test_memoize_priming.py`: listing a category's items and then fetching one by id costs exactly **1** read for that fetch (US5 scenario 2).
- [X] T033 [US5] Write exact-count tests in `tests/service/test_memoize_priming.py` for the three item patterns, with the `0.1.0a49` value asserted alongside each so the residual is visible in the test itself: `list_items` then `list_categories_by_item` per item (20) → **46** (a49: 45); `list_items` then `get_item` per item (20) → **23** (a49: 22); 10 small `list_items` sharing 3 items → **30** (a49: 23). Assert the bound the spec states — none exceeds `0.1.0a49` by more than one read per `list_items(category_id=…)` call in the pattern (SC-007).
- [X] T034 [US5] Confirm `list_items` in `taxomesh/application/service.py` is genuinely unmodified by this feature — `git diff` on that method must be empty.

**Checkpoint**: The exclusion is a gate, not a comment. Adding item priming later fails T031, which is the intent.

---

## Phase 7: User Story 6 — existing uses keep working, now fully typed (Priority: P2)

**Goal**: Every decorated shape the one production consumer uses keeps working unchanged,
and priming and lookup are statically checked against the decorated function's own
signature.

**Independent test**: Decorate a zero-argument, a keyword-only and a positional function
and a method; call, prime, look up and clear each; inspect name, docstring and signature;
run strict type checking over deliberate misuse.

- [X] T035 [P] [US6] Write tests in `tests/utils/test_memoize.py` covering every decorated shape the consumer uses — zero-argument, keyword-only, positional, positional-plus-keyword-only, and a method — calling, priming, looking up and clearing each. Six of the consumer's own functions are decorated this way, two zero-argument and three keyword-only; a break here costs it more than this feature saves it.
- [X] T036 [P] [US6] Write tests in `tests/utils/test_memoize.py` for introspection (NFR-003, US6 scenario 4): a decorated function and a decorated method each report their own `__name__`, `__qualname__`, `__doc__` and `inspect.signature`, not the cache class's. Include at least one of the 16 memoized service methods, since the constitution requires each to carry a Google-style docstring.
- [X] T037 [US6] Write a test in `tests/utils/test_memoize.py` that runs `mypy --strict` as a subprocess over a fixture file of deliberate misuses and asserts each expected error is reported (SC-009). No such mechanism exists in the suite today — model the fixture on `measurements/unified_misuse.py`, which reports 13 errors, and skip the test when `mypy` is not importable so the suite still runs without the dev extra.
- [X] T038 [US6] Verify the per-callable manual clear and `clear_all_caches()` still work for every shape in T035 (FR-012), including a decorated method cleared through one instance while another instance's entry is also cleared — the registry clears the whole cache, not one key.

**Checkpoint**: The consumer can take this release without editing its own code.

---

## Phase 8: Polish & cross-cutting

- [X] T039 [P] Update the consumer documentation per FR-013 — which reads prime and read through; that listing items does neither and what that costs relative to `0.1.0a49`; the cache lifetime and that it is measured from the fetch; that every write clears everything; and that `list_items`'s own result cache retains a listing until the next write. [quickstart.md](./quickstart.md) is the source text. Any runnable example must pass `tests/docs/test_doc_examples.py`; tag illustrative fragments ` ```python notest `.
- [X] T040 [P] Add the `[Unreleased]` CHANGELOG entry in `CHANGELOG.md`: the two mechanisms (priming and read-through), the exact per-pattern figures with their provenance, the item residual stated as a bound, and the caching utility's new shape including the removal of the never-released module-level `prime()`. Every figure must be one a test in this repository reproduces, or carry its external provenance — R5's 150/177/103 on the consumer's own database is external and must say so (FR-014).
- [X] T041 Update `docs/python-api.md` and any docstring that describes `taxomesh.utils.memoize`, so `prime`/`cached`/`Miss` are documented and the removed module-level helper is not.
- [X] T042 Run the four quality gates in the 3.13 venv: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy --strict .`, `uv run pytest --cov=taxomesh --cov-fail-under=80`. All must pass; coverage at or above the baseline recorded in T001.
- [X] T043 Re-read [quickstart.md](./quickstart.md) and [contracts/memoize-cache.md](./contracts/memoize-cache.md) against the implementation and correct any statement that no longer matches.
- [X] T044 Run `/speckit.analyze` and fix until it returns zero deviations, re-running it after **every** fix, per the project workflow. Only then propose the PR.

---

## Dependencies

```
Phase 1 (T001 → T002)
   └── Phase 2 (T003,T004,T005,T006 → T007 → T008 → T009 → T010)   BLOCKS EVERYTHING
          ├── Phase 3 US1 (T011 → T012,T013,T014,T017 [P] → T015 → T016 → T018 → T019,T020 → T021)   ← MVP
          │      ├── Phase 4 US2 (T022 → T023 → T024)
          │      └── Phase 5 US3 (T025..T029 [P] → T030)
          ├── Phase 6 US5 (T031 → T032 → T033 → T034)
          └── Phase 7 US6 (T035,T036 [P] → T037 → T038)
                 └── Phase 8 (T039,T040 [P] → T041 → T042 → T043 → T044)
```

**Story independence**:

- **US5 is independent of US1–US3.** It asserts an *absence* and can be written and passing
  before priming exists — which is the point: it must fail if anyone ever adds item priming.
- **US6 depends only on Phase 2**, not on the service change at all.
- **US2 and US3 depend on US1** being implemented, since they constrain its behaviour.

## Parallel opportunities

- **T003 + T004 + T005 + T006** — four independent unit-test groups in the same new-shape file; write together, but land them before T007.
- **T012 + T013 + T014 + T017** — independent read-count tests, different fixtures.
- **T025 … T029** — five independent correctness tests.
- **T035 + T036** — decorated shapes and introspection, different concerns.
- **T039 + T040** — docs and changelog, different files.

## Implementation strategy

**MVP is Phase 2 + Phase 3.** That delivers the measured fix — the consumer-shaped walk
goes 177 → 103, and every category pattern lands at or below `0.1.0a49`. Phases 4–7 are the
guardrails that make it safe to ship: Phase 4 proves 060 is intact, Phase 5 proves
correctness on four backends, Phase 6 proves the expensive path stayed excluded, Phase 7
proves the consumer can take the release. None are optional before a release.

**Do not skip Phase 6.** T031 is the only thing standing between this feature and the
memory cost the spec rejected — an absent test would let a later contributor add item
priming as an "obvious symmetry" with no signal that it was considered and refused.

**Two things that will look like bugs and are not.** The consumer-shaped walk costs 103,
not 0 — the walk's own root is nobody's child, so nothing primes it. And three item
patterns cost *more* than `0.1.0a49` — that residual is FR-007's accepted price and is
asserted, not tolerated.
