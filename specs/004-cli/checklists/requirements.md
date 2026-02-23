# Requirements Checklist: CLI (004-cli)

**Date**: 2026-02-23
**Last Updated**: 2026-02-23 (rev 3)
**Source**: `specs/004-cli/spec.md`

---

## Functional Requirements

### CLI entry point

- [x] **FR-001** — `taxomesh` entry point registered in `[project.scripts]`
- [x] **FR-002** — CLI implemented using Typer
- [x] **FR-003** — Three sub-command groups: `category`, `item`, `tag`
- [x] **FR-004** — `category`/`tag` groups: `list`, `add`, `delete`, `update`; `item` group also has `add-to-category`, `add-to-tag`
- [x] **FR-005** — All commands support `--help`

### Configuration

- [x] **FR-006** — CLI reads `taxomesh.toml` from CWD; absence is not an error
- [x] **FR-007** — Default config: `type = "json"`, `path = "taxomesh.json"`
- [x] **FR-008** — Root `--config <path>` option accepted
- [x] **FR-009** — Invalid TOML → descriptive stderr + non-zero exit

### Category sub-commands

- [x] **FR-010** — `category add --name X [--description Y] [--parent-id UUID [--sort-index INT]]`
- [x] **FR-011** — `category list [--parent-id UUID]`; without filter prints all; with filter prints children ordered by `sort_index`; exit 0 always
- [x] **FR-012** — `category delete <id>` deletes and prints confirmation
- [x] **FR-013** — `category update <id>` requires ≥1 of `--name`, `--description`, `--parent-id`

### Item sub-commands

- [x] **FR-014** — `item add --external-id X [--category-id UUID [--sort-index INT]] [--tag-id UUID]`; `--external-id` required
- [x] **FR-015** — `item list [--category-id UUID]`; without filter prints all; with filter prints items ordered by `sort_index`; exit 0 always
- [x] **FR-016** — `item delete <id>` deletes and prints confirmation
- [x] **FR-017** — `item update <id> [--enable|--disable] [--category-id UUID [--sort-index INT]] [--tag-id UUID]`; ≥1 option required
- [x] **FR-018** — `item add-to-category ITEM_ID --category-id UUID [--sort-index INT]`; idempotent
- [x] **FR-019** — `item add-to-tag ITEM_ID --tag-id UUID`; idempotent

### Tag sub-commands

- [x] **FR-020** — `tag add --name X` creates and prints tag
- [x] **FR-021** — `tag list` prints all tags; exit 0 always
- [x] **FR-022** — `tag delete <id>` deletes and prints confirmation
- [x] **FR-023** — `tag update <id> --name X` renames and prints tag

### Error handling

- [x] **FR-024** — Any `TaxomeshError` → stderr message + exit 1
- [x] **FR-025** — Any unexpected exception → stderr message + exit 1

### Domain model changes

- [x] **FR-026** — `Category.description: Annotated[str, Field(max_length=100_000)] = ""`; `BeforeValidator` coerces `None` → `""`

### Service layer extensions

- [x] **FR-027** — `TaxomeshService.update_category(category_id, name, description) -> Category`
- [x] **FR-028** — `TaxomeshService.update_item(item_id, enabled) -> Item`
- [x] **FR-029** — `TaxomeshService.update_tag(tag_id, name) -> Tag`
- [x] **FR-030** — `TaxomeshService.delete_tag(tag_id) -> None`
- [x] **FR-031** — `TaxomeshService.place_item_in_category(item_id, category_id, sort_index=0) -> ItemParentLink`; idempotent
- [x] **FR-032** — `TaxomeshService.list_items(*, category_id=None) -> list[Item]`; filtered + sorted by `sort_index` when `category_id` provided; raises `TaxomeshCategoryNotFoundError` for unknown category
- [x] **FR-033** — `TaxomeshService.list_categories(*, parent_id=None) -> list[Category]`; filtered + sorted by `sort_index` when `parent_id` provided; raises `TaxomeshCategoryNotFoundError` for unknown parent

### Repository layer extensions

- [x] **FR-034** — `TaxomeshRepositoryBase.delete_tag(tag_id: UUID) -> bool` (16th method)
- [x] **FR-035** — `TaxomeshRepositoryBase.save_item_parent_link(link: ItemParentLink) -> None` (17th); upsert on `(item_id, category_id)`
- [x] **FR-036** — `TaxomeshRepositoryBase.list_item_parent_links() -> list[ItemParentLink]` (18th)
- [x] **FR-037** — `JsonRepository` implements `delete_tag`, `save_item_parent_link`, `list_item_parent_links`

### README

- [x] **FR-038** — README updated: CLI section appears before Python API quick start

### Tests

- [x] **FR-039** — `tests/test_cli.py` covers: all sub-commands (happy path), all not-found error paths, config file loading, default-config fallback, inline `--category-id`/`--tag-id` on `item add`, `item add-to-category`, `item add-to-tag`, `category add --parent-id`, `category list --parent-id`, `item list --category-id`; uses Typer's `CliRunner`

---

## Quality Gates

- [x] `ruff check .` — zero violations
- [x] `ruff format --check .` — no formatting issues
- [x] `mypy --strict .` — zero type errors
- [x] `pytest --cov=taxomesh --cov-fail-under=80` — all tests pass, coverage ≥ 80%

---

## Success Criteria

- [x] **SC-001** — `taxomesh category add --name "Music"` exits 0, prints category with UUID
- [x] **SC-002** — `taxomesh category add --name "Jazz" --parent-id <id>` creates category and parent link
- [x] **SC-003** — `taxomesh item add --external-id 99` exits 0, prints item
- [x] **SC-004** — `taxomesh item add --external-id 1 --category-id <id>` places item in category
- [x] **SC-005** — `taxomesh item add-to-category ITEM_ID --category-id <id>` places existing item
- [x] **SC-006** — `taxomesh item add-to-tag ITEM_ID --tag-id <id>` assigns tag to existing item
- [x] **SC-007** — `taxomesh tag add --name "live"` exits 0, prints tag
- [x] **SC-008** — Command targeting non-existent entity exits 1, stderr has typed error message
- [x] **SC-009** — Valid `taxomesh.toml` causes correct repo path to be used
- [x] **SC-010** — Absent `taxomesh.toml` → defaults used, no error
- [x] **SC-011** — All `--help` flags produce output
- [x] **SC-012** — All quality gates pass
- [x] **SC-013** — `taxomesh category update <id>` with no options exits non-zero
- [x] **SC-014** — `taxomesh category list --parent-id <id>` returns children ordered by sort_index
- [x] **SC-015** — `taxomesh item list --category-id <id>` returns items ordered by sort_index
