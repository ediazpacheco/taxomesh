# Implementation Plan: Django CLI Compatibility and Admin Graph View

**Branch**: `015-django-cli-admin` | **Date**: 2026-03-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/015-django-cli-admin/spec.md`

## Summary

Two independent deliverables:

1. **CLI + Django fix (P1)**: When `taxomesh.toml` has `type = "django"` and
   `DJANGO_SETTINGS_MODULE` is not set, `DjangoRepository.__init__` currently lets Django's
   `ImproperlyConfigured` escape uncaught — producing a cryptic internal traceback. Fix:
   catch `ImproperlyConfigured` inside `DjangoRepository.__init__` and re-raise as
   `TaxomeshRepositoryError` with a message that names the fix. The existing `build()` error
   handler in `cli/config.py` already catches `TaxomeshRepositoryError` and exits cleanly.
   Additionally, update `--show-config` to correctly emit `type = "django"` + `using = "<alias>"`
   (instead of a file path) for the django backend.

2. **Named constants (P1 co-deliverable, Principle X)**: Introduce `DJANGO_REPO_TYPE` in
   `django_repository.py` (matching the existing `YAML_REPO_TYPE` / `JSON_REPO_TYPE` pattern),
   replace all bare `"django"` string literals, and introduce `SUPPORTED_REPO_TYPES` as the
   single authoritative list of all valid `repository.type` values.

3. **Django admin graph view (P2)**: Register a custom `/admin/taxomesh_contrib_django/graph/`
   URL via `CategoryModelAdmin.get_urls()`. Link it from the app index via a template override
   at `taxomesh/contrib/django/templates/admin/taxomesh_contrib_django/app_index.html`. The
   view calls `TaxomeshService.get_graph()` and renders a server-side HTML tree using
   `admin/taxomesh_contrib_django/graph.html`, which extends Django admin's `base_site.html`.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Typer ≥ 0.12 (CLI), Django ≥ 4.2 (optional — admin view), stdlib `tomllib`
**Storage**: Django ORM (optional backend) — no new storage changes
**Testing**: pytest, pytest-django
**Target Platform**: CLI (cross-platform) + Django admin (web)
**Project Type**: Library + CLI tool + optional Django contrib app
**Performance Goals**: N/A — CLI startup output; admin page is synchronous single-page load
**Constraints**: `--show-config` must NOT instantiate any repository; Django not required at CLI import time; no external CSS/JS libraries in the admin template
**Scale/Scope**: 5 files modified, 2 new template files, 1 new test file, 2 existing test files updated

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I — Hexagonal (dependency direction) | ✅ PASS | `cli/config.py` is the outermost adapter layer. Importing `DJANGO_REPO_TYPE` from sibling adapter `django_repository.py` is adapter→adapter (same layer). `admin.py` (contrib/django) is also outermost adapter. No inward dependency violations. |
| I — Adapter defaults stay in adapters | ✅ PASS | Default `using` alias (`"default"`) stays in `django_repository.py` (`_USING_DEFAULT`). `config.py` imports it; does not redefine it. |
| I — Composition-root exception | ✅ PASS | All Django imports inside `DjangoRepository.__init__` and methods remain lazy (inside function bodies with `# noqa: PLC0415`). The new `ImproperlyConfigured` catch is a nested import inside the same guard. `DJANGO_REPO_TYPE` import in `django_repository.py` is a pure string constant — no Django dependency at module level. |
| II — TaxomeshService is single public facade | ✅ PASS | Admin graph view instantiates `TaxomeshService` directly (as any consumer would). No new service methods added. |
| III — Repository as Protocol | ✅ PASS | No changes to the protocol. |
| IV — Pydantic models + mypy strict | ✅ PASS | No new domain models. `taxomesh/contrib/django/` is already excluded from mypy strict in `pyproject.toml`. All non-excluded new code typed fully. |
| V — Custom exception hierarchy | ✅ PASS | `DjangoRepository.__init__` re-raises `ImproperlyConfigured` as `TaxomeshRepositoryError` — consistent with the existing pattern for `ImportError`. No silent failures. |
| VIII — Quality gates non-negotiable | ✅ PASS | Full gate run required before PR. `contrib/django/` excluded from coverage by `pyproject.toml [tool.coverage.run]`; overall coverage must remain ≥ 80%. |
| X — Named constants, no magic literals | ✅ PASS | `DJANGO_REPO_TYPE` defined in `django_repository.py`. `SUPPORTED_REPO_TYPES` defined in `cli/config.py`. Bare `"django"` literals in `service.py` and `config.py` replaced. |
| XI — OO by default | ✅ PASS | Admin graph view implemented as a method on `CategoryModelAdmin`. `dump_config()` remains a pure stateless utility function (no state — exempt by constitution clause). |

**Gate result: ALL PASS — proceed to Phase 0.**

## Project Structure

### Documentation (this feature)

```text
specs/015-django-cli-admin/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/
│   ├── cli.md           # Phase 1 output — --show-config django behaviour
│   └── admin.md         # Phase 1 output — admin graph view URL/template contract
└── tasks.md             # Phase 2 output (/speckit.tasks command — NOT created here)
```

### Source Code (files touched by this feature)

```text
taxomesh/
├── adapters/
│   ├── repositories/
│   │   └── django_repository.py       # MODIFIED: add DJANGO_REPO_TYPE constant;
│   │                                  #   catch ImproperlyConfigured in __init__;
│   │                                  #   replace _USING_DEFAULT import ref in _build_django
│   └── cli/
│       └── config.py                  # MODIFIED: import DJANGO_REPO_TYPE; add SUPPORTED_REPO_TYPES;
│                                      #   update dump_config() for django type (using vs path);
│                                      #   update _resolve_effective_config() for django
├── application/
│   └── service.py                     # MODIFIED: lazy-import DJANGO_REPO_TYPE alongside DjangoRepository;
│                                      #   replace bare "django", "yaml", "json" keys in _REPO_BUILDERS
└── contrib/
    └── django/
        ├── admin.py                   # MODIFIED: add graph_view() method on CategoryModelAdmin;
        │                              #   override get_urls() to register /graph/ URL
        └── templates/
            └── admin/
                └── taxomesh_contrib_django/
                    ├── app_index.html # NEW: extends admin/app_index.html; adds Graph link
                    └── graph.html     # NEW: extends admin/base_site.html; renders taxonomy tree

tests/
├── adapters/
│   └── cli/
│       └── test_config_dump.py        # MODIFIED: update invariant tests; add django-type --show-config tests
└── contrib/
    └── django/
        ├── test_admin.py              # MODIFIED: add graph view tests (URL accessible, renders tree,
        │                              #   handles empty state, handles DB error)
        └── test_cli_django_error.py   # NEW: test CLI exits with friendly message when Django not configured
```

**Structure Decision**: Single project layout. No new packages or modules. The feature touches the
existing adapter, application, and contrib layers. Template directory added under `contrib/django/`
using Django's standard app-directories template discovery.

## Key Design Decisions

### Decision 1 — ImproperlyConfigured catch location

**Chosen**: Catch `django.core.exceptions.ImproperlyConfigured` inside `DjangoRepository.__init__`
(same guard as the existing `ImportError` catch) and re-raise as `TaxomeshRepositoryError`.

**Rationale**: Keeps all Django error handling co-located in the adapter that owns the Django dependency.
The CLI's `build()` function already handles `TaxomeshRepositoryError` correctly — no changes to
`main.py` or `build()` needed.

**Catch pattern**: A nested try/import inside the outer `try` block — import
`ImproperlyConfigured` lazily to avoid module-level Django dependency:

```python
try:
    from taxomesh.contrib.django.models import (CategoryModel, ...)  # noqa: PLC0415
except ImportError as exc:
    raise TaxomeshRepositoryError("Django is not installed. Run: pip install taxomesh[django]") from exc
except Exception as exc:
    try:
        from django.core.exceptions import ImproperlyConfigured  # noqa: PLC0415
        if isinstance(exc, ImproperlyConfigured):
            raise TaxomeshRepositoryError(
                "Django settings are not configured. "
                "Set the DJANGO_SETTINGS_MODULE environment variable before running "
                "taxomesh with type = 'django'."
            ) from exc
    except ImportError:
        pass
    raise
```

### Decision 2 — SUPPORTED_REPO_TYPES placement

**Chosen**: Define `SUPPORTED_REPO_TYPES: Final[tuple[str, ...]]` in `cli/config.py` by
importing `DJANGO_REPO_TYPE` from `django_repository.py` at module level (alongside the
existing `YAML_REPO_TYPE` / `JSON_REPO_TYPE` imports).

**Rationale**: `config.py` is the outermost adapter layer and already imports per-adapter
type constants. Importing `DJANGO_REPO_TYPE` from `django_repository.py` at module level is
safe — `django_repository.py` has no Django imports at module level (all deferred inside
`__init__` and methods). No circular import risk.

**service.py uses a different approach**: `_build_repo_from_config` lazily imports `YAML_REPO_TYPE`,
`JSON_REPO_TYPE`, `DJANGO_REPO_TYPE` alongside their respective adapter classes to replace the
three bare string literals in `_REPO_BUILDERS`. The default `"yaml"` literal in
`section.get("type", "yaml")` is also replaced with `YAML_REPO_TYPE`.

### Decision 3 — dump_config() signature for django type

**Chosen**: Rename the second parameter from `repo_path` to `repo_detail`. `dump_config` checks
`repo_type` and renders either `path = "..."` (yaml/json) or `using = "..."` (django).

**CONFIG_KEYS update**: Add `"repository.using"` to `CONFIG_KEYS`. Update the existing
invariant test from strict equality (`==`) to subset check (`⊆`): "every key in the dump
output must appear in CONFIG_KEYS." Add new tests for the django-type dump behaviour.

### Decision 4 — Admin graph URL registration and main index link

**Chosen**: Override `CategoryModelAdmin.get_urls()` to prepend
`path("graph/", self.admin_site.admin_view(self.graph_view), name="taxomesh_contrib_django_graph")`
to the standard URLs.

**Link on main admin index**: Add a `CategoryGraphProxy` proxy model (proxy of `CategoryModel`,
`verbose_name_plural = "Graph"`) and a `CategoryGraphProxyAdmin` that:
- Allows only `has_view_permission` (for staff); all write permissions return `False`
- Overrides `changelist_view` to 302-redirect to the `taxomesh_contrib_django_graph` named URL

This surfaces "Graph" as a row in the Taxomesh section on `/admin/` with zero extra clicks.
One new migration (`0002_categorygraphproxy.py`) creates the content type entry (no new DB table).

**Link from app index**: The existing `app_index.html` template override also provides the Graph
link at the app-index level — consistent and harmless.

**Rationale**: No `AdminSite` subclassing required. Works transparently for any consumer that
has `taxomesh.contrib.django` in `INSTALLED_APPS`.

### Decision 5 — Admin graph view implementation

**Chosen**: `CategoryModelAdmin.graph_view(request)` method:
1. Instantiates `DjangoRepository()` and `TaxomeshService(repository=repo)`
2. Calls `service.get_graph()`
3. Catches `TaxomeshError` and passes error message to template context
4. Renders `admin/taxomesh_contrib_django/graph.html` with the graph data

**Access control**: Uses `self.admin_site.admin_view()` wrapper, which enforces `is_staff`
and active session — same access control as any other admin view.

## Complexity Tracking

> No constitution violations to justify.
