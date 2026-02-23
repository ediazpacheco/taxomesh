# Requirements Checklist: CLI (004-cli)

**Date**: 2026-02-23
**Last Updated**: 2026-02-23 (rev 3)
**Source**: `specs/004-cli/spec.md`

---

## Functional Requirements

### CLI entry point

- [ ] **FR-001** — `taxomesh` entry point registered in `[project.scripts]`
- [ ] **FR-002** — CLI implemented using Typer
- [ ] **FR-003** — Three sub-command groups: `category`, `item`, `tag`
- [ ] **FR-004** — `category`/`tag` groups: `list`, `add`, `delete`, `update`; `item` group also has `add-to-category`, `add-to-tag`
- [ ] **FR-005** — All commands support `--help`

### Configuration

- [ ] **FR-006** — CLI reads `taxomesh.toml` from CWD; absence is not an error
- [ ] **FR-007** — Default config: `type = "json"`, `path = "taxomesh.json"`
- [ ] **FR-008** — Root `--config <path>` option accepted
- [ ] **FR-009** — Invalid TOML → descriptive stderr + non-zero exit

### Category sub-commands

- [ ] **FR-010** — `category add --name X [--description Y] [--parent-id UUID [--sort-index INT]]`
- [ ] **FR-011** — `category list [--parent-id UUID]`; without filter prints all; with filter prints children ordered by `sort_index`; exit 0 always
- [ ] **FR-012** — `category delete <id>` deletes and prints confirmation
- [ ] **FR-013** — `category update <id>` requires ≥1 of `--name`, `--description`, `--parent-id`

### Item sub-commands

- [ ] **FR-014** — `item add --external-id X [--category-id UUID [--sort-index INT]] [--tag-id UUID]`; `--external-id` required
- [ ] **FR-015** — `item list [--category-id UUID]`; without filter prints all; with filter prints items ordered by `sort_index`; exit 0 always
- [ ] **FR-016** — `item delete <id>` deletes and prints confirmation
- [ ] **FR-017** — `item update <id> [--enable|--disable] [--category-id UUID [--sort-index INT]] [--tag-id UUID]`; ≥1 option required
- [ ] **FR-018** — `item add-to-category ITEM_ID --category-id UUID [--sort-index INT]`; idempotent
- [ ] **FR-019** — `item add-to-tag ITEM_ID --tag-id UUID`; idempotent

### Tag sub-commands

- [ ] **FR-020** — `tag add --name X` creates and prints tag
- [ ] **FR-021** — `tag list` prints all tags; exit 0 always
- [ ] **FR-022** — `tag delete <id>` deletes and prints confirmation
- [ ] **FR-023** — `tag update <id> --name X` renames and prints tag

### Error handling

- [ ] **FR-024** — Any `TaxomeshError` → stderr message + exit 1
- [ ] **FR-025** — Any unexpected exception → stderr message + exit 1

### Domain model changes

- [ ] **FR-026** — `Category.description: Annotated[str, Field(max_length=100_000)] = ""`; `BeforeValidator` coerces `None` → `""`

### Service layer extensions

- [ ] **FR-027** — `TaxomeshService.update_category(category_id, name, description) -> Category`
- [ ] **FR-028** — `TaxomeshService.update_item(item_id, enabled) -> Item`
- [ ] **FR-029** — `TaxomeshService.update_tag(tag_id, name) -> Tag`
- [ ] **FR-030** — `TaxomeshService.delete_tag(tag_id) -> None`
- [ ] **FR-031** — `TaxomeshService.place_item_in_category(item_id, category_id, sort_index=0) -> ItemParentLink`; idempotent
- [ ] **FR-032** — `TaxomeshService.list_items(*, category_id=None) -> list[Item]`; filtered + sorted by `sort_index` when `category_id` provided; raises `TaxomeshCategoryNotFoundError` for unknown category
- [ ] **FR-033** — `TaxomeshService.list_categories(*, parent_id=None) -> list[Category]`; filtered + sorted by `sort_index` when `parent_id` provided; raises `TaxomeshCategoryNotFoundError` for unknown parent

### Repository layer extensions

- [ ] **FR-034** — `TaxomeshRepositoryBase.delete_tag(tag_id: UUID) -> bool` (16th method)
- [ ] **FR-035** — `TaxomeshRepositoryBase.save_item_parent_link(link: ItemParentLink) -> None` (17th); upsert on `(item_id, category_id)`
- [ ] **FR-036** — `TaxomeshRepositoryBase.list_item_parent_links() -> list[ItemParentLink]` (18th)
- [ ] **FR-037** — `JsonRepository` implements `delete_tag`, `save_item_parent_link`, `list_item_parent_links`

### README

- [ ] **FR-038** — README updated: CLI section appears before Python API quick start

### Tests

- [ ] **FR-039** — `tests/test_cli.py` covers: all sub-commands (happy path), all not-found error paths, config file loading, default-config fallback, inline `--category-id`/`--tag-id` on `item add`, `item add-to-category`, `item add-to-tag`, `category add --parent-id`, `category list --parent-id`, `item list --category-id`; uses Typer's `CliRunner`

---

## Quality Gates

- [ ] `ruff check .` — zero violations
- [ ] `ruff format --check .` — no formatting issues
- [ ] `mypy --strict .` — zero type errors
- [ ] `pytest --cov=taxomesh --cov-fail-under=80` — all tests pass, coverage ≥ 80%

---

## Success Criteria

- [ ] **SC-001** — `taxomesh category add --name "Music"` exits 0, prints category with UUID
- [ ] **SC-002** — `taxomesh category add --name "Jazz" --parent-id <id>` creates category and parent link
- [ ] **SC-003** — `taxomesh item add --external-id 99` exits 0, prints item
- [ ] **SC-004** — `taxomesh item add --external-id 1 --category-id <id>` places item in category
- [ ] **SC-005** — `taxomesh item add-to-category ITEM_ID --category-id <id>` places existing item
- [ ] **SC-006** — `taxomesh item add-to-tag ITEM_ID --tag-id <id>` assigns tag to existing item
- [ ] **SC-007** — `taxomesh tag add --name "live"` exits 0, prints tag
- [ ] **SC-008** — Command targeting non-existent entity exits 1, stderr has typed error message
- [ ] **SC-009** — Valid `taxomesh.toml` causes correct repo path to be used
- [ ] **SC-010** — Absent `taxomesh.toml` → defaults used, no error
- [ ] **SC-011** — All `--help` flags produce output
- [ ] **SC-012** — All quality gates pass
- [ ] **SC-013** — `taxomesh category update <id>` with no options exits non-zero
- [ ] **SC-014** — `taxomesh category list --parent-id <id>` returns children ordered by sort_index
- [ ] **SC-015** — `taxomesh item list --category-id <id>` returns items ordered by sort_index
