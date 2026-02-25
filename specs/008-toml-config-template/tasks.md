# Tasks: taxomesh.toml Configuration Template

**Input**: Design documents from `/specs/008-toml-config-template/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: TDD — test tasks precede each implementation task (per project constitution).

**Organization**: Tasks are grouped by user story. All tasks complete.

---

## Phase 1: Setup

No project initialization required — no new dependencies, no scaffolding.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Exception class and exports that all user stories depend on.

- [X] T001 [P] Add `TaxomeshConfigError(TaxomeshError)` to `taxomesh/exceptions.py`
- [X] T002 [P] Export `TaxomeshConfigError` from `taxomesh/__init__.py`
- [X] T003 Amend `.specify/memory/constitution.md`: extend composition-root exception in Principle I; update Principle II default; add `TaxomeshConfigError` to hierarchy in Principle V; bump version 1.2.2 → 1.2.3 (note: final constitution version is 1.2.4 — see T015)

**Checkpoint**: `TaxomeshConfigError` importable from public API — US1, US2, US3 may proceed.

---

## Phase 3: User Story 1 — Developer Discovers and Uses the Config Template (Priority: P1) 🎯 MVP

**Goal**: Create `taxomesh.toml.example` — a self-documenting TOML template at the repo root.

**Independent Test**:
1. `taxomesh.toml.example` exists at the repository root.
2. It contains a header comment, the `[repository]` section with `type` and `path` keys with inline comments, an uncommented YAML example, and a fully commented-out JSON alternative.
3. Copy to a temp dir as `taxomesh.toml`, change `path`, run `taxomesh category list` — CLI uses the new path.

### Implementation for User Story 1

- [X] T004 [US1] Create `taxomesh.toml.example` at repository root with header comment block, `[repository]` section documenting `type` (accepted: `"yaml"` | `"json"`; default: `"yaml"`) and `path` (default type-specific: `"data/taxomesh.yaml"` / `"data/taxomesh.json"`; resolved from CWD), an uncommented YAML backend example, and a fully commented-out JSON backend alternative block in `taxomesh.toml.example`
- [X] T005 [US1] Fix JSON backend wording in `taxomesh.toml.example`: replace "backward-compatible" with neutral "alternative option" in `taxomesh.toml.example`

**Checkpoint**: `taxomesh.toml.example` exists at repo root and is fully self-documenting. SC-001 and SC-002 satisfied.

---

## Phase 4: User Story 2 — README Points to the Config Template (Priority: P2)

**Goal**: Add a top-level `## Configuration` section to `README.md`; reference `taxomesh.toml.example`; simplify `## CLI` config sub-section to a one-line mention.

**Independent Test**:
1. `README.md` has a top-level `## Configuration` section before `## CLI`.
2. Section includes Python API usage and reference to `taxomesh.toml.example`.
3. `## CLI` has only a one-line mention of `--config`.
4. "backward-compatible" wording is absent from README.

### Implementation for User Story 2

- [X] T006 [US2] Restructure `README.md`: add top-level `## Configuration` section (before `## CLI`) with Python API usage examples (`TaxomeshService()`, `TaxomeshService(config_path=…)`); simplify `## CLI` to one-line `--config` mention; reference `taxomesh.toml.example` for full key reference in `README.md`
- [X] T007 [US2] Fix "backward-compatible" wording in `README.md` TOML code blocks and architecture diagram — replace with neutral "alternative option" in `README.md`

**Checkpoint**: README satisfies FR-006, FR-007, FR-013, SC-003. Existing TOML blocks unchanged.

---

## Phase 5: User Story 3 — Python API Users Configure via taxomesh.toml (Priority: P3)

**Goal**: Make `TaxomeshService` config-aware — auto-discovers `taxomesh.toml` from CWD, accepts
`config_path`, exposes `repository` property, raises `TaxomeshConfigError` for all config failures
(invalid TOML, unsupported type, and OS read errors — all chained).

**Independent Test**:
```python
# No config → YAMLRepository fallback
svc = TaxomeshService(); assert type(svc.repository).__name__ == "YAMLRepository"

# Explicit YAML config_path → YAMLRepository
svc = TaxomeshService(config_path="taxomesh.toml.example")
assert type(svc.repository).__name__ == "YAMLRepository"

# Explicit repository → bypasses config
from taxomesh.adapters.repositories.json_repository import JsonRepository
from pathlib import Path
repo = JsonRepository(Path("x.json"))
svc = TaxomeshService(repository=repo)
assert svc.repository is repo
```

### Tests first (TDD)

- [X] T008 [US3] Write failing tests for `TaxomeshService(config_path=…)` in `tests/service/test_service_config.py` covering: auto-discovery, explicit YAML/JSON path, str config_path, config_path overrides CWD discovery, repository bypass, `TaxomeshConfigError` for invalid TOML and unsupported type, nonexistent config_path fallback, `repository` property returns active backend, `repository` property returns injected repo
- [X] T009 [US3] Add failing test for OS-level read error (`PermissionError`) on config file raising `TaxomeshConfigError` with chaining in `tests/service/test_service_config.py` (FR-011 — OSError wrapping gap)

### Implementation

- [X] T010 [US3] Extend `TaxomeshService.__init__` with `config_path: Path | str | None = None` (keyword-only); add `repository` property; add `_build_repo_from_config()` static method; all adapter imports inside `if repository is None:` guard in `taxomesh/application/service.py`
- [X] T011 [US3] Fix OSError wrapping gap in `taxomesh/application/service.py`: wrap `read_text()` call in `try/except OSError as exc` and re-raise as `TaxomeshConfigError(…) from exc` to satisfy FR-011 (currently only `tomllib.TOMLDecodeError` is caught)
- [X] T012 [US3] Simplify `build()` in `taxomesh/adapters/cli/config.py`: remove TOML-parsing and repo-construction logic; delegate to `TaxomeshService(config_path=resolved)`; use `svc.repository` for `BuildResult.repository`
- [X] T013 [US3] Update `tests/test_cli.py` to reflect simplified `build()`: adjust assertions that relied on CLI defaulting to YAML when no config file is present
- [X] T015 [US3] Add `DEFAULT_YAML_PATH: Final[Path]` constant to `taxomesh/adapters/repositories/yaml_repository.py`; add `DEFAULT_JSON_PATH: Final[Path]` constant to `taxomesh/adapters/repositories/json_repository.py`; remove any `_DEFAULT_YAML_PATH` / `_DEFAULT_JSON_PATH` from `taxomesh/application/service.py`; update `service.py` to call `YAMLRepository()` / `JsonRepository()` with no path argument when config omits `path`; add `Final[str]` annotation to `_CONFIG_FILENAME` in `taxomesh/adapters/cli/config.py`; amend constitution Principle I with "adapter defaults stay in adapters" clause and bump version 1.2.3 → 1.2.4 (FR-014)

**Checkpoint**: FR-008 through FR-014 all satisfied. SC-005 satisfied. All US3 tests pass.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final quality gate run after all implementation changes are complete.

- [X] T014 Run all quality gates confirming zero regressions: `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy --strict .` + `uv run pytest --cov=taxomesh --cov-fail-under=80 -q`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: N/A
- **Foundational (Phase 2)**: No dependencies — can start immediately; BLOCKS US3 (needs `TaxomeshConfigError`)
- **User Story 1 (Phase 3)**: Independent — no prerequisites
- **User Story 2 (Phase 4)**: Logically follows US1 (README references the file US1 creates); different files so technically parallel
- **User Story 3 (Phase 5)**: Requires Foundational (T001–T002) to be complete
- **Polish (Phase 6)**: Requires all user stories to be complete

### User Story Dependencies

- **US1 (P1)**: Independent — no prerequisites
- **US2 (P2)**: Logically follows US1 (README references `taxomesh.toml.example`); independently deliverable
- **US3 (P3)**: Requires Foundational phase (`TaxomeshConfigError` must exist before tests can be written)

### Parallel Opportunities

- T001 and T002 (Foundational) can run in parallel — different files
- T004 and T005 (US1) are sequential (wording fix follows file creation)
- T006 and T007 (US2) are sequential (fix wording after restructuring)
- T009 (test) must precede T011 (implementation fix) — TDD order
- T014 (quality gates) must run last

---

## Implementation Strategy

### Delivered

| Phase | Tasks | Status |
|-------|-------|--------|
| Foundational | T001–T003 | ✅ Complete |
| US1 — template file | T004–T005 | ✅ Complete |
| US2 — README | T006–T007 | ✅ Complete |
| US3 — service tests | T008–T009 | ✅ Complete |
| US3 — service impl | T010–T013 | ✅ Complete |
| US3 — FR-014 (adapter defaults) | T015 | ✅ Complete |
| Quality gates | T014 | ✅ Complete |

---

## Notes

- [P] marker indicates tasks that touch different files and have no inter-dependencies
- [Story] label maps task to specific user story for traceability
- TDD is mandatory per project constitution — T009 must fail before T011 is written
- Commit after T011 passes tests; then commit after T014 (quality gates)
- T009 and T011 together close the only outstanding spec gap (FR-011)
