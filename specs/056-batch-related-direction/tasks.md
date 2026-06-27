# Tasks: Direction-Aware Batched Related-Items Traversal

**Feature**: `056-batch-related-direction`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Contracts**: [contracts/service_and_repository.md](./contracts/service_and_repository.md)

**TDD is mandatory** (project rule): every implementation task is preceded by a
failing test task. No task is done until its `pytest` target passes.

> **Post-review amendment.** After the initial implementation, two optimizations
> were folded in (tasks below describe the original approach; the shipped code
> reflects the amendment):
> - The two batched link queries (`..._for_sources` / planned `..._for_targets`)
>   were **unified** into one `list_item_relation_links_for_items(ids, *,
>   direction, relation_types)` across the Protocol and all adapters.
> - `direction="both"` now uses a **single combined** `source OR target` query →
>   **two** repository calls total (not three). The anti-N+1 guards assert one
>   unified link query + one bulk lookup, with a Django `CaptureQueriesContext`
>   test pinning the single combined SQL query for `both`.
> - Added Django index `taxomesh_rl_tgt_type_sort_idx` (migration `0010`) for the
>   incoming/both `ORDER BY`. Backward compatibility was waived by the user.

## Conventions

- Generalized service method:
  `TaxomeshService.list_related_items_for_sources(..., direction: Literal["outgoing","incoming","both"] = "outgoing")`
  in `taxomesh/application/service.py`.
- New repository Protocol method: `list_item_relation_links_for_targets(target_item_ids, *, relation_types=None)`,
  mirror of `list_item_relation_links_for_sources`.
- Backends to keep in lockstep: `JsonRepository`, `YAMLRepository`,
  `DjangoRepository`, and the in-memory test repository in
  `tests/service/conftest.py`.

---

## Phase 1: Setup

- [X] T001 Confirm baseline is green before any change: run `ruff check .`, `ruff format --check .`, `mypy --strict .`, and `pytest tests/service/test_service_item_relations.py tests/service/test_service_no_full_scan.py tests/service/test_service_cache.py tests/service/test_service_list_related_resilience.py` from repo root; record that all pass.

---

## Phase 2: Foundational — batched incoming-link repository query (blocks US1 and US3)

**Goal**: Add `list_item_relation_links_for_targets` so the incoming/both service
paths can stay at two/three repository calls. US2 (outgoing) does not depend on
this phase.

- [X] T002 [P] Add repo-level tests for `list_item_relation_links_for_targets` to `tests/service/test_yaml_repository_relations.py` (mirror the existing `list_item_relation_links_for_sources` cases): returns incoming links for many targets, empty input returns `[]`, `relation_types` allow-list filtering, deterministic order `(target_item_id, relation_type, sort_index, source_item_id)`. Tests must fail (method absent).
- [X] T003 Add `list_item_relation_links_for_targets(self, target_item_ids: Collection[UUID], *, relation_types: Collection[str] | None = None) -> list[ItemRelationLink]` to the `TaxomeshRepositoryBase` Protocol in `taxomesh/ports/repository.py`, with a house-style docstring mirroring `list_item_relation_links_for_sources` (incoming semantics, deterministic order, empty-input behavior).
- [X] T004 [P] Implement `list_item_relation_links_for_targets` in `taxomesh/adapters/repositories/json_repository.py` — filter `target_item_id in target_set`, sort by `(str(target_item_id), relation_type, sort_index, str(source_item_id))`, empty input → `[]`.
- [X] T005 [P] Implement `list_item_relation_links_for_targets` in `taxomesh/adapters/repositories/yaml_repository.py` (same shape as JSON adapter).
- [X] T006 [P] Implement `list_item_relation_links_for_targets` in `taxomesh/adapters/repositories/django_repository.py` — `.filter(target_item_id__in=target_list)`, `.order_by("target_item_id", "relation_type", "sort_index", "source_item_id")`, empty input → `[]`, wrap `DatabaseError` in `TaxomeshRepositoryError`.
- [X] T007 [P] Implement `list_item_relation_links_for_targets` in the in-memory repository in `tests/service/conftest.py` (same shape as JSON adapter).
- [X] T008 Run T002 repo tests and `mypy --strict .`; confirm the new method is green across adapters and Protocol-conformant.

**Checkpoint**: All adapters expose a batched incoming-link query; behavioral
and type checks pass.

---

## Phase 3: User Story 1 — Batched incoming relations without N+1 (P1)

**Goal**: `list_related_items_for_sources(..., direction="incoming")` resolves
incoming related items in exactly two repository calls, grouped like the outgoing
result.

**Independent test**: incoming call over many ids returns the correct grouped
dict and makes exactly two repository calls regardless of input size.

- [X] T009 [P] [US1] Add incoming behavioral tests to `tests/service/test_service_item_relations.py` (parametrized over all backends): grouped dict keyed by queried id → relation_type → source-side items; empty input → `{}`; queried item with no incoming links absent; dedup/reorder of input ids; `relation_types` filtering + case-insensitivity (`["COVERS"]`); deterministic order `(sort_index, source_item_id)`. Tests must fail (no `direction` param yet).
- [X] T010 [P] [US1] Add anti-N+1 query-count guard for incoming to `tests/service/test_service_no_full_scan.py` using `RecordingRepository`: with `direction="incoming"`, assert no `list_items` call, exactly one `get_items_by_ids` call with `enabled=True`, and exactly one `list_item_relation_links_for_targets` call — and that the count does not grow when more source ids are passed.
- [X] T011 [P] [US1] Add incoming resilience tests to `tests/service/test_service_list_related_resilience.py`: dangling/disabled source-side item skipped with one WARNING under `skip_on_error=True`; `skip_on_error=False` raises `TaxomeshItemNotFoundError`; empty input emits no warning. Mirror the outgoing message-shape assertions.
- [X] T012 [US1] Generalize `list_related_items_for_sources` in `taxomesh/application/service.py`: add keyword-only `direction: Literal["outgoing","incoming","both"] = "outgoing"`; thread it (validated) into the memoized `_fetch_related_items_for_sources` cache key; in the private impl select the link query and grouping/related-id endpoints by direction (`incoming` → `list_item_relation_links_for_targets`, group by `target_item_id`, related id = `source_item_id`). Keep the single `get_items_by_ids(needed_ids, enabled=True)` bulk lookup and the existing skip_on_error/warning logic unchanged.
- [X] T013 [US1] Run T009–T011 plus the existing outgoing suite and `mypy --strict .`; confirm incoming behavior, anti-N+1, and resilience pass and nothing regressed.

**Checkpoint**: Incoming batched traversal works end-to-end with the two-call
guarantee; outgoing remains green.

---

## Phase 4: User Story 2 — Default outgoing behavior preserved (P1)

**Goal**: Existing outgoing callers and tests behave identically; `direction`
defaults to `outgoing`.

**Independent test**: calling the method with no `direction` argument yields the
pre-feature outgoing result, grouping, ordering, caching, and errors.

- [X] T014 [P] [US2] Add an explicit default-equivalence test to `tests/service/test_service_item_relations.py`: a call with no `direction` argument and the same call with `direction="outgoing"` produce identical results; assert the outgoing two-call bound is unchanged.
- [X] T015 [US2] Run the full pre-existing outgoing suite (`test_service_item_relations.py`, `test_service_no_full_scan.py`, `test_service_cache.py`, `test_service_list_related_resilience.py`, `test_logging.py`) and confirm 100% pass with no edits to their existing assertions (regression gate for SC-003).

**Checkpoint**: Backward compatibility proven.

---

## Phase 5: User Story 3 — Both-direction batched relations (P2)

**Goal**: `direction="both"` returns the union of outgoing and incoming related
items, grouped per queried id and relation type, in three bounded repository
calls.

**Independent test**: both-direction call over items with links on each side
merges both halves under the queried id; repository calls = three and constant.

- [X] T016 [P] [US3] Add both-direction behavioral tests to `tests/service/test_service_item_relations.py` (parametrized backends): an item with outgoing and incoming links of a relation type yields both target-side and source-side related items under that id; documented union order (outgoing-derived first, then incoming-derived); relation_types filtering and empty input behave as for the other directions.
- [X] T017 [P] [US3] Add both-direction anti-N+1 guard to `tests/service/test_service_no_full_scan.py`: with `direction="both"`, assert exactly one `list_item_relation_links_for_sources`, one `list_item_relation_links_for_targets`, and one `get_items_by_ids` (three total), constant as input ids grow.
- [X] T018 [P] [US3] Add both-direction cache-key independence test to `tests/service/test_service_cache.py`: `outgoing`, `incoming`, and `both` for the same ids are independent cache entries; a write invalidates all; identical repeated `both` calls hit the repo once.
- [X] T019 [US3] Extend the private impl in `taxomesh/application/service.py` for `direction="both"`: issue both batched link queries, group each matched link under whichever endpoint is in the queried-id set with the other endpoint as the related id, union per `(queried_id, relation_type)` with outgoing-derived items first then incoming-derived; single bulk `get_items_by_ids(..., enabled=True)` over all referenced endpoints.
- [X] T020 [US3] Run T016–T018 and `mypy --strict .`; confirm both-direction behavior, three-call bound, and cache independence pass.

**Checkpoint**: All three directions complete and behaviorally symmetric.

---

## Phase 6: Polish, Docs & Release

- [X] T021 Update the `list_related_items_for_sources` docstring in `taxomesh/application/service.py` (house style): document the `direction` parameter, per-direction repository-call bounds (2 / 2 / 3), the N+1 rationale, the union-order rule for `both`, and clarify that `source_item_ids` are the queried ids interpreted per direction. Add/extend the `Example::` block to show an incoming result.
- [X] T022 [P] Update `README.md` if it documents the batched method, adding the `direction` parameter and incoming/both usage (per project rule: README updates after analyze passes — stage but confirm timing).
- [X] T023 [P] Add a `CHANGELOG.md` entry under a new `## [0.1.0a46] — 2026-06-27` section describing the direction-aware batched traversal and the new repository method.
- [X] T024 Bump the version `0.1.0a45 → 0.1.0a46` in `pyproject.toml` and keep `taxomesh/__init__.py` `__version__` in sync.
- [X] T025 Run the full quality gates from repo root: `ruff check .`, `ruff format --check .`, `mypy --strict .`, `pytest --cov=taxomesh --cov-fail-under=80`; confirm all pass.

---

## Dependencies & Execution Order

- **Phase 1 (Setup)** → **Phase 2 (Foundational)** must complete before US1/US3.
- **US1 (Phase 3)** introduces the `direction` parameter and depends on Phase 2.
- **US2 (Phase 4)** is a regression gate; runs after US1 wires the default.
- **US3 (Phase 5)** depends on Phase 2 (incoming query) and US1's direction
  dispatch in the service method.
- **Phase 6** runs last (docs + release + full gates).

### Story dependency notes

- US2 is verification-only; it adds no production code beyond what US1's default
  provides, so it cannot regress independently of US1.
- US1 and US3 share the same service method; US3 extends the dispatch US1 adds.

## Parallel Execution Examples

- Phase 2 adapters: T004, T005, T006, T007 are `[P]` (different files) after the
  Protocol method T003 lands.
- US1 tests: T009, T010, T011 are `[P]` (different test files) and can be written
  together before T012.
- US3 tests: T016, T017, T018 are `[P]` before T019.
- Polish: T022 and T023 are `[P]` (different files).

## Implementation Strategy

- **MVP = Phase 1 + Phase 2 + US1**: closes the stated incoming N+1 gap. Shippable
  on its own with default outgoing untouched.
- **Increment 2 = US2**: locks backward-compatibility proof.
- **Increment 3 = US3**: adds `both`.
- **Release = Phase 6**: docs, changelog, version, full gates.

## Format Validation

All tasks use `- [ ] Tnnn [P?] [US?] description + file path`. Setup,
Foundational, and Polish tasks carry no story label; US1/US2/US3 tasks carry
their label.
