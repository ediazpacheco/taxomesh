# Tasks: Graph Enhancements (CLI + Admin)

**Input**: Design documents from `/specs/024-graph-enhancements/`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅

**TDD**: Mandatory per CLAUDE.md — every test task must run and FAIL before its implementation task begins.

**Note on US2**: FR-004 (link underlines) is already implemented in the template.
T007 is a regression test that should pass immediately; document as such.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (US1–US5)

---

## Phase 1: Setup

**Purpose**: Ensure the admin graph test file exists as a base for all admin test tasks.

- [x] T001 Create `tests/contrib/django/test_admin_graph.py` if it does not already exist — module docstring, `pytest.importorskip("django")`, `pytestmark = pytest.mark.django_db`, empty body ready for test classes

---

## Phase 2: Foundational (Blocking Prerequisites for Admin Stories)

**Purpose**: Introduce `GraphEntry` and `RelationEntry` TypedDicts and refactor `_flatten_graph`
so that US3, US4, and US5 share a stable, mypy-strict data contract.

⚠️ US3, US4, and US5 depend on this phase. US1 is independent and can proceed in parallel.

- [x] T002 Define `GraphEntry` TypedDict (`depth`, `kind`, `name`, `uuid`, `enabled`, `external_id`, `linked_url`, `has_descendants`) and `RelationEntry` TypedDict (`relation_type`, `target_name`, `target_uuid`) in `taxomesh/contrib/django/admin.py`
- [x] T003 Refactor `_flatten_graph` in `taxomesh/contrib/django/admin.py` to return `list[GraphEntry]`, populate `external_id` (empty string when `None`), `has_descendants` (True if category has items or child categories), and `linked_url: None` (filled later by `graph_view`)

**Checkpoint**: `mypy --strict .` passes. `_flatten_graph` returns `list[GraphEntry]`.

---

## Phase 3: User Story 1 — CLI `--show-relations` (Priority: P1) 🎯 MVP

**Goal**: Add `--show-relations` flag to `taxomesh graph`; outgoing item relations appear
as indented leaves below each item in the Rich tree.

**Independent Test**: `taxomesh graph` omits relations; `taxomesh graph --show-relations`
prints `[relation_type] → target_name` below each item that has outgoing relations.

> ⚠️ **TDD**: Write T004, verify it FAILS, then implement T005–T006.

### Tests (write first — must FAIL before implementation)

- [x] T004 [P] [US1] Write failing tests for `--show-relations` in `tests/adapters/cli/test_graph_output.py`:
  - `test_graph_no_show_relations_omits_relation_lines` — asserts no relation text in default output
  - `test_graph_show_relations_prints_relation_lines` — asserts relation type + target name appear
  - `test_graph_show_relations_no_op_when_no_relations` — asserts output unchanged with flag when taxonomy has no relations

### Implementation

- [x] T005 [US1] Add `show_relations: bool = typer.Option(False, "--show-relations/--no-show-relations")` parameter to `graph_cmd` in `taxomesh/adapters/cli/main.py`
- [x] T006 [US1] Update `_add_graph_node` in `taxomesh/adapters/cli/main.py` to accept `relations: dict[UUID, list[ItemRelationLink]] | None = None` and `item_lookup: dict[UUID, Item] | None = None`; when `show_relations` is True in `graph_cmd`, pre-fetch all outgoing `ItemRelationLink` records for every item in the graph (via `svc.list_item_relations`) into a `dict[UUID, list[ItemRelationLink]]` and resolve target names with `svc.get_item`; render each relation as a dim leaf `[relation_type] → target_name`

**Verify**: `pytest tests/adapters/cli/test_graph_output.py` → all pass.

**Checkpoint**: US1 fully functional and independently testable.

---

## Phase 4: User Story 2 — Admin Link Underlines (Priority: P2)

**Goal**: Confirm (regression test) that no link underlines appear in the admin graph.
Implementation is already present — this phase produces the test artefact only.

> ⚠️ **TDD note**: FR-004 is already implemented. T007 should PASS immediately.
> Treat as a regression guard, not a new implementation.

### Tests

- [x] T007 [P] [US2] Write regression test `test_graph_links_have_no_underline` in `tests/contrib/django/test_admin_graph.py` — read `graph.html` template source and assert `text-decoration: none` is present for `.taxomesh-label a`

**Checkpoint**: US2 verified via passing regression test.

---

## Phase 5: User Story 3 — Admin Expand/Collapse (Priority: P3)

**Goal**: Every non-empty category gets a `[+]`/`[-]` clickable control; clicking it
hides/shows all descendant entries via vanilla JS (no page reload).

**Independent Test**: Load graph page HTML — verify each non-empty category row contains
a button with class `taxomesh-toggle`. JS click simulation collapses/expands descendants.

> ⚠️ **TDD**: Write T008, verify it FAILS, then implement T009.

### Tests (write first — must FAIL before implementation)

- [x] T008 [P] [US3] Write failing tests in `tests/contrib/django/test_admin_graph.py` — class `TestExpandCollapse`:
  - `test_non_empty_category_has_toggle_button` — assert `taxomesh-toggle` button present in response HTML for a category that has items
  - `test_empty_category_has_no_toggle_button` — assert no toggle button for a category with no items and no children
  - `test_leaf_item_without_relations_has_no_toggle_button` — assert items without outgoing relations show no toggle

### Implementation

- [x] T009 [US3] Add `[+]`/`[-]` toggle buttons and vanilla JS expand/collapse to `taxomesh/contrib/django/templates/admin/taxomesh_contrib_django/graph.html`:
  - Render `<button class="taxomesh-toggle">[-]</button>` before the label for each entry where `entry.has_descendants` is True
  - Assign `data-idx="{{ forloop.counter0 }}"` to each `.taxomesh-entry` div
  - Add inline `<script>` that builds a `parentIdx[]` array from depth values on page load; clicking a toggle button adds `data-collapsed-by="N"` to all descendant entries; CSS `[data-collapsed-by] { display: none }` hides them; clicking again removes the attribute and toggles button text between `[+]` and `[-]`

**Verify**: `pytest tests/contrib/django/test_admin_graph.py::TestExpandCollapse` → all pass.

**Checkpoint**: US3 fully functional and independently testable.

---

## Phase 6: User Story 4 — Admin Item Relations Toggle (Priority: P4)

**Goal**: A checkbox at the top of the graph page toggles visibility of item relation rows
without a page reload. Relations are pre-loaded into the template context; JS controls
their visibility. Default: OFF (hidden).

**Independent Test**: Load graph page — no relation rows visible. Toggle checkbox ON — each
item with relations shows its outgoing relations. Toggle OFF — relations hidden again.

> ⚠️ **TDD**: Write T010, verify it FAILS, then implement T011–T012.

### Tests (write first — must FAIL before implementation)

- [x] T010 [P] [US4] Write failing tests in `tests/contrib/django/test_admin_graph.py` — class `TestRelationsToggle`:
  - `test_relations_toggle_checkbox_present` — assert `<input type="checkbox" id="taxomesh-show-relations">` in response HTML
  - `test_item_relations_in_context` — assert `item_relations` key is in template context and contains relation data for items that have outgoing links
  - `test_relation_rows_hidden_by_default` — assert relation rows have CSS class or style that hides them by default
  - `test_item_with_relations_has_toggle_button_when_relations_loaded` — assert item entry with relation data includes a toggle button

### Implementation

- [x] T011 [US4] Update `graph_view` in `taxomesh/contrib/django/admin.py` to build `item_relations: dict[str, list[RelationEntry]]` — for each item entry in `entries`, call `svc.list_item_relations(UUID(entry["uuid"]))` and populate `item_relations[entry["uuid"]]` with `RelationEntry` dicts (`relation_type`, `target_name` via `svc.get_item`, `target_uuid`); pass `item_relations` in the template context
- [x] T012 [US4] Update `taxomesh/contrib/django/templates/admin/taxomesh_contrib_django/graph.html`:
  - Add `<label><input type="checkbox" id="taxomesh-show-relations"> Show item relations</label>` above the graph div
  - For each item entry, render a hidden `.taxomesh-relations` sub-block listing each `RelationEntry` from `item_relations[entry.uuid]` (hidden by default via `display:none`)
  - For items that have relations data, render a `[+]`/`[-]` toggle button (only shown when relations are visible; JS controls this)
  - Add JS: when `#taxomesh-show-relations` changes, toggle class `taxomesh-relations-visible` on `#taxomesh-graph`; CSS `.taxomesh-relations-visible .taxomesh-relations { display: block }` reveals relation blocks; when unchecked, reset all per-item relation expand/collapse state

**Verify**: `pytest tests/contrib/django/test_admin_graph.py::TestRelationsToggle` → all pass.

**Checkpoint**: US4 fully functional and independently testable.

---

## Phase 7: User Story 5 — Admin Icon-Link to Configured Django Model (Priority: P5)

**Goal**: When `TAXOMESH_LINKED_MODEL` Django setting is configured, each item/category
with a non-empty `external_id` shows a `↗` icon-link to its corresponding model instance's
admin change page. No icon when setting absent, `external_id` empty, or instance not found.

**Independent Test**: With `TAXOMESH_LINKED_MODEL = "myapp.Content"` in settings and a
matching instance, the icon-link appears; for items without `external_id` or missing
instances, no icon appears; with setting absent, no icons anywhere.

> ⚠️ **TDD**: Write T013, verify it FAILS, then implement T014–T016.

### Tests (write first — must FAIL before implementation)

- [x] T013 [P] [US5] Write failing tests in `tests/contrib/django/test_admin_graph.py` — class `TestLinkedModel`:
  - `test_icon_link_appears_when_model_configured_and_external_id_set` — with `settings.TAXOMESH_LINKED_MODEL` pointing to a test model and an item whose `external_id` matches a pk, assert `↗` link is present in response HTML
  - `test_no_icon_when_external_id_absent` — assert no `↗` for items without `external_id`
  - `test_no_icon_when_setting_absent` — assert no `↗` when `TAXOMESH_LINKED_MODEL` not in settings
  - `test_no_icon_when_instance_not_found` — assert no `↗` when setting is valid but no instance with the given pk exists (graceful degradation)

### Implementation

- [x] T014 [US5] Add `TAXOMESH_LINKED_MODEL_SETTING: Final[str] = "TAXOMESH_LINKED_MODEL"` constant to `taxomesh/contrib/django/admin.py` (import `Final` from `typing`)
- [x] T015 [US5] Update `graph_view` in `taxomesh/contrib/django/admin.py` to resolve `linked_url` for each `GraphEntry`: read `getattr(settings, TAXOMESH_LINKED_MODEL_SETTING, None)`; use `django.apps.apps.get_model()` to resolve the model; for each entry with a non-empty `external_id`, attempt `linked_model.objects.get(pk=entry["external_id"])` and set `entry["linked_url"]` to `reverse(f"admin:{app_label}_{model_name}_change", args=[entry["external_id"]])`; silently set `linked_url = None` on any exception (`LookupError`, `ValueError`, `DoesNotExist`, `Exception`)
- [x] T016 [US5] Render icon-link in `taxomesh/contrib/django/templates/admin/taxomesh_contrib_django/graph.html`: after the `<span class="taxomesh-label">` for each entry, add `{% if entry.linked_url %}<a href="{{ entry.linked_url }}" title="View in admin" style="text-decoration:none; font-size:0.85em;">↗</a>{% endif %}`

**Verify**: `pytest tests/contrib/django/test_admin_graph.py::TestLinkedModel` → all pass.

**Checkpoint**: US5 fully functional and independently testable.

---

## Phase 8: Polish & Quality Gates

**Purpose**: Ensure all quality gates pass before PR.

- [x] T017 Run `ruff check .` and fix any linting violations in modified files
- [x] T018 Run `ruff format --check .` and fix any formatting issues in modified files
- [x] T019 Run `mypy --strict .` and fix all type errors (focus on `GraphEntry`, `RelationEntry`, updated function signatures)
- [x] T020 Run `pytest --cov=taxomesh --cov-fail-under=80` — full suite must pass with ≥ 80% coverage

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on T001 (Phase 1 complete)
- **US1 (Phase 3)**: Independent — can run in parallel with Phase 2 (touches only CLI files)
- **US2 (Phase 4)**: Depends on T001 (test file exists); can run in parallel with Phase 2/3
- **US3 (Phase 5)**: Depends on Phase 2 complete (needs `GraphEntry.has_descendants`)
- **US4 (Phase 6)**: Depends on Phase 2 complete; benefits from US3 (toggle buttons reused)
- **US5 (Phase 7)**: Depends on Phase 2 complete; independent of US3/US4
- **Polish (Phase 8)**: All prior phases complete

### User Story Dependencies

| Story | Depends on | Parallel with |
|-------|------------|---------------|
| US1 | T001 (test file) | Phase 2, US2 |
| US2 | T001 (test file) | Phase 2, US1 |
| US3 | Phase 2 complete | US5 |
| US4 | Phase 2 complete | US5 |
| US5 | Phase 2 complete | US3, US4 |

### Within Each User Story

1. Test task — write and verify it **FAILS**
2. Implementation tasks — in listed order
3. Re-run tests — verify they **PASS**
4. `mypy --strict .` check on modified files

---

## Parallel Execution Examples

### Phase 2 + US1 (after T001)

```
Parallel A: T002 → T003   (admin TypedDicts + _flatten_graph refactor)
Parallel B: T004           (CLI test — different file, independent)
```

### US3 + US5 (after Phase 2)

```
Parallel A: T008 → T009   (expand/collapse test + impl)
Parallel B: T013           (icon-link test — different test class, independent)
```

---

## Implementation Strategy

### MVP (US1 only — CLI `--show-relations`)

1. Complete T001 (setup)
2. Complete T004 (test — verify FAIL)
3. Complete T005–T006 (implementation)
4. Verify tests pass → **MVP deliverable**

### Incremental Admin Delivery

1. T001–T003 (setup + foundational)
2. T007 (US2 regression — passes immediately)
3. T008–T009 (US3 expand/collapse)
4. T010–T012 (US4 relations toggle)
5. T013–T016 (US5 icon-links)
6. T017–T020 (quality gates)

---

## Notes

- All test tasks must be verified to FAIL before their corresponding implementation tasks run (CLAUDE.md TDD requirement)
- `text-decoration: none` (FR-004) is already in the template; T007 is a regression guard, not new work
- `item_relations` is always loaded server-side (all relation data sent to template); JS controls visibility — no AJAX required
- `linked_url` resolution is silent on failure — no exceptions propagate to the user
- Commit after each user story phase (after quality gates pass for that phase)
