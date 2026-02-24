# Tasks: Taxonomy Graph

**Input**: Design documents from `/specs/006-taxonomy-graph/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**TDD**: Test tasks are REQUIRED by project constitution (CLAUDE.md §Testing Rules).
Every test task MUST run and fail before its paired implementation task.

**Already implemented (do not re-implement)**:
- FR-011–FR-014 (root category: `_ensure_root()`, `_root_id`, `TaxomeshRootCategoryError`) — 200 tests green.

**Remaining scope**: FR-001–FR-010, FR-007a, FR-007b — `TaxomeshGraph` type, `get_graph()` service method, `graph` CLI command.

---

## Phase 1: Setup

**Purpose**: Add `rich` runtime dependency required by the CLI render command.

- [x] T001 Add `rich>=13.0` to `[project] dependencies` in `pyproject.toml` and run `uv add rich` to update `uv.lock`

**Checkpoint**: `python -c "import rich"` succeeds in the virtualenv.

---

## Phase 2: Foundational (Blocking Prerequisite)

**Purpose**: Define the `CategoryNode` and `TaxomeshGraph` dataclasses that both US1 (service) and US2 (CLI) depend on.

**⚠️ CRITICAL**: Neither user story can be implemented until this phase is complete.

- [x] T002 Create `taxomesh/domain/graph.py` with `CategoryNode` and `TaxomeshGraph` dataclasses exactly as specified in `specs/006-taxonomy-graph/data-model.md`:
  - `@dataclass class CategoryNode` with fields `category: Category`, `items: list[Item]`, `children: list[CategoryNode]`
  - `@dataclass class TaxomeshGraph` with field `roots: list[CategoryNode]`
  - Module docstring; import `Category` and `Item` from `taxomesh.domain.models`
  - No Pydantic; stdlib `dataclasses` only

**Checkpoint**: `from taxomesh.domain.graph import CategoryNode, TaxomeshGraph` succeeds; `mypy --strict taxomesh/domain/graph.py` passes.

---

## Phase 3: User Story 1 — Retrieve Taxonomy Graph from Service (Priority: P1) 🎯 MVP

**Goal**: `TaxomeshService.get_graph()` returns a fully populated `TaxomeshGraph` snapshot — all non-root categories with their items and children, respecting sort_index ordering and multi-parent repetition.

**Independent Test**: Call `service.get_graph()` on a populated `InMemoryRepository`; assert graph structure, ordering, and exclusions without touching the CLI.

### Tests for User Story 1

> **Write these tests FIRST. All MUST fail before T004 is started.**

- [x] T003 [US1] Write failing tests for `get_graph()` in `tests/service/test_service_graph.py` covering all acceptance scenarios:
  - `test_get_graph_returns_taxomesh_graph_instance` — return type is `TaxomeshGraph`
  - `test_get_graph_empty_taxonomy_returns_empty_roots` — no user categories → `roots == []`
  - `test_get_graph_single_category_no_items` — one category, no items → `roots` has one `CategoryNode` with empty `items` and `children`
  - `test_get_graph_items_ordered_by_sort_index` — two items with reversed sort_index → returned in ascending order
  - `test_get_graph_item_in_multiple_categories_appears_in_each` — one item placed in two categories → appears in both nodes
  - `test_get_graph_excludes_root_from_graph` — root category (`__root__`) never appears in any `CategoryNode.category`
  - `test_get_graph_top_level_category_appears_in_roots` — category with only root as parent → in `TaxomeshGraph.roots`
  - `test_get_graph_child_category_not_in_roots` — category with explicit parent → NOT in `TaxomeshGraph.roots`; appears in parent's `children`
  - `test_get_graph_multi_parent_category_appears_under_each_parent` — category with two explicit parents → appears in both parents' `children`
  - `test_get_graph_children_ordered_by_sort_index` — two children with different sort_index values → returned in ascending order
  - `test_get_graph_no_tag_data_in_graph` — taxonomy with tags → `TaxomeshGraph` carries no tag objects anywhere (SC-002)

### Implementation for User Story 1

- [x] T004 [US1] Implement `TaxomeshService.get_graph() -> TaxomeshGraph` in `taxomesh/application/service.py` (depends on T002, T003 — tests must fail first):
  - Import `TaxomeshGraph`, `CategoryNode` from `taxomesh.domain.graph`
  - Algorithm (reads only — no writes):
    1. `all_cats = {c.category_id: c for c in self._repo.list_categories() if c.category_id != self._root_id}`
    2. `all_links = self._repo.list_category_parent_links()`
    3. `explicit_links` = links where `parent_category_id != self._root_id`
    4. `root_child_links` = links where `parent_category_id == self._root_id`; build `root_sort = {link.category_id: link.sort_index for link in root_child_links}`
    5. `explicitly_parented` = `{link.category_id for link in explicit_links}`
    6. Top-level cat IDs = `{cid for cid in root_sort if cid not in explicitly_parented}`
    7. `children_by_parent`: `dict[UUID, list[tuple[int, UUID]]]` — for each explicit link: append `(sort_index, category_id)` under `parent_category_id`; sort each list by sort_index
    8. `item_links = self._repo.list_item_parent_links()`; `items_map = {i.item_id: i for i in self._repo.list_items()}`; `items_by_cat`: `dict[UUID, list[Item]]` — per category, sort by sort_index
    9. Recursive `_build_node(cat_id) -> CategoryNode`: `items = items_by_cat.get(cat_id, [])`, `children = [_build_node(cid) for _, cid in sorted children_by_parent.get(cat_id, [])]`
    10. `roots = [_build_node(cid) for cid in sorted top-level IDs by root_sort[cid]]`
    11. Return `TaxomeshGraph(roots=roots)`
  - Add Google-style docstring

**Checkpoint**: `pytest tests/service/test_service_graph.py -v` → all 11 tests pass.

---

## Phase 4: User Story 2 — Display Taxonomy Graph in the Terminal (Priority: P2)

**Goal**: `taxomesh graph` renders the full taxonomy as a Rich colour-coded tree: categories in bold cyan, items in yellow, `[disabled]` badge on disabled items, descriptive empty message.

**Independent Test**: Invoke `graph` command via `CliRunner` on both empty and populated taxonomies; assert exit code 0, presence of category names, item `external_id`, `[disabled]` badge for disabled items, tree connector characters.

### Tests for User Story 2

> **Write these tests FIRST. All MUST fail before T006 is started.**

- [x] T005 [P] [US2] Write failing tests for the `graph` CLI command in `tests/test_cli.py` (appended to existing file) covering all acceptance scenarios:
  - `test_graph_empty_taxonomy_exits_zero` — empty repo → exit code 0
  - `test_graph_empty_taxonomy_shows_message` — output contains a non-blank descriptive message (not empty string) (FR-009)
  - `test_graph_shows_category_name` — one category "Animals" → "Animals" in output (FR-007b)
  - `test_graph_shows_item_external_id` — item with external_id "lion" → "lion" in output (FR-007a)
  - `test_graph_shows_item_item_id` — item with known item_id UUID → str(item_id) in output (FR-007a)
  - `test_graph_shows_item_enabled_true` — item with `enabled=True` → "enabled=True" in output (FR-007a)
  - `test_graph_shows_item_enabled_false` — item with `enabled=False` → "enabled=False" in output (FR-007a)
  - `test_graph_shows_tree_connectors` — populated taxonomy → output contains at least one of: `│`, `├`, `└`, `──` (FR-008)
  - `test_graph_nested_category_appears_under_parent` — child category explicitly linked to parent → child's name in output (FR-008)
  - `test_graph_no_tag_data_in_output` — taxonomy with tags → tag names not in graph output (FR-010)
  - Use `InMemoryRepository` + patched `build` (same pattern as existing CLI tests)

### Implementation for User Story 2

- [x] T006 [US2] Implement `graph` Typer command in `taxomesh/adapters/cli/main.py` (depends on T004, T005 — tests must fail first):
  - Add `@app.command("graph")` (top-level single command, not a sub-app): `def graph_cmd(ctx: typer.Context) -> None:`
    - Call `build(_config_path(ctx))`, `_print_verbose(result, _verbose(ctx))`
    - Call `result.service.get_graph()` inside try/except `TaxomeshError` → `_err(str(exc))`
    - If `graph.roots == []`: `typer.echo("No categories found. Add one with: taxomesh category add --name <name>")` and return (exit 0)
    - Otherwise build `rich.tree.Tree("Taxonomy")` and recursively populate; print via `rich.console.Console().print(tree)`
  - Recursive helper `_add_graph_node(tree_node, category_node)`:
    - Add category branch: `tree_node.add(f"[bold cyan]{category_node.category.name}[/bold cyan]")`
    - For each item: build label with all three fields:
      `enabled_style = "green" if item.enabled else "red"`
      `label = f"[yellow]{item.external_id}[/yellow]  [dim]{item.item_id}[/dim]  [{enabled_style}]enabled={item.enabled}[/{enabled_style}]"`
    - Recurse into children
  - Add Google-style docstrings to new function and command

**Checkpoint**: `pytest tests/test_cli.py -k graph -v` → all graph tests pass; `taxomesh graph` (real CLI) renders a tree.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [x] T007 [P] Update `taxomesh/__init__.py` exports: verify `TaxomeshGraph` and `CategoryNode` do NOT need to be re-exported (they are returned by `get_graph()` — callers receive them via type inference; no explicit export needed per constitution Public API Surface rules)
- [x] T008 Run full quality gates and confirm all pass:
  - `ruff check .`
  - `ruff format --check .`
  - `mypy --strict .`
  - `pytest --cov=taxomesh --cov-fail-under=80`

**Checkpoint**: All four gates green; PR is ready.

---

## Dependencies & Execution Order

### Phase Dependencies

```
T001 (Setup: rich dep)
  └── T002 (Foundational: domain types)
        ├── T003 (US1 tests: write failing) ──→ T004 (US1 impl: get_graph)
        │                                              └── T005 (US2 tests: write failing) ──→ T006 (US2 impl: graph cmd)
        └── T005 can start after T002 (dataclasses needed for test assertions)
```

- **T001**: No dependencies — start immediately
- **T002**: Depends on T001 (rich available for import sanity check)
- **T003**: Depends on T002 (imports `TaxomeshGraph`); must fail before T004
- **T004**: Depends on T002 + T003 (tests failing)
- **T005**: Depends on T004 (CLI tests exercise `get_graph()` indirectly); must fail before T006
- **T006**: Depends on T004 + T005 (tests failing)
- **T007, T008**: Depend on T006

### Parallel Opportunities

- T003 and T005 can be written in parallel after T002 (both are test files in different locations with no shared writes)
- T007 (export check) can run in parallel with T008 after T006

---

## Parallel Example: Write Both Test Files Together

```
After T002 completes:
  Task A: T003 — Write tests/service/test_service_graph.py (US1 tests)
  Task B: T005 — Write graph CLI tests in tests/test_cli.py (US2 tests)
  → Both can run simultaneously (different files)
```

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. T001 — Add rich dep
2. T002 — Create domain types
3. T003 — Write failing service tests
4. T004 — Implement `get_graph()`
5. **STOP and VALIDATE**: `pytest tests/service/test_service_graph.py -v` → all pass
6. Developers using the library can now call `service.get_graph()`

### Full Delivery

5. T005 — Write failing CLI tests
6. T006 — Implement `graph` command
7. T007, T008 — Polish + quality gates
8. Open PR

---

## Notes

- `[P]` = parallelizable (different files, no dependency on incomplete sibling task)
- `[US1]` / `[US2]` = traceability to spec user story
- Constitution rule: tests must FAIL before implementation starts — never skip
- `__root__` is already fully implemented; `test_service_graph.py` uses `service._root_id` only for setup assertions, not as a focus
- `rich` Console in CLI tests: `CliRunner` captures Rich output including markup; check for markup strings or use `strip_ansi=False` — existing test pattern in `tests/test_cli.py` already works
