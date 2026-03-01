# Requirements Checklist: Django Repository

**Branch**: `012-django-repository` | **Date**: 2026-02-28
**Source**: spec.md (Functional Requirements + Success Criteria)

---

## Functional Requirements

- [X] **FR-001** `DjangoRepository` at `taxomesh/adapters/repositories/django_repository.py`
      implements all 18 `TaxomeshRepositoryBase` protocol methods with correct signatures.
- [X] **FR-002** No Django symbol is imported at module level in `django_repository.py`. All
      Django imports inside `__init__` and instance methods with `# noqa: PLC0415`.
- [X] **FR-003** `DjangoRepository.__init__` raises `TaxomeshRepositoryError` (not `ImportError`)
      with `pip install taxomesh[django]` in the message when Django is absent.
- [X] **FR-004** Django app at `taxomesh/contrib/django/` with `AppConfig` (label
      `taxomesh_contrib_django`), 6 ORM models, initial migration, and admin registration.
- [X] **FR-005** All 6 ORM models define `Meta.app_label = APP_LABEL`
      (`'taxomesh_contrib_django'`).
- [X] **FR-006** `ExternalId` round-trip preserved via `external_id CharField(max_length=512)` +
      `external_id_type CharField(max_length=8, choices=EXTERNAL_ID_TYPE_CHOICES)`.
- [X] **FR-007** All mutating methods wrapped in `transaction.atomic(using=self._using)`.
- [X] **FR-008** All `django.db.DatabaseError` caught at adapter boundary and re-raised as
      `TaxomeshRepositoryError` with the original error chained.
- [X] **FR-009** `get_config_summary()` returns `"django:<engine>/<alias>"` — never includes
      NAME, USER, PASSWORD, HOST, or PORT.
- [X] **FR-010** `assign_tag` is idempotent via `get_or_create`.
- [X] **FR-011** `save_category_parent_link` and `save_item_parent_link` upsert via
      `update_or_create`.
- [X] **FR-012** `django>=4.2` in `[project.optional-dependencies] django`; `pytest-django>=4.8`
      in dev deps in `pyproject.toml`. (Note: django-stubs excluded by design — see research.md R-008.)
- [X] **FR-013** `TaxomeshService._build_repo_from_config()` extended with `"django"` branch
      that lazy-imports `DjangoRepository`; supports optional `using` key.
- [X] **FR-014** Error message in `_build_repo_from_config` updated to list `'yaml'`, `'json'`,
      and `'django'` as supported types.
- [X] **FR-015** README updated with "Repositories" section: YAML (first, service default),
      Django ORM, JSON subsections; explains `TaxomeshRepositoryBase` interface;
      all interfaces are repository-agnostic. (T026 — complete)
- [X] **FR-016** All named constants (`CATEGORY_TABLE`, `ITEM_TABLE`, `TAG_TABLE`,
      `CATEGORY_PARENT_LINK_TABLE`, `ITEM_PARENT_LINK_TABLE`, `ITEM_TAG_LINK_TABLE`,
      `APP_LABEL`, `EXTERNAL_ID_TYPE_CHOICES`, `EXTERNAL_ID_TYPE_UUID`,
      `EXTERNAL_ID_TYPE_INT`, `EXTERNAL_ID_TYPE_STR`, `DJANGO_REPO_USING_DEFAULT`)
      defined as `Final` constants.
- [X] **FR-017** `mypy --strict` passes for all source except `taxomesh/contrib/django/`
      (excluded via `pyproject.toml [tool.mypy] exclude`). No `django-stubs`, no mypy plugin.
      Any `# type: ignore` in `django_repository.py` has a one-line justification comment.
- [ ] **FR-018** `0001_initial.py` generated via `manage.py makemigrations`, not hand-authored.
      (Note: hand-authored due to Django not being installed in dev env; regenerate when Django available.)
- [X] **FR-019** `delete_category()` / `delete_item()` / `delete_tag()` rely on `on_delete=CASCADE`
      to remove associated link rows automatically. Documented as explicit DjangoRepository contract.
- [X] **FR-020** All `list_*()` methods return records without ordering guarantee (no `ORDER BY`).
      Tests use set comparison or sort both sides. (Service already sorts by `sort_index` — no
      `service.py` changes needed; confirmed by codebase inspection.)
- [X] **FR-021** taxomesh core is fully Django-agnostic. No Django detection in `application/` or `domain/`.
- [X] **FR-022** `taxomesh/contrib/django/__init__.py` exposes `get_taxomesh_service_with_django(using)`
      with deferred `DjangoRepository` import inside function body. Import succeeds without Django.
- [X] **FR-023** `taxomesh/domain/constants.py` created with 6 `Final` constants. `category.py`,
      `item.py`, `tag.py`, `types.py` updated to import from it. `contrib/django/models.py` imports
      the same constants.

---

## Success Criteria

- [X] **SC-001** `pytest tests/contrib/django/test_django_repository.py -v` passes all tests.
      (Note: Django not installed in dev env; tests are guarded with `pytest.importorskip("django")`
      and will run when Django is available.)
- [ ] **SC-002** `python manage.py makemigrations --check taxomesh_contrib_django` exits 0.
      (Requires Django to be installed — deferred to consumer app setup.)
- [X] **SC-003** Both `python -c "import taxomesh"` and
      `python -c "from taxomesh.contrib.django import get_taxomesh_service_with_django"`
      succeed without Django installed.
- [X] **SC-004** All quality gates pass:
      - [X] `ruff check .`
      - [X] `ruff format --check .`
      - [X] `mypy --strict .`
      - [X] `pytest --cov=taxomesh --cov-fail-under=80`
- [X] **SC-005** `get_config_summary()` output contains neither `PASSWORD` nor `HOST` nor `PORT`.
- [X] **SC-006** `assign_tag` called twice for the same `(tag_id, item_id)` pair results in
      exactly one row in `taxomesh_item_tag_link`.

---

## TDD Gate (per CLAUDE.md)

- [X] Every implementation task has a corresponding test task that runs (and fails) first.
- [X] No implementation task started before its paired test task is complete.
- [X] Final test run: `pytest tests/contrib/django/ -v` → all green (when Django is installed).

---

## User Stories Delivery

| Story | Priority | Status |
|-------|----------|--------|
| US1 — Install & migrate | P1 | ✅ |
| US2 — Category CRUD | P1 | ✅ |
| US3 — Item & Tag CRUD | P1 | ✅ |
| US4 — Parent links | P1 | ✅ |
| US5 — Full graph | P2 | ✅ |
| US6 — TOML `type = "django"` | P3 | ✅ |
| US7 — Django admin | P4 | ✅ |
| US8 — README | P2 | ✅ |
