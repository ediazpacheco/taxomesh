# Tasks: Django CLI Compatibility and Admin Graph View

**Input**: Design documents from `/specs/015-django-cli-admin/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓

**Tests**: TDD is mandatory per `CLAUDE.md`. Every implementation task is preceded by a
failing test task. No implementation begins until its test task is written and confirmed failing.

**Organization**: Phase 2 (Foundational) unblocks both user stories. Phases 3 and 4 are
independently executable once Phase 2 is complete.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no unresolved dependencies)
- **[Story]**: Which user story this task belongs to (`US1`, `US2`)
- Exact file paths are included in every task description

---

## Phase 1: Setup

No project initialization required — no new packages, no new migrations, no new modules.
Template directories are created as part of Phase 4 implementation tasks.

---

## Phase 2: Foundational — Named Constants (Principle X)

**Purpose**: Introduce `DJANGO_REPO_TYPE` and eliminate bare `"django"`/`"yaml"`/`"json"` string
literals from service-layer code. These constants are referenced by both US1 (`config.py`) and
US2 (service initialization path). All subsequent phases depend on this phase being complete.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T001 Write failing test in `tests/service/test_service_config.py` asserting `DJANGO_REPO_TYPE` can be imported from `taxomesh.adapters.repositories.django_repository` and equals `"django"` — confirm test FAILS before proceeding
- [x] T002 Add `DJANGO_REPO_TYPE: Final[str] = "django"` constant to `taxomesh/adapters/repositories/django_repository.py` immediately after `_USING_DEFAULT`, following the `YAML_REPO_TYPE`/`JSON_REPO_TYPE` pattern; run `pytest tests/service/test_service_config.py` and confirm T001 now passes
- [x] T003 In `taxomesh/application/service.py` `_build_repo_from_config`: add `YAML_REPO_TYPE` and `JSON_REPO_TYPE` to the existing lazy imports of `YAMLRepository`/`JsonRepository`; add a separate lazy import of `DJANGO_REPO_TYPE` from `django_repository`; replace bare `"yaml"`, `"json"`, `"django"` string keys in `_REPO_BUILDERS` dict and the `"yaml"` default in `section.get("type", "yaml")` with the named constants; run `pytest tests/service/test_service_config.py` to confirm no regression

**Checkpoint**: `DJANGO_REPO_TYPE` constant exists; no bare type-identifier string literals remain in `service.py`. User story implementation can now begin.

---

## Phase 3: User Story 1 — CLI Django Error Fix + `--show-config` Update (Priority: P1) 🎯 MVP

**Goal**: CLI exits with a clear, actionable message when `type = "django"` is configured but
Django settings are not; `--show-config` correctly outputs `type = "django"` + `using` alias;
`SUPPORTED_REPO_TYPES` is the single source of truth for valid type values.

**Independent Test**: Point `taxomesh.toml` at `type = "django"` without `DJANGO_SETTINGS_MODULE`
set (simulated via mock), run any CLI command, confirm exit code 1 and `"DJANGO_SETTINGS_MODULE"`
appears in stderr. Run `taxomesh --show-config` with a django TOML, confirm output contains
`type = "django"` and `using` key, no `path` key, and valid TOML output.

### Tests for User Story 1

> **Write tests FIRST — confirm they FAIL — then implement**

- [x] T004 [P] [US1] Write tests in `tests/adapters/cli/test_cli_django_error.py` (new file): (a) test that `DjangoRepository()` raises `TaxomeshRepositoryError` with `"DJANGO_SETTINGS_MODULE"` in message when `ImproperlyConfigured` is raised during the model import (mock `taxomesh.contrib.django.models` in `sys.modules` with an object that raises `ImproperlyConfigured` on attribute access); (b) test that the CLI exits with code 1 and `"DJANGO_SETTINGS_MODULE"` in stderr when a `taxomesh.toml` with `type = "django"` causes `TaxomeshRepositoryError` (mock `DjangoRepository` to raise the expected error, write real TOML, invoke via `CliRunner`) — confirm both tests FAIL before proceeding
- [x] T005 [P] [US1] Update `tests/adapters/cli/test_config_dump.py`: (a) change `assert dumped_keys == set(CONFIG_KEYS)` to `assert dumped_keys <= set(CONFIG_KEYS)` in `TestConfigKeysInvariant.test_config_keys_covers_all_dump_output_keys` (invariant relaxed to subset); (b) add `TestDumpConfigDjango` class with tests: `test_dump_config_django_is_valid_toml`, `test_dump_config_django_has_using_key`, `test_dump_config_django_has_no_path_key`, `test_dump_config_django_accepted_values_lists_all_types`; (c) add `TestSupportedRepoTypes` class: `test_supported_repo_types_is_tuple`, `test_supported_repo_types_contains_yaml_json_django` — confirm all new tests FAIL before proceeding
- [x] T006 [P] [US1] Add tests in `tests/adapters/cli/test_config_dump.py` `TestShowConfigPartialAndErrors`: `test_show_config_django_type_has_using_key`, `test_show_config_django_type_has_no_path_key`, `test_show_config_django_type_is_valid_toml`, `test_show_config_django_type_with_custom_using_alias` (write TOML with `using = "secondary"`, assert `using = "secondary"` in output); `test_show_config_django_does_not_require_django_installed` (no `DJANGO_SETTINGS_MODULE` needed for `--show-config`) — confirm tests FAIL before proceeding

### Implementation for User Story 1

- [x] T007 [US1] In `taxomesh/adapters/repositories/django_repository.py` `DjangoRepository.__init__`: extend the existing `try/except ImportError` block with a second `except Exception as exc` clause that lazily imports `django.core.exceptions.ImproperlyConfigured` and, if `exc` is an instance, raises `TaxomeshRepositoryError("Django settings are not configured. Set the DJANGO_SETTINGS_MODULE environment variable before running taxomesh with type = 'django'.")` from `exc`; re-raise the original exception if not `ImproperlyConfigured`; run `pytest tests/adapters/cli/test_cli_django_error.py` and confirm T004 tests pass
- [x] T008 [US1] In `taxomesh/adapters/cli/config.py`: (a) add module-level import `from taxomesh.adapters.repositories.django_repository import DJANGO_REPO_TYPE`; (b) define `SUPPORTED_REPO_TYPES: Final[tuple[str, ...]] = (YAML_REPO_TYPE, JSON_REPO_TYPE, DJANGO_REPO_TYPE)`; (c) add `"repository.using"` to `CONFIG_KEYS`; run `pytest tests/adapters/cli/test_config_dump.py::TestSupportedRepoTypes` and confirm T005 (c) tests now pass
- [x] T009 [US1] In `taxomesh/adapters/cli/config.py` `_resolve_effective_config`: import `_USING_DEFAULT` from `django_repository` alongside the existing adapter imports; add `elif repo_type == DJANGO_REPO_TYPE:` branch that sets `repo_detail = str(section.get("using", _USING_DEFAULT))` and returns `(DJANGO_REPO_TYPE, repo_detail)`; rename the local variable `repo_path` → `repo_detail` throughout the function; update the return type annotation to `tuple[str, str]` (unchanged) — run `pytest tests/adapters/cli/test_config_dump.py::TestShowConfigPartialAndErrors` to confirm T006 tests begin passing
- [x] T010 [US1] In `taxomesh/adapters/cli/config.py` `dump_config`: rename parameter `repo_path` → `repo_detail` in signature and docstring; update accepted-values comment to derive the list from `SUPPORTED_REPO_TYPES` (join with `", "`); add conditional block — when `repo_type == DJANGO_REPO_TYPE`, emit `using = "{repo_detail}"` with its own comment block instead of the `path` key; run `pytest tests/adapters/cli/test_config_dump.py` and confirm all T005 and T006 tests pass
- [x] T011 [US1] Run `pytest tests/adapters/cli/ tests/service/test_service_config.py` — all tests must pass; then run `ruff check taxomesh/adapters/cli/config.py taxomesh/adapters/repositories/django_repository.py taxomesh/application/service.py` and fix any lint issues

**Checkpoint**: US1 complete. CLI exits cleanly with actionable message when Django is not configured. `--show-config` correctly reflects `type = "django"`. `SUPPORTED_REPO_TYPES` is the canonical list.

---

## Phase 4: User Story 2 — Django Admin Taxonomy Graph View (Priority: P2)

**Goal**: A "Graph" page accessible from the taxomesh Django admin section renders the
full taxonomy as a styled, indented HTML tree. Works for any taxonomy size. Handles empty
state and repository errors gracefully.

**Independent Test**: With `taxomesh.contrib.django` in `INSTALLED_APPS` and the admin enabled,
a staff user GETs `/admin/taxomesh_contrib_django/categorymodel/graph/`; the response is
HTTP 200 and the rendered HTML contains category names from the fixture data. An admin user
navigating to the taxomesh app index page sees a "Graph" link.

### Tests for User Story 2

> **Write tests FIRST — confirm they FAIL — then implement**

- [x] T012 [US2] Add test class `TestGraphAdminView` to `tests/contrib/django/test_admin.py`: (a) `test_graph_url_is_registered` — `reverse("admin:taxomesh_contrib_django_graph")` does not raise; (b) `test_graph_view_returns_200_for_staff_user` — create staff `User`, use `django.test.Client`, GET the graph URL, assert status 200; (c) `test_graph_view_shows_category_name` — create a `CategoryModel` record, GET graph URL, assert category name appears in response content; (d) `test_graph_view_empty_state_message` — no categories in DB, GET graph URL, assert "No categories" (or equivalent) in response content; (e) `test_graph_view_shows_error_on_db_failure` — mock `TaxomeshService.get_graph` to raise `TaxomeshError("db error")`, GET graph URL, assert "db error" in response content and status 200 — confirm all five tests FAIL before proceeding

### Implementation for User Story 2

- [x] T013 [US2] In `taxomesh/contrib/django/admin.py`: (a) add module-level helper `_flatten_graph(graph: TaxomeshGraph) -> list[dict[str, object]]` performing depth-first traversal of `graph.roots`, emitting one dict per category (kind=`"category"`) and per item (kind=`"item"`) with keys `depth`, `kind`, `name`, `uuid`, `enabled`, `external_id`; (b) override `get_urls()` on `CategoryModelAdmin` to prepend `path("graph/", self.admin_site.admin_view(self.graph_view), name="taxomesh_contrib_django_graph")` before the standard URLs; (c) add `graph_view(self, request: HttpRequest) -> HttpResponse` method that instantiates `DjangoRepository()` + `TaxomeshService(repository=repo)`, calls `service.get_graph()`, catches `TaxomeshError`, builds context dict (`title`, `entries`, `has_entries`, `error`, `opts`), and renders `admin/taxomesh_contrib_django/graph.html`; add required imports (`TaxomeshService`, `DjangoRepository`, `TaxomeshGraph`, `TaxomeshError`, `CategoryNode`, `HttpRequest`, `HttpResponse`, `TemplateResponse`)
- [x] T014 [P] [US2] Create `taxomesh/contrib/django/templates/admin/taxomesh_contrib_django/graph.html`: extends `admin/base_site.html`; `{% block content %}` renders a `<div class="results">` containing either (a) an error notice `<p class="errornote">{{ error }}</p>` when `error` is set, (b) an empty-state `<p>No categories found…</p>` when `not has_entries`, or (c) a flat list of entry rows — each row is a `<div>` with inline `style="padding-left: {{ entry.depth|mul:1.5 }}rem"` for indentation, showing name, UUID (in a `<small>` tag), and a coloured enabled indicator (✓ green / ✗ red); category rows and item rows use distinct CSS classes (`taxomesh-category`, `taxomesh-item`); the template uses only Django built-in tags and filters
- [x] T015 [P] [US2] Create `taxomesh/contrib/django/templates/admin/taxomesh_contrib_django/app_index.html`: extends `admin/app_index.html`; add `{% block content %}{{ block.super }}` to append a second `<div class="module">` table with caption "Visualization" and one row — link text "Graph", `href="{% url 'admin:taxomesh_contrib_django_graph' %}"`, description "View the full taxonomy as a tree" — styled to match the built-in model links rows; close `{% endblock %}`
- [x] T016 [US2] Run `pytest tests/contrib/django/test_admin.py` — all five T012 tests must pass; fix any failures before proceeding; then run `ruff check taxomesh/contrib/django/admin.py` and fix lint issues

**Checkpoint**: US2 complete. Graph page accessible from admin section. Tree renders for non-empty taxonomy. Empty state and error state handled correctly.

---

## Phase 4b: Amendment — Graph Link on Main Admin Index

**Goal**: Surface the "Graph" link directly on `/admin/` (zero extra clicks) using a proxy model
with a redirect changelist view. No `AdminSite` subclassing; single migration.

- [x] T020 [US2] Write failing tests in `tests/contrib/django/test_admin.py` class `TestGraphProxyAdminIndex`: (a) `test_graph_proxy_model_appears_in_admin_app_list` — GET `/admin/` and assert `b"Graph"` in response; (b) `test_graph_proxy_changelist_redirects` — GET the proxy changelist URL and assert 302 redirect to graph view URL — confirm both FAIL before proceeding
- [x] T021 [US2] Add `CategoryGraphProxy` to `taxomesh/contrib/django/models.py`: proxy of `CategoryModel`, `verbose_name = verbose_name_plural = "Graph"`, `app_label = APP_LABEL`, `proxy = True`
- [x] T022 [US2] Add `CategoryGraphProxyAdmin` to `taxomesh/contrib/django/admin.py`: `has_add/change/delete_permission` return `False`; `has_view_permission` returns `request.user.is_staff`; `changelist_view` 302-redirects to `reverse("admin:taxomesh_contrib_django_graph")`
- [x] T023 [US2] Create `taxomesh/contrib/django/migrations/0002_categorygraphproxy.py` — proxy `CreateModel` migration with `bases=("taxomesh_contrib_django.categorymodel",)`; run `pytest tests/contrib/django/test_admin.py` and confirm all tests pass including T020

**Checkpoint**: "Graph" row visible on `/admin/` in Taxomesh section. Clicking it redirects to the graph page.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [x] T017 Run full quality gate: `ruff check .` → `ruff format --check .` → `mypy --strict .` (note: `taxomesh/contrib/django/` is excluded from mypy strict per `pyproject.toml`) → `pytest --cov=taxomesh --cov-fail-under=80`; fix any issues before proceeding
- [x] T018 Verify `quickstart.md` scenarios: (a) confirm `taxomesh --show-config` with a `type = "django"` TOML file outputs the correct TOML without requiring `DJANGO_SETTINGS_MODULE`; (b) confirm running any CLI command with `type = "django"` and no `DJANGO_SETTINGS_MODULE` (mocked via test) exits 1 with actionable message; (c) confirm graph admin page link is visible in taxomesh section of Django admin
- [x] T019 Propose commit: stage `specs/015-django-cli-admin/` (all files), `taxomesh/adapters/repositories/django_repository.py`, `taxomesh/application/service.py`, `taxomesh/adapters/cli/config.py`, `taxomesh/contrib/django/admin.py`, `taxomesh/contrib/django/templates/` (both new templates), `tests/adapters/cli/test_cli_django_error.py`, `tests/adapters/cli/test_config_dump.py`, `tests/contrib/django/test_admin.py`, `tests/service/test_service_config.py`, `tests/django_settings.py`, `tests/django_urls.py`; present commit message and file list for user approval before committing

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 2 (Foundational)**: No dependencies — start immediately
  - T001 → T002 (sequential: test then implement)
  - T002 → T003 (sequential: constant must exist before replacing literals)
- **Phase 3 (US1)**: Depends on Phase 2 completion (uses `DJANGO_REPO_TYPE`)
  - T004, T005, T006 — independent tests, can be written in parallel [P, P, P]
  - T007 → verify T004 passes
  - T008 → verify T005(c) passes
  - T009, T010 — sequential (both in `config.py`, T009 before T010)
  - T011 — final verification, after T007-T010
- **Phase 4 (US2)**: Independent of Phase 3 (admin view does not use `config.py` changes)
  - T012 — write all five tests before implementing
  - T013, T014 [P], T015 [P] — implementation; T014 and T015 are different files, parallel
  - T016 — verification after T013-T015
- **Phase 5 (Polish)**: Depends on both Phase 3 and Phase 4 completion

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — independent of US2
- **US2 (P2)**: Can start after Phase 2 — independent of US1

### Within Each User Story

- Tests MUST be written and confirmed FAILING before any implementation
- Implementation proceeds in the order: constants → error handling → config functions → dump output
- Each implementation step followed by targeted test run to confirm tests move from FAIL to PASS

### Parallel Opportunities

- T004, T005, T006 can be written simultaneously (different test files / different test classes)
- T014 and T015 are new template files with no code dependency on each other — parallel
- Phase 3 and Phase 4 can proceed in parallel after Phase 2 completes (different files throughout)

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 2: Foundational (T001 → T002 → T003)
2. Complete Phase 3: User Story 1 (T004–T011)
3. **STOP and VALIDATE**: CLI error message works; `--show-config` shows django type correctly
4. Deliver US1 independently — US2 adds value but is not a blocker

### Incremental Delivery

1. Phase 2 → Foundation established
2. Phase 3 → CLI works with Django; `--show-config` complete; Principle X compliant (MVP)
3. Phase 4 → Admin graph view adds visual taxonomy browsing
4. Phase 5 → Quality gates pass; ready for PR

---

## Notes

- [P] tasks = different files or genuinely independent steps, no blocking dependencies
- [Story] label traces each task to its acceptance criteria in spec.md
- `taxomesh/contrib/django/` is excluded from `mypy --strict` and coverage (see `pyproject.toml`)
- Django template `{{ entry.depth|mul:1.5 }}` requires the `mul` filter from `django.template.defaultfilters` or a simple integer depth — if `mul` is not available, compute `style` string in view context instead
- `--show-config` with `type = "django"` MUST NOT require `DJANGO_SETTINGS_MODULE` (contracts/cli.md)
- Run `pytest` after every implementation task, not just at checkpoints
- Commit only when explicitly approved by user (CLAUDE.md governance)
