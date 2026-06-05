# Implementation Plan: Repository-Level Filtered Lookups

**Branch**: `054-repo-filtered-lookups` | **Date**: 2026-06-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/054-repo-filtered-lookups/spec.md`

## Summary

Eliminate four full-table scans in `TaxomeshService` read paths (profiled at
~85% of cold detail-page render time in letrastango, ~7.3K items / ~14K links)
by pushing filtering down to the repository layer:

1. New port method `get_items_by_ids(item_ids, *, enabled=None) -> dict[UUID, Item]`
   — bulk item fetch by internal ID, mirroring 052's `get_items_by_external_ids`.
2. Keyword filters on the existing port method:
   `list_item_parent_links(*, item_id=None, category_ids=None)`.

Both are implemented in all four adapters (`JsonRepository`, `YAMLRepository`,
`DjangoRepository` with DB-side `.filter(...)`, and the `InMemoryRepository`
test fixture), and the four service call sites are rewired. **Zero observable
behavior change** — same results, ordering, exceptions, logging — enforced by
the existing 4-backend parametrized parity fixture plus new no-full-scan tests.

## Technical Context

**Language/Version**: Python 3.11 (targets 3.11–3.13)
**Primary Dependencies**: Pydantic v2 (domain models), Django ≥ 4.2 (optional adapter), pyyaml ≥ 6.0 — no new dependencies
**Storage**: JsonRepository (JSON file), YAMLRepository (YAML file), DjangoRepository (Django ORM), InMemoryRepository (test fixture)
**Testing**: pytest + pytest-django; existing 4-backend parametrized `service` fixture (`tests/service/conftest.py`) for parity
**Target Platform**: Library — any platform supporting Python 3.11+
**Project Type**: library (hexagonal: domain / ports / application / adapters)
**Performance Goals**: Repository work in the four read paths scales with matched records, not table size; no full `list_items()` / unfiltered `list_item_parent_links()` calls remain in those paths
**Constraints**: No observable behavior change (results, ordering, exceptions, log semantics); mypy --strict; ruff (line 119); coverage ≥ 80%; TDD
**Scale/Scope**: Consumer dataset ~7,300 items / ~14,000 item-parent links; change surface = 1 port file, 3 adapter files, 1 test fixture, 4 service call sites

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Hexagonal — dependency direction | ✅ PASS | Change flows port → adapters → service call sites; no inward-layer violation. No adapter defaults touched. |
| II. TaxomeshService single facade | ✅ PASS | No new public service API; internal call-site rewiring only. |
| III. Repository as Protocol | ✅ PASS | Port extended structurally on `TaxomeshRepositoryBase` (Protocol); adapters comply structurally, no inheritance. |
| IV. Pydantic + mypy --strict | ✅ PASS | No model changes; new signatures fully typed (`Collection[UUID]`, `dict[UUID, Item]`); no `Any`. |
| V. Exception hierarchy | ✅ PASS | New/extended methods raise `TaxomeshRepositoryError` on storage failure, like all repo ops. Missing-ID-silently-absent mirrors the established 052 bulk-lookup contract (a documented mapping contract, not a silent failure). |
| VI. DAG integrity | ✅ PASS | Read-only feature; no graph writes. |
| VII. Spec-driven | ✅ PASS | spec.md complete; this plan follows it. |
| VIII. Quality gates | ✅ PASS | ruff, ruff format, mypy --strict, pytest ≥ 80% all enforced in tasks. |
| IX. Framework-agnostic handlers | ✅ PASS | contrib/api untouched. |
| X. Named constants | ✅ PASS | No new magic literals introduced (filters pass caller-supplied IDs through). |
| XI. OO by default | ✅ PASS | All logic lives in existing repository classes / service methods. Shared filter logic factored as pure stateless helper only if duplication warrants (see research.md R5). |

**Post-Phase-1 re-check**: ✅ PASS — design artifacts introduce no violations.

## Project Structure

### Documentation (this feature)

```text
specs/054-repo-filtered-lookups/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── repository-port.md   # Port contract deltas
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
taxomesh/
├── ports/
│   └── repository.py                      # +get_items_by_ids; list_item_parent_links gains filters
├── application/
│   └── service.py                         # 4 call sites rewired:
│                                          #   ~510-519 list_items(category_id=...)      [site 4]
│                                          #   ~521-555 list_categories_by_item          [site 2]
│                                          #   ~1192-1226 list_related_items_for_sources [site 1]
│                                          #   ~1733-1770 _load_item_candidates          [site 3]
└── adapters/repositories/
    ├── json_repository.py                 # both methods
    ├── yaml_repository.py                 # both methods
    └── django_repository.py               # both methods — DB-side .filter(...)

tests/
└── service/
    ├── conftest.py                        # InMemoryRepository gains both methods
    ├── test_repo_filtered_lookups.py      # NEW: repo-level contract tests (4 backends)
    └── test_service_no_full_scan.py       # NEW: spy-repo tests — no full-table calls in the 4 paths

pyproject.toml                             # version 0.1.0a41 → 0.1.0a42
CHANGELOG.md                               # new entry
```

**Structure Decision**: Existing hexagonal layout; no new packages. New tests
live under `tests/service/` beside the 4-backend parametrized fixture they
reuse (same placement as 052's `test_service_bulk_external_id.py`).

## Behavior-Parity Pin-downs (from code inspection)

These are the subtle invariants each call-site rewrite MUST preserve
(details and rationale in [research.md](./research.md)):

- **Sites 1 & 3 fetch with `enabled=True`**: today both call
  `self._repo.list_items()` whose port default is `enabled=True`, so their
  item maps contain *only enabled items*. The replacement
  `get_items_by_ids(...)` calls MUST pass `enabled=True` — otherwise disabled
  relation targets would stop being treated as dangling (site 1) and disabled
  items would leak into recursive candidates (site 3).
- **Site 1 map must include source IDs**: the dangling-link WARNING renders
  the *source* item via `item_map.get(link.source_item_id)`; the bulk fetch
  is over `{source_item_id} ∪ {target_item_id}` of the matched links.
- **Site 4 keeps per-link `self.get_item(lnk.item_id)`**: a dangling link in
  the non-recursive path raises `TaxomeshItemNotFoundError` today; switching
  item resolution to a silent bulk map would change behavior. Only the link
  fetch changes.
- **Stable re-sort stays**: sites 2 and 4 apply
  `sorted(links, key=lambda l: l.sort_index)` over repo output; Python sort
  stability + the repo ordering contract make filtered results identical.
  Keep the `sorted()` calls as-is.
- **Site 3 dedup order**: first link wins per item, iterating links in repo
  order — preserved because filtering doesn't reorder.

## Complexity Tracking

No constitution violations — table not required.
