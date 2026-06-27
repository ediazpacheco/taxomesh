# Implementation Plan: Direction-Aware Batched Related-Items Traversal

**Branch**: `056-batch-related-direction` | **Date**: 2026-06-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/056-batch-related-direction/spec.md`

> **Post-review amendment (supersedes parts of the Design Notes below).** Two
> follow-on optimizations were folded into this feature:
> 1. The repository layer is **unified** into one direction-aware method
>    `list_item_relation_links_for_items(item_ids, *, direction, relation_types)`,
>    replacing the prior `..._for_sources` (and the planned `..._for_targets`).
> 2. `direction="both"` resolves in **two** repository calls, not three — a single
>    combined `Q(source__in) | Q(target__in)` query plus the bulk lookup. The
>    service sorts the derived entries to preserve the outgoing-first union order.
> 3. A Django composite index `taxomesh_rl_tgt_type_sort_idx` (migration `0010`)
>    mirrors the outgoing index so the incoming/both `ORDER BY` is index-backed.
>    Backward compatibility was explicitly waived by the user.

## Summary

Generalize the shipped batched outgoing traversal
`TaxomeshService.list_related_items_for_sources` with a
`direction: Literal["outgoing", "incoming", "both"] = "outgoing"` parameter so the
single primitive resolves outgoing, incoming, and union related items for many
items in a bounded, input-size-independent number of repository calls. This
closes the N+1 gap for the incoming direction (callers currently loop the
single-item `list_related_items` / `list_item_relations` with
`direction="incoming"`).

Technical approach: add a batched **incoming**-link repository query
`list_item_relation_links_for_targets` (mirror of the existing
`list_item_relation_links_for_sources`) to the `TaxomeshRepositoryBase`
Protocol and every adapter, then teach the service's memoized private
implementation to select the link query (and the grouping key) by direction.
`outgoing` and `incoming` each cost two repository calls (one link query + one
bulk item lookup); `both` costs three (both link queries + one bulk lookup).
Default `outgoing` preserves current behavior, signature compatibility, cache
keys, and all existing tests.

## Technical Context

**Language/Version**: Python 3.11 (targets 3.11–3.13)
**Primary Dependencies**: Pydantic v2 (domain models); Django ≥ 4.2 (optional adapter); pyyaml ≥ 6.0; existing `taxomesh/utils/memoize.py` TTL cache
**Storage**: JsonRepository (JSON file), YAMLRepository (YAML file), DjangoRepository (Django ORM), InMemoryRepository (test fixture in `tests/service/conftest.py`)
**Testing**: pytest (parametrized across in_memory / json / yaml / django backends), spy `RecordingRepository` for query-count guards
**Target Platform**: Library (importable Python package)
**Project Type**: Single library (hexagonal: domain / ports / application / adapters)
**Performance Goals**: Bounded repository calls per batched call — 2 for outgoing/incoming, 3 for both — constant w.r.t. number of input ids (anti-N+1)
**Constraints**: Full backward compatibility (default `direction="outgoing"` identical to current behavior); domain-agnostic; mypy --strict; ruff; ≥80% coverage; line length 119
**Scale/Scope**: One new repository Protocol method + 4 adapter implementations; one generalized service method (public wrapper + memoized private impl); tests; docstring + CHANGELOG + version bump

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Hexagonal architecture**: ✅ Change flows adapters → application → domain only. New repository method is declared in `ports/repository.py` (Protocol) and implemented in adapters; the service depends only on the port. No inward violations. No new composition-root imports.
- **II. Single facade**: ✅ Only `TaxomeshService.list_related_items_for_sources` changes signature (adds a defaulted keyword); no new public class.
- **III. Repository as Protocol**: ✅ New method added to the `TaxomeshRepositoryBase` Protocol; structurally implemented by all adapters and the in-memory test repo. `Base` suffix preserved.
- **IV. Pydantic models + mypy strict**: ✅ No model changes. `direction` typed as `Literal["outgoing", "incoming", "both"]`, matching the single-item methods. No `Any`.
- **V. Exception hierarchy**: ✅ Reuses `TaxomeshItemNotFoundError` for the missing-item case in every direction; no new exceptions, no silent failures.
- **VI. DAG integrity**: ✅ Not applicable — item relations are a separate property graph, not the category DAG; no cycle logic touched.
- **VII. Spec-driven**: ✅ This plan follows `spec.md`; full speckit workflow in use.
- **VIII. Quality gates**: ✅ ruff + mypy --strict + pytest ≥80% will run before commit.
- **IX. Framework-agnostic handlers**: ✅ No HTTP/contrib.api changes in scope.
- **X. Named constants**: ✅ No new magic literals. Direction string values live only in the `Literal` type and the existing single-item methods' contract; reuse the same values. (No new `Final` constants required; the `Literal` is the single source of truth, consistent with how `list_item_relations` already declares it.)
- **XI. Object-oriented by default**: ✅ Logic stays in `TaxomeshService` and the repository adapter classes; no new module-level state.

**Result**: PASS — no violations, no Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/056-batch-related-direction/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (method + repository contracts)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
taxomesh/
├── ports/
│   └── repository.py                       # ADD list_item_relation_links_for_targets to Protocol
├── application/
│   └── service.py                          # GENERALIZE list_related_items_for_sources + memoized _fetch_*
└── adapters/repositories/
    ├── json_repository.py                  # ADD list_item_relation_links_for_targets
    ├── yaml_repository.py                   # ADD list_item_relation_links_for_targets
    └── django_repository.py                 # ADD list_item_relation_links_for_targets (ORM target_item_id__in)

tests/service/
├── conftest.py                              # ADD list_item_relation_links_for_targets to InMemoryRepository
├── test_service_item_relations.py           # ADD incoming/both behavioral cases (parametrized backends)
├── test_service_no_full_scan.py             # ADD incoming/both query-count (anti-N+1) guards
├── test_service_cache.py                    # ADD direction cache-key independence cases
├── test_service_list_related_resilience.py  # ADD incoming/both skip_on_error + dangling cases
├── test_yaml_repository_relations.py         # ADD repo-level for_targets coverage (mirror for_sources)
└── (json/django repo relation tests as present)  # mirror for_targets coverage

CHANGELOG.md                                 # ADD 0.1.0a46 entry
pyproject.toml + taxomesh/__init__.py        # version bump 0.1.0a45 → 0.1.0a46
README.md                                    # update batched-method description if present
```

**Structure Decision**: Single hexagonal library; the change spans the port
(Protocol), the application service, and all repository adapters, with the
in-memory test repository in `tests/service/conftest.py` kept in lockstep.

## Design Notes

### Repository layer — new batched incoming-link query

Add to the `TaxomeshRepositoryBase` Protocol and every adapter, mirroring
`list_item_relation_links_for_sources` exactly but keyed on the target side:

```python
def list_item_relation_links_for_targets(
    self,
    target_item_ids: Collection[UUID],
    *,
    relation_types: Collection[str] | None = None,
) -> list[ItemRelationLink]:
```

- Filter: `target_item_id in target_set` (Django: `.filter(target_item_id__in=...)`).
- Deterministic order: `(target_item_id, relation_type, sort_index, source_item_id)`
  — the symmetric counterpart of the outgoing order
  `(source_item_id, relation_type, sort_index, target_item_id)`.
- Empty input → `[]`; optional `relation_types` allow-list; flat list return.
- In-memory adapters (Json/YAML/InMemory) reuse the same list-comprehension +
  `sorted(...)` shape as the outgoing method.

### Application layer — direction generalization

`list_related_items_for_sources` public wrapper gains
`direction: Literal["outgoing", "incoming", "both"] = "outgoing"`, validates/passes
it through to the memoized `_fetch_related_items_for_sources` (added to its cache
key so each direction is an independent entry). The memoized impl:

1. **Select link query by direction**
   - `outgoing`: `list_item_relation_links_for_sources(ids, ...)`; grouping key =
     `source_item_id`; related id = `target_item_id`.
   - `incoming`: `list_item_relation_links_for_targets(ids, ...)`; grouping key =
     `target_item_id`; related id = `source_item_id`.
   - `both`: call **both** queries; for each link the grouping key is whichever
     endpoint is in the queried-id set and the related id is the other endpoint.
     (An item that is both source and target of the same link cannot occur —
     self-relations are rejected by the domain model.)
2. **One bulk item lookup**: `get_items_by_ids(needed_ids, enabled=True)` over the
   union of all endpoint ids referenced by the matched links — unchanged.
3. **Group + skip_on_error + warning** logic unchanged; the only differences are
   which id is the dict key and which is the materialized related item.

This keeps the two-call guarantee for outgoing/incoming and a bounded three-call
cost for both. The method name and `source_item_ids` parameter name are retained
for backward compatibility; the docstring clarifies that the ids are the
*queried* items, interpreted per `direction`.

### Ordering for `both`

Within a `{queried_id: {relation_type: [...]}}` group, outgoing-derived and
incoming-derived related items are concatenated deterministically: outgoing
results first (in their `(sort_index, target_item_id)` order), then incoming
results (in their `(sort_index, source_item_id)` order). This is documented in
the docstring and asserted in tests, so the union order is stable and
reproducible.

## Complexity Tracking

> No constitution violations. No entries required.
