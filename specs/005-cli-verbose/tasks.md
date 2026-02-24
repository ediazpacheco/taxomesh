# Tasks: CLI Verbose Mode & List Enhancements

**Input**: Design documents from `/specs/005-cli-verbose/`
**Branch**: `005-cli-verbose`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅

**Tests**: Included — FR-013 explicitly requires extending `tests/test_cli.py`. Per project TDD rule, test tasks come before their implementation tasks.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no blocking dependency)
- **[US#]**: Which user story (from spec.md)

---

## Phase 1: Setup

No new infrastructure needed. All changes are modifications to existing files in an established project structure. Proceed directly to Phase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Refactor the CLI's service-construction and context-object patterns so all subsequent user story phases can build on a stable foundation.

**⚠️ CRITICAL**: No user story work (Phases 3–5) can begin until this phase is complete.

- [x] T001 Write failing tests asserting `build()` returns a `BuildResult` instance with `.service`, `.repository`, `.config_file_path` (absolute `Path`), and `.config_file_exists` (bool) fields in `tests/test_cli.py`
- [x] T002 Add `BuildResult` dataclass and `build(config_path: Path | None) -> BuildResult` function (replacing `build_service()`) in `taxomesh/adapters/cli/config.py`; `config_file_path` must always be an absolute resolved `Path`; add Google-style docstrings to both `BuildResult` (class-level, describing all fields) and `build()` (Args/Returns sections); run T001 tests — must pass
- [x] T003 Refactor `taxomesh/adapters/cli/main.py`: change root callback `ctx.obj` from `Path | None` to `dict[str, Any]` with keys `config_path` and `verbose` (default 0); at the `ctx.obj = {...}` assignment add an inline `# Any: ctx.obj is a typed dict accessed only via _verbose()/_config_path() helpers` comment to satisfy the mypy-strict `Any` justification requirement (constitution Principle IV); add private helpers `_verbose(ctx: typer.Context) -> int` and `_config_path(ctx: typer.Context) -> Path | None`; replace every `svc = _get_service(ctx)` call in all 14 sub-command handlers with `result = build(_config_path(ctx)); svc = result.service`; remove `_get_service()`

**Checkpoint**: `build()` returns `BuildResult`; all sub-commands use `build()` internally; all existing tests pass.

---

## Phase 3: User Story 3 — Repository Configuration Method (Priority: P2)

**Note**: US3 is scheduled before US1 because `get_config_summary()` is a hard prerequisite for the verbose block output (FR-008). Its own user value (programmatic introspection) is also delivered here.

**Goal**: `TaxomeshRepositoryBase` exposes `get_config_summary() -> str`; `JsonRepository` implements it; method is tested independently.

**Independent Test**: Construct a `JsonRepository(Path("/data/x.json"))` and assert `get_config_summary()` returns a string containing `/data/x.json`.

- [x] T004 [P] [US3] Write failing test for `JsonRepository.get_config_summary()`: assert it returns a non-empty string containing the configured path; assert it does not raise in `tests/test_cli.py`
- [x] T005 [P] [US3] Add `get_config_summary() -> str` method stub (with full Google-style docstring specifying no-raise and no-secrets contract) to `TaxomeshRepositoryBase` protocol in `taxomesh/ports/repository.py`
- [x] T006 [US3] Implement `get_config_summary()` in `JsonRepository` returning `str(self._path)`; add Google-style docstring in `taxomesh/adapters/repositories/json_repository.py`; run T004 test — must pass

**Checkpoint**: `JsonRepository.get_config_summary()` returns the configured path string; US3 acceptance criteria (spec scenarios 1–3) satisfied.

---

## Phase 4: User Story 1 — `--verbose` Flag & Repository Info Display (Priority: P1)

**Goal**: Root `taxomesh` command accepts `--verbose [N]`; when level ≥ 1, a 3-line block is printed to stdout before any sub-command output — unconditionally, even on error.

**Independent Test**: Run `taxomesh --verbose category list` via `CliRunner`; assert the first three output lines contain `Repository`, `Config`, and `Config file` labels before any category records or list headers.

- [x] T007 [US1] Write failing tests covering all US1 acceptance scenarios: `--verbose` (no value) → level 1 output; `--verbose 1` → same output; `--verbose 2` → accepted without error, output identical to level 1 (clamped); `--verbose 0` → no verbose block; no flag → no verbose block; verbose block appears before list header; config file path shown with `[not found]` when file absent; verbose block appears even when command errors (no footer on error) in `tests/test_cli.py`
- [x] T008 [US1] Add `verbose: int` option to root `main()` callback in `taxomesh/adapters/cli/main.py` using `typer.Option(0, "--verbose", is_flag=False, flag_value=1, help="Verbosity level: 0=silent (default), 1=verbose. Using --verbose without a value sets level 1.")`; update `ctx.obj` dict to include `"verbose": min(verbose, 1)` (clamp to 1); **fallback**: if `is_flag=False, flag_value=1` is rejected by Click at runtime, use `Optional[int] = typer.Option(None)` with `None` treated as 0 — note that this fallback cannot satisfy FR-001's "no-value → level 1" requirement; if the fallback is activated the T007 `--verbose` (no-value) test will fail and must be marked xfail with a comment explaining the Click limitation
- [x] T009 [US1] Implement `_print_verbose(result: BuildResult, level: int) -> None` in `taxomesh/adapters/cli/main.py`: when `level >= 1`, print the three-line aligned block to stdout — `Repository  : {type(result.repository).__name__}`, `Config      : {result.repository.get_config_summary()}`, `Config file : {result.config_file_path}` (append ` [not found]` when `not result.config_file_exists`)
- [x] T010 [US1] Add `_print_verbose(result, _verbose(ctx))` call immediately after `result = build(_config_path(ctx))` in all 14 sub-command handlers in `taxomesh/adapters/cli/main.py`; run T007 tests — must pass

**Checkpoint**: `taxomesh --verbose <any-command>` prints the 3-line repository block first; all US1 acceptance scenarios pass.

---

## Phase 5: User Story 2 — List Command Headers & Footers (Priority: P1)

**Goal**: Every `list` sub-command prints `--- {Label} ---` before records and `--- Total: N ---` after, always, regardless of verbosity.

**Independent Test**: Run `taxomesh category list` (three categories) via `CliRunner`; assert output contains `--- Categories ---` before record lines and `--- Total: 3 ---` after; run with 0 categories and assert `--- Total: 0 ---`.

- [x] T011 [US2] Write failing tests covering all US2 acceptance scenarios: header and footer present on `category list`, `item list`, `tag list`; footer count is 0 for empty; footer count matches filter result (not total) when `--category-id` or `--parent-id` is used; no footer when command errors in `tests/test_cli.py`
- [x] T012 [US2] Update `category_list`, `item_list`, `tag_list` in `taxomesh/adapters/cli/main.py`: collect all records into a list first; `typer.echo(f"--- {label} ---")` before records; print each record; `typer.echo(f"--- Total: {len(records)} ---")` after; entity labels: `Categories`, `Items`, `Tags`; do not print footer in the error path; run T011 tests — must pass

**Checkpoint**: All three list commands produce header + records + footer; footer count is filter-accurate; US2 acceptance scenarios pass.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Repair existing tests broken by new list output format; verify full quality gate compliance.

- [x] T013 Update all existing assertions in `tests/test_cli.py` that match the raw output of `category list`, `item list`, or `tag list` commands: wrap expected strings to account for the new `--- {Label} ---` header and `--- Total: N ---` footer lines; run full test suite to confirm no regressions
- [x] T014 Run all quality gates and fix any violations: `ruff check .` → `ruff format --check .` → `mypy --strict .` → `pytest --cov=taxomesh --cov-fail-under=80`; all must pass before this task is marked complete

**Checkpoint**: All 14 tasks complete; full quality gate suite green.

---

## Phase 7: Amendment — Boolean `--verbose` Simplification

**Purpose**: Remove integer verbosity levels (0/1/2) and replace `--verbose [N]` with a
plain boolean `--verbose` flag. Removes clamping logic, the `None`-as-0 fallback, and all
xfail markers. `--verbose` (bare, no value) now works naturally.

**⚠️ NOTE**: This phase amends Phase 4 (US1). Tasks T007–T010 remain marked complete as
the underlying verbose mechanism already works; only the type/levels change.

- [x] T015 [US1-amend] In `tests/test_cli.py`: remove 3 level-specific tests
  (`test_verbose_2_clamped_to_level_1`, `test_verbose_0_suppresses_block`,
  `test_verbose_1_same_as_bare_verbose`); remove the 6 `@pytest.mark.xfail` decorators
  from the remaining bare-`--verbose` tests; confirm all 6 now FAIL (bare `--verbose`
  still broken until T016)
- [x] T016 [US1-amend] In `taxomesh/adapters/cli/main.py`: change `verbose: int | None`
  to `verbose: bool = typer.Option(False, "--verbose", is_flag=True, help="Enable verbose
  output: show repository type, configuration, and config file path before command output.")`
  ; update `ctx.obj` to store `verbose` directly as `bool`; change `_verbose(ctx) -> int`
  to `_verbose(ctx) -> bool`; update `_print_verbose(result, level)` signature to
  `_print_verbose(result, verbose)` and condition from `level >= 1` to `verbose`; remove
  `min(verbose, 1) if verbose is not None else 0` clamping; run T015 tests — must pass
- [x] T017 [US1-amend] Run quality gates: `ruff check .` → `ruff format --check .` →
  `mypy --strict .` → `pytest --cov=taxomesh --cov-fail-under=80`; all must pass

**Checkpoint**: `taxomesh --verbose category list` works; no xfail tests; all quality gates green.

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 2 (Foundational)
  └── Phase 3 (US3 — prerequisite for US1)
        └── Phase 4 (US1)
  └── Phase 5 (US2 — independent of US3 and US1)
        └── Phase 6 (Polish — depends on US1 + US2 complete)
```

### User Story Dependencies

| Story | Depends On | Can Parallelize With |
|-------|------------|---------------------|
| US3 (Phase 3) | Phase 2 complete | US2 (Phase 5) |
| US1 (Phase 4) | Phase 2 + US3 complete | — |
| US2 (Phase 5) | Phase 2 complete | US3 (Phase 3) |

### Within Each Phase

- T004 and T005 within Phase 3 are marked [P] — different files (`tests/test_cli.py` vs `taxomesh/ports/repository.py`), no inter-dependency.
- T006 depends on both T004 and T005.
- All Phase 4 and Phase 5 tasks touch `taxomesh/adapters/cli/main.py`; keep sequential within each phase.
- Phase 5 (US2) can begin as soon as Phase 2 is done — it does NOT need Phase 3 (US3) or Phase 4 (US1).

---

## Parallel Opportunities

### Phase 3: run T004 and T005 simultaneously

```
Task: T004 — write get_config_summary test in tests/test_cli.py
Task: T005 — add get_config_summary stub to taxomesh/ports/repository.py
```

### Phases 3 and 5: run simultaneously after Phase 2 (two-developer scenario)

```
Developer A: Phase 3 (US3) → Phase 4 (US1)
Developer B: Phase 5 (US2)
```

---

## Implementation Strategy

### MVP (Phase 2 + Phase 3 + Phase 4 only)

1. Complete Phase 2: ctx.obj + BuildResult refactoring
2. Complete Phase 3: `get_config_summary()` protocol + implementation
3. Complete Phase 4: `--verbose` flag + verbose block output
4. **STOP and VALIDATE**: `taxomesh --verbose <command>` shows repo block; US1 and US3 acceptance scenarios pass

### Full Delivery

1. MVP above (Phases 2–4)
2. Phase 5: list headers/footers — independently testable
3. Phase 6: repair broken tests + quality gates → all green

### Single-Developer Order

T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008 → T009 → T010 → T011 → T012 → T013 → T014

---

## Notes

- **TDD**: each test task (`T001`, `T004`, `T007`, `T011`) must produce a **failing** test before the corresponding implementation task runs
- `[P]` = different files, no blocking dependency on other tasks in the same phase
- `[US#]` label maps each task to a user story for traceability
- Commit after each phase checkpoint or logical group; never commit a failing test suite
- Phase 6 T014 must be the final check — no PR without a fully green quality gate run
