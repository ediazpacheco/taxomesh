# Tasks: YAML Repository

**Input**: Design documents from `/specs/007-yaml-repository/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**TDD**: Test tasks are REQUIRED by project constitution (CLAUDE.md §Testing Rules).
Every test task MUST run and fail before its paired implementation task.

---

## Phase 1: Setup

**Purpose**: Promote `pyyaml` to a required runtime dependency and add mypy stubs.

- [X] T001 Update `pyproject.toml`: move `pyyaml>=6.0` from `[project.optional-dependencies] yaml` to `[project.dependencies]`; add `types-PyYAML>=6.0` to `[project.optional-dependencies] dev`
- [X] T002 Run `uv add pyyaml` and `uv add --dev types-PyYAML` to update `uv.lock`

**Checkpoint**: `python -c "import yaml"` succeeds; `uv run mypy --strict taxomesh/` does not emit implicit-Any errors for yaml imports.

---

## Phase 2: Foundational

No shared domain types are introduced by this feature. The `TaxomeshRepositoryBase` protocol already exists in `taxomesh/ports/repository.py`. No foundational blocking tasks required — user stories may proceed after Phase 1.

---

## Phase 3: User Story 1 — YAMLRepository (Priority: P1) 🎯 MVP

**Goal**: A fully protocol-compliant `YAMLRepository` that stores all taxomesh domain objects in a YAML file on disk with atomic writes.

**Independent Test**: Instantiate `YAMLRepository` against a temp dir; call all 17 protocol methods; assert round-trip fidelity, error conditions, and atomic-write invariants — entirely without touching the CLI.

### Tests for User Story 1

> **Write these tests FIRST. All MUST fail before T004 is started.**

- [X] T003 [US1] Write failing tests for `YAMLRepository` in `tests/service/test_yaml_repository.py` covering all acceptance scenarios:
  - `test_init_creates_file_when_not_exists` — fresh temp dir → `taxomesh.yaml` created on disk
  - `test_init_loads_existing_valid_file` — save a category, reload repo, assert round-trip
  - `test_init_raises_on_directory_path` — path is an existing directory → `TaxomeshRepositoryError`
  - `test_init_raises_on_invalid_yaml` — file contains invalid YAML → `TaxomeshRepositoryError`
  - `test_init_empty_file_treated_as_empty_taxonomy` — empty file → no error, all lists empty
  - `test_init_missing_top_level_keys_treated_as_empty` — YAML with only `categories:` key → items/tags/links all empty
  - `test_init_creates_parent_directories` — given path `tmp/nested/deep/taxomesh.yaml` where `nested/deep/` does not exist, `YAMLRepository(path)` creates the directory tree and succeeds
  - `test_save_and_get_category` — save + get by id
  - `test_list_categories` — save two categories, list returns both
  - `test_delete_category_returns_true` — delete existing → True
  - `test_delete_category_missing_returns_false` — delete non-existent → False
  - `test_save_and_get_item` — save + get by id
  - `test_list_items` — save two items, list returns both
  - `test_delete_item_returns_true`
  - `test_delete_item_missing_returns_false`
  - `test_save_and_get_tag`
  - `test_list_tags`
  - `test_delete_tag_returns_true`
  - `test_delete_tag_missing_returns_false`
  - `test_assign_tag_links_tag_to_item`
  - `test_assign_tag_is_idempotent` — assign twice → only one link stored
  - `test_remove_tag_returns_true`
  - `test_remove_tag_missing_returns_false`
  - `test_save_category_parent_link_and_list`
  - `test_save_item_parent_link_upserts_sort_index` — save same (item, category) twice with different sort_index → only one link, updated sort_index
  - `test_list_item_parent_links`
  - `test_get_config_summary_returns_path_string` — non-empty, contains the configured path

### Implementation for User Story 1

- [X] T004 [US1] Implement `YAMLRepository` in `taxomesh/adapters/repositories/yaml_repository.py` (depends on T003 — tests must fail first):
  - Module docstring
  - `__init__(self, path: Path | str = Path("taxomesh.yaml")) -> None`: raise `TaxomeshRepositoryError` if path is a directory; if file exists call `_load()`; else create parent dirs + call `_flush()`
  - `_load(self) -> None`: `raw: Any = yaml.safe_load(...)`; raise `TaxomeshRepositoryError` if not a dict or parse fails; populate `self._categories`, `self._items`, `self._tags`, `self._links`, `self._category_parent_links`, `self._item_parent_links` using `Model.model_validate()`
  - `_flush(self) -> None`: `data = {all six keys}` via `model_dump(mode="json")`; write atomically via `tempfile.mkstemp` + `os.fsync` + `os.replace`; use `yaml.safe_dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)`
  - All 17 protocol methods matching `JsonRepository` semantics exactly; Google-style docstrings on all public methods
  - `save_item_parent_link` MUST upsert (update sort_index if (item_id, category_id) already exists)
  - `assign_tag` MUST be idempotent

**Checkpoint**: `pytest tests/service/test_yaml_repository.py -v` → all 27 tests pass.

---

## Phase 4: User Story 2 — CLI Default Change (Priority: P2)

**Goal**: The CLI `build()` factory defaults to `YAMLRepository`/`taxomesh.yaml` when no `taxomesh.toml` is present; `type = "yaml"` is accepted explicitly; `type = "json"` is preserved for backward compatibility.

**Independent Test**: Invoke CLI commands via `CliRunner` with no config / YAML config / JSON config; assert the correct repository type and path appear in verbose output; no real file I/O needed (mock `build` or use temp dirs).

### Tests for User Story 2

> **Write these tests FIRST. All MUST fail before T006 is started.**

- [X] T005 [US2] Append failing tests for the CLI default change to `tests/test_cli.py` covering:
  - `test_cli_default_repo_is_yaml` — no `taxomesh.toml` → verbose output contains `taxomesh.yaml`; exit code 0
  - `test_cli_toml_type_yaml_uses_yaml_path` — `[repository] type = "yaml" path = "data.yaml"` → verbose output contains `data.yaml`; exit code 0
  - `test_cli_toml_type_json_backward_compat` — `[repository] type = "json" path = "legacy.json"` → verbose output contains `legacy.json`; exit code 0
  - `test_cli_toml_type_unsupported_exits_nonzero` — `[repository] type = "csv"` → exit code 1, stderr contains descriptive error
  - `test_cli_leaves_json_untouched_when_yaml_is_default` — given `taxomesh.json` exists in the temp dir and no `taxomesh.toml` is present, invoke any CLI command, assert `taxomesh.json` content is unchanged and `taxomesh.yaml` is created (covers FR-013)
  - Use temp directories + `CliRunner(mix_stderr=False)` so that stdout/stderr are separable; do NOT patch `build` — use real file system via temp dirs to exercise the full config path

### Implementation for User Story 2

- [X] T006 [US2] Update `taxomesh/adapters/cli/config.py` (depends on T005 — tests must fail first):
  - Change `_DEFAULT_REPO_TYPE = "yaml"` (was `"json"`)
  - Change `_DEFAULT_REPO_PATH = "taxomesh.yaml"` (was `"taxomesh.json"`)
  - Add import: `from taxomesh.adapters.repositories.yaml_repository import YAMLRepository`
  - Replace the single `if repo_type != "json": sys.exit(1)` block with:
    ```python
    if repo_type == "yaml":
        repo = YAMLRepository(Path(repo_path))
    elif repo_type == "json":
        repo = JsonRepository(Path(repo_path))
    else:
        print(f"Error: unsupported repository type '{repo_type}'. Supported: 'yaml', 'json'.", file=sys.stderr)
        sys.exit(1)
    ```
  - Update Google-style docstring on `build()` to mention YAML as the new default

**Checkpoint**: `pytest tests/test_cli.py -k "yaml or json or repo" -v` → all new tests pass; existing CLI tests unaffected.

---

## Phase 5: User Story 3 — Example YAML Data File (Priority: P3)

**Goal**: `examples/taxomesh_example.yaml` ships in the repository with a rich, realistic taxonomy: ≥5 top-level categories, ≥1 four-level-deep chain, 2–3 items per category node; loads cleanly via `YAMLRepository`.

**Independent Test**: Load the file via `YAMLRepository`; feed to `TaxomeshService`; assert `get_graph()` returns ≥5 roots and ≥1 four-level-deep chain.

### Tests for User Story 3

> **Write these tests FIRST. They will fail until T008 creates the file.**

- [X] T007 [P] [US3] Write failing tests in `tests/test_example_yaml.py` covering:
  - All tests MUST resolve the file path as: `EXAMPLE = Path(__file__).parent.parent / "examples" / "taxomesh_example.yaml"` (absolute, works regardless of pytest invocation directory)
  - `test_example_file_exists` — `EXAMPLE.exists()` is True
  - `test_example_file_loads_without_error` — `YAMLRepository(EXAMPLE)` does not raise
  - `test_example_file_has_at_least_six_categories` — `list_categories()` returns ≥ 6 (root + 5 top-level)
  - `test_example_file_graph_has_at_least_five_roots` — `service.get_graph().roots` has ≥ 5 nodes
  - `test_example_file_graph_has_four_level_deep_chain` — at least one root node has a chain of depth ≥ 4 (helper: `max_depth(node)` recurses into `children`)

### Implementation for User Story 3

- [X] T008 [US3] Create `examples/taxomesh_example.yaml` (depends on T007 — tests must fail first):
  - Valid YAML loadable by `YAMLRepository` using the schema from `data-model.md`
  - Top-level categories (all children of `__root__`):
    1. **Animals** → children: Mammals, Birds, Reptiles
       - Mammals → children: Carnivores, Herbivores
         - Carnivores → children: BigCats ← 4-level depth satisfied here
    2. **Plants** → children: Trees, Flowers
    3. **Vehicles** → children: Land, Air, Water
    4. **Music** → children: Classical, Jazz, Rock
    5. **Literature** → children: Fiction, NonFiction
  - 2–3 items per leaf/branch category, each with unique UUID `item_id`, readable `external_id`, `enabled: true` or `false`
  - All UUIDs hand-written as valid UUID4 strings (no Python-specific tags)
  - All `category_parent_links` and `item_parent_links` entries present with `sort_index` values
  - Root category (`__root__`) present in `categories` with reserved name

**Checkpoint**: `pytest tests/test_example_yaml.py -v` → all 5 tests pass.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T009 Update `README.md`: new default storage format (YAML), how to configure `taxomesh.toml` for `type = "yaml"` vs `type = "json"`, path to example file (`examples/taxomesh_example.yaml`), pyyaml as required dep (no extras install needed), note that `TaxomeshService()` direct API still defaults to `JsonRepository`
- [X] T010 Run full quality gates and confirm all pass:
  - `ruff check .`
  - `ruff format --check .`
  - `mypy --strict .`
  - `pytest --cov=taxomesh --cov-fail-under=80`

**Checkpoint**: All four gates green; PR is ready.

---

## Dependencies & Execution Order

### Phase Dependencies

```
T001 → T002 (Setup: dep promotion + lockfile)
  └── T003 (US1 tests: write failing) ──→ T004 (US1 impl: YAMLRepository)
        └── T005 (US2 tests: write failing) ──→ T006 (US2 impl: CLI config)
  └── T007 [P] (US3 tests: write failing) ──→ T008 (US3 impl: example file)
        └── T009, T010 (Polish)
```

- **T001–T002**: No dependencies — start immediately
- **T003**: Depends on T002 (pyyaml importable); must fail before T004
- **T004**: Depends on T003 (tests failing)
- **T005**: Depends on T004 (CLI tests exercise `YAMLRepository` via `build()`)
- **T006**: Depends on T005 (tests failing)
- **T007**: Can start in parallel with T003 after T002 (different file, no shared writes)
- **T008**: Depends on T007 (tests failing)
- **T009, T010**: Depend on T006 + T008

### Parallel Opportunities

- T003 and T007 can be written in parallel after T002 (different test files, no shared writes)
- T009 (README) can begin in parallel with T010 (quality gates) after T008

---

## Parallel Example: Write Both Test Files Together

```
After T002 completes:
  Task A: T003 — Write tests/service/test_yaml_repository.py (US1 tests)
  Task B: T007 — Write tests/test_example_yaml.py (US3 tests)
  → Both can run simultaneously (different files)
```

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. T001 — Update pyproject.toml
2. T002 — Sync lockfile
3. T003 — Write failing YAMLRepository tests
4. T004 — Implement YAMLRepository
5. **STOP and VALIDATE**: `pytest tests/service/test_yaml_repository.py -v` → all pass
6. Library users can now pass `YAMLRepository` directly to `TaxomeshService`

### Full Delivery

5. T005 — Write failing CLI tests
6. T006 — Update CLI config default
7. T007 — Write failing example file tests
8. T008 — Create example YAML file
9. T009, T010 — Polish + quality gates
10. Open PR

---

## Notes

- `[P]` = parallelizable (different files, no dependency on incomplete sibling)
- `[US1]` / `[US2]` / `[US3]` = traceability to spec user story
- TDD is mandatory — tests must FAIL before implementation starts
- `tests/service/test_yaml_repository.py` mirrors the pattern in `tests/service/test_json_repository.py`
- `tests/test_example_yaml.py` uses `Path(__file__).parent.parent / "examples" / "taxomesh_example.yaml"` for path resolution
- The `examples/` directory is source-only — hatchling excludes it from the wheel by default (no `pyproject.toml` changes needed)
- Existing CLI tests (those that mock `build`) are unaffected by the T006 default change
