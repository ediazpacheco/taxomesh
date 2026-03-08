# Tasks: Graph & Admin UX Improvements

**Input**: Design documents from `/specs/025-graph-admin-ux/`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅

**TDD**: Mandatory per CLAUDE.md — write failing tests first, verify they FAIL, then implement.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: User story label (US1–US6)

---

## Phase 1: Setup

**Purpose**: Add named constants that are shared across US1 (CLI) and US2 (admin graph depth).
These are foundational and blocking for both.

- [x] T001 Add `MAX_DEPTH_UNLIMITED: Final[int] = 0` and `GRAPH_DEFAULT_MAX_DEPTH: Final[int] = 3` constants to `taxomesh/adapters/cli/main.py` (after existing imports/constants section)
- [x] T002 Add `ADMIN_GRAPH_DEFAULT_MAX_DEPTH: Final[int] = 3` constant to `taxomesh/contrib/django/admin.py` (after `TAXOMESH_LINKED_MODEL_SETTING`)

---

## Phase 2: Foundational — `_resolve_linked_url` shared helper

**Purpose**: Extract the linked-model URL resolution into a shared module-level helper used by
US3 (list/detail icon-links) and the existing `graph_view`. Must complete before US3.

⚠️ US3 depends on this phase. US1, US2, US4, US5, US6 are independent of it.

- [x] T003 Extract `_resolve_linked_url(external_id: str) -> str | None` from `graph_view` into a module-level private helper in `taxomesh/contrib/django/admin.py`; update `graph_view` to call `_resolve_linked_url(entry["external_id"])` instead of the inline logic; ensure `mypy --strict .` still passes

**Checkpoint**: `mypy --strict .` passes. `_resolve_linked_url` is callable from any admin class.

---

## Phase 3: User Story 1 — CLI `--max-depth` (Priority: P1) 🎯 MVP

**Goal**: `taxomesh graph` accepts `--max-depth N` (default 3); nodes beyond depth N are omitted.
`--max-depth 0` renders the complete taxonomy.

**Independent Test**: Run `taxomesh graph` on a 5-level taxonomy — only depths 0–2 (categories)
and 1–3 (items) appear. Run with `--max-depth 0` — all nodes appear.

> ⚠️ **TDD**: Write T004, verify FAIL, then implement T005–T006.

### Tests (write first — must FAIL before implementation)

- [x] T004 [P] [US1] Write failing tests in `tests/adapters/cli/test_graph_output.py` — class `TestMaxDepth`:
  - `test_graph_default_max_depth_hides_deep_nodes` — assert nodes beyond depth 3 absent in default output
  - `test_graph_max_depth_zero_shows_all_nodes` — assert all nodes appear with `--max-depth 0`
  - `test_graph_max_depth_one_shows_only_root_categories` — assert only root categories appear with `--max-depth 1` (no items, no children)
  - `test_graph_show_relations_respects_max_depth` — assert relations only appear for items within depth limit

### Implementation

- [x] T005 [US1] Add `max_depth: int = typer.Option(GRAPH_DEFAULT_MAX_DEPTH, "--max-depth", help="Max depth to display; 0 = unlimited")` parameter to `graph_cmd` in `taxomesh/adapters/cli/main.py`
- [x] T006 [US1] Update `_add_graph_node` in `taxomesh/adapters/cli/main.py` to accept `current_depth: int = 0` and `max_depth: int = MAX_DEPTH_UNLIMITED`; skip items when `max_depth != MAX_DEPTH_UNLIMITED and current_depth + 1 > max_depth`; skip child recursion when `max_depth != MAX_DEPTH_UNLIMITED and current_depth + 1 > max_depth`; pass `current_depth + 1` and `max_depth` in recursive calls; update `graph_cmd` to pass `max_depth=max_depth` to `_add_graph_node`

**Verify**: `pytest tests/adapters/cli/test_graph_output.py::TestMaxDepth` → all pass.

**Checkpoint**: US1 fully functional and independently testable.

---

## Phase 4: User Story 2 — Admin Graph Depth + Relations Always Collapsed (Priority: P2)

**Goal**: Admin graph respects `ADMIN_GRAPH_DEFAULT_MAX_DEPTH = 3`; removes the "Show item
relations" toggle; item relations are always rendered but collapsed per-item via `[+]`/`[-]`.

**Independent Test**: Load admin graph — no checkbox present; items with relations show `[+]`;
nodes beyond depth 3 absent; clicking `[+]` reveals relations without page reload.

> ⚠️ **TDD**: Write T007, verify FAIL, then implement T008–T009.

### Tests (write first — must FAIL before implementation)

- [x] T007 [P] [US2] Write failing tests in `tests/contrib/django/test_admin_graph.py` — class `TestDepthAndRelations`:
  - `test_admin_graph_omits_nodes_beyond_default_depth` — assert nodes at depth > 3 absent in response
  - `test_admin_graph_no_relations_toggle_checkbox` — assert `id="taxomesh-show-relations"` absent in response HTML
  - `test_admin_graph_item_with_relations_has_toggle_button` — assert items with relations still have `taxomesh-rel-toggle` button
  - `test_admin_graph_relation_rows_hidden_by_default` — assert `.taxomesh-relations` blocks have `display:none` or equivalent

### Implementation

- [x] T008 [US2] Update `_flatten_graph` in `taxomesh/contrib/django/admin.py` to accept `max_depth: int = ADMIN_GRAPH_DEFAULT_MAX_DEPTH`; in `_visit(node, depth)`, return early (skip entry + descendants) when `max_depth != 0 and depth > max_depth`; skip item entries when `max_depth != 0 and depth + 1 > max_depth`; update `graph_view` call to `_flatten_graph(graph)` (default applies automatically)
- [x] T009 [US2] Update `taxomesh/contrib/django/templates/admin/taxomesh_contrib_django/graph.html`:
  - Remove the `<label><input type="checkbox" id="taxomesh-show-relations">` block and its JS event handler
  - Remove CSS `.taxomesh-relations-visible .taxomesh-relations { display: block }` rule
  - Keep `.taxomesh-relations` blocks hidden by default (`display: none`)
  - Keep `taxomesh-rel-toggle` buttons for items with relations — clicking them directly toggles that item's `.taxomesh-relations` block (simplified JS: no checkbox dependency)

**Verify**: `pytest tests/contrib/django/test_admin_graph.py::TestDepthAndRelations` → all pass.

**Checkpoint**: US2 fully functional and independently testable.

---

## Phase 5: User Story 3 — Icon-Link in Item/Category List & Detail (Priority: P3)

**Goal**: When `TAXOMESH_LINKED_MODEL` is configured, Item and Category admin list and detail
views show a `↗` icon-link for entries with a non-empty `external_id`.

**Independent Test**: With `TAXOMESH_LINKED_MODEL` set, Item list shows `↗` column; entries with
`external_id` have a link; entries without do not; same icon on detail page.

> ⚠️ **TDD**: Write T010, verify FAIL, then implement T011–T012.

### Tests (write first — must FAIL before implementation)

- [x] T010 [P] [US3] Write failing tests in `tests/contrib/django/test_admin_graph.py` — class `TestLinkedObjectColumn`:
  - `test_item_list_shows_linked_url_column_when_model_configured` — assert `↗` appears in Item changelist for item with `external_id`
  - `test_item_list_no_icon_when_external_id_absent` — assert no `↗` for item without `external_id`
  - `test_category_list_shows_linked_url_column` — assert `↗` in Category changelist for category with `external_id`
  - `test_item_detail_shows_linked_url_field` — assert `↗` link present in Item change form readonly fields

### Implementation

- [x] T011 [US3] Add `linked_object_url(self, obj: ItemModel) -> str` method to `ItemModelAdmin` in `taxomesh/contrib/django/admin.py` — calls `_resolve_linked_url(obj.external_id or "")`, returns `format_html('<a href="{}" title="View in admin">↗</a>', url)` if URL resolved else `""`; set `linked_object_url.short_description = "↗"` and `linked_object_url.allow_tags = True`; add `"linked_object_url"` to `list_display` and `readonly_fields`
- [x] T012 [P] [US3] Add `linked_object_url(self, obj: CategoryModel) -> str` method to `CategoryModelAdmin` in `taxomesh/contrib/django/admin.py` — same pattern as T011 but for `CategoryModel`; add `"linked_object_url"` to `list_display` and `readonly_fields`

**Verify**: `pytest tests/contrib/django/test_admin_graph.py::TestLinkedObjectColumn` → all pass.

**Checkpoint**: US3 fully functional and independently testable.

---

## Phase 6: User Story 4 — Admin Home Version Widget (Priority: P4)

**Goal**: The Taxomesh section in the Django admin home shows the installed taxomesh version
and the active backend (config path or "Django ORM backend").

**Independent Test**: Load Django admin home — Taxomesh section displays a non-empty version
string and a non-empty backend string.

> ⚠️ **TDD**: Write T013, verify FAIL, then implement T014–T015.

### Tests (write first — must FAIL before implementation)

- [x] T013 [P] [US4] Write failing tests in `tests/contrib/django/test_admin_graph.py` — class `TestVersionWidget`:
  - `test_app_index_shows_taxomesh_version` — assert version string is present in app_index response HTML
  - `test_app_index_shows_backend_info` — assert backend/config info is present in app_index response HTML

### Implementation

- [x] T014 [US4] Add `taxomesh_version_info` simple tag to `taxomesh/contrib/django/templatetags/taxomesh_tags.py` — returns `dict[str, str]` with `version` (from `importlib.metadata.version("taxomesh")`, fallback `"unknown"`) and `backend` (str path to `taxomesh.toml` in `settings.BASE_DIR` if it exists, else `"Django ORM backend"`); import `importlib.metadata` and `pathlib.Path`
- [x] T015 [US4] Update `taxomesh/contrib/django/templates/admin/taxomesh_contrib_django/app_index.html` — add `{% load taxomesh_tags %}` and `{% taxomesh_version_info as tm_info %}` at top of block; add a new table row in the existing "Visualization" module showing `taxomesh {{ tm_info.version }}` and `{{ tm_info.backend }}`

**Verify**: `pytest tests/contrib/django/test_admin_graph.py::TestVersionWidget` → all pass.

**Checkpoint**: US4 fully functional and independently testable.

---

## Phase 7: User Story 5 — Remove `ItemRelationLinkModelAdmin` (Priority: P5)

**Goal**: The standalone "Item relation links" entry is removed from the Django admin. Relation
management continues to work via inlines on the Item change page.

**Independent Test**: Django admin home has no "Item relation links" section; Item change page
inlines still functional.

> ⚠️ **TDD**: Write T016, verify FAIL (test currently passes since admin IS registered), then implement T017.

### Tests (write first)

- [x] T016 [P] [US5] Write/update test in `tests/contrib/django/test_admin_graph.py` — class `TestItemRelationLinkNotRegistered`:
  - `test_item_relation_link_not_in_admin_registry` — assert `ItemRelationLinkModel not in admin.site._registry`
  - Verify this test FAILS (since admin is still registered) before implementing T017

### Implementation

- [x] T017 [US5] Delete `ItemRelationLinkModelAdmin` class and its `@admin.register(ItemRelationLinkModel)` decorator from `taxomesh/contrib/django/admin.py` (currently at lines ~940–984); keep `ItemRelationLinkModel` import (still needed by inlines and `ItemRelationLinkForm`)

**Verify**: `pytest tests/contrib/django/test_admin_graph.py::TestItemRelationLinkNotRegistered` → all pass.

**Checkpoint**: US5 complete. Inlines on Item change page still work.

---

## Phase 8: User Story 6 — README & Version Bump (Priority: P6)

**Goal**: README documents all new features; package version bumped to `0.1.0a12`.

> No test tasks — documentation and version changes are validated by reading and by `pip show`.

### Implementation

- [x] T018 [P] [US6] Bump version from `0.1.0a11` to `0.1.0a12` in `pyproject.toml` line 3
- [x] T019 [P] [US6] Update `README.md` — add/update sections documenting: `--max-depth` CLI option (with default 3 and `0`=unlimited); admin graph depth behaviour (top 3 levels by default); item relations always shown collapsed; `TAXOMESH_LINKED_MODEL` icon-link in Item/Category list and detail; admin home version widget; note that `ItemRelationLinkModelAdmin` is removed (use Item inlines instead)

**Checkpoint**: US6 complete.

---

## Phase 9: Polish & Quality Gates

- [x] T020 Run `ruff check .` and fix any linting violations in modified files
- [x] T021 Run `ruff format --check .` and fix any formatting issues
- [x] T022 Run `mypy --strict .` and fix all type errors (focus on `_add_graph_node` new params, `_flatten_graph` signature, `linked_object_url` methods, `taxomesh_version_info` return type)
- [x] T023 Run `pytest --cov=taxomesh --cov-fail-under=80` — full suite must pass with ≥ 80% coverage

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 (T003 uses constants from T002)
- **US1 (Phase 3)**: Depends on T001 (constants in CLI file)
- **US2 (Phase 4)**: Depends on T002 (admin constant); benefits from T003 if `_resolve_linked_url` touches `graph_view` (but graph_view depth change is independent)
- **US3 (Phase 5)**: Depends on Phase 2 (T003 — `_resolve_linked_url` must exist)
- **US4 (Phase 6)**: Depends on T001/T002 indirectly (template tag file); independent of US1–US3
- **US5 (Phase 7)**: Independent — can run after Phase 1
- **US6 (Phase 8)**: Independent — can run at any point; ideally last
- **Polish (Phase 9)**: All prior phases complete

### User Story Dependencies

| Story | Depends on | Can run in parallel with |
|-------|------------|--------------------------|
| US1 | T001 | US2 (different file), US4, US5, US6 |
| US2 | T002, T008 (depth in flatten) | US1, US3 (different classes), US5 |
| US3 | Phase 2 (T003) | US1, US4, US5 |
| US4 | T014 (template tag) | US1, US3, US5 |
| US5 | — | All |
| US6 | — | All (do last for accuracy) |

### Within Each User Story

1. Test task — write and verify it **FAILS**
2. Implementation tasks — in order
3. Re-run tests — verify they **PASS**

---

## Parallel Execution Examples

### After Phase 1 + Phase 2

```
Parallel A: T004 → T005 → T006  (US1 — CLI, test_graph_output.py)
Parallel B: T007 → T008 → T009  (US2 — admin.py + graph.html)
Parallel C: T013 → T014 → T015  (US4 — templatetags + app_index.html)
Parallel D: T016 → T017         (US5 — admin.py, different class)
```

### After Phase 2 complete

```
Parallel E: T010 → T011 → T012  (US3 — admin.py ItemModelAdmin/CategoryModelAdmin)
```

---

## Implementation Strategy

### MVP (US1 + US5 — quickest wins)

1. T001 (setup)
2. T004 → T005 → T006 (CLI `--max-depth`)
3. T016 → T017 (remove ItemRelationLinkModelAdmin)
4. T020–T023 (quality gates)

### Full incremental delivery

1. T001–T003 (setup + foundational)
2. US1 (CLI depth)
3. US2 (admin depth + relations collapse)
4. US3 (list/detail icon-links)
5. US4 (version widget)
6. US5 (remove standalone admin)
7. US6 (README + version)
8. Quality gates

---

## Notes

- All TDD tasks must FAIL before their implementation tasks run (CLAUDE.md mandatory)
- `_resolve_linked_url` helper (T003) uses `format_html` from `django.utils.html` — safe HTML construction
- `linked_object_url` methods use `format_html` + `mark_safe` appropriately — no raw string concatenation
- `ADMIN_GRAPH_DEFAULT_MAX_DEPTH = 3` matches `GRAPH_DEFAULT_MAX_DEPTH = 3` — same default, separate constants (different adapter layers)
- `ItemRelationLinkModel` import stays in admin.py after T017 — do not remove it
