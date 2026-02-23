# Quickstart: CLI (004-cli)

**Date**: 2026-02-23
**Last Updated**: 2026-02-23 (rev 2)

This guide shows how to use the `taxomesh` command-line interface.
No Python code is required — everything is done from the shell.

---

## Installation

```bash
pip install taxomesh
```

After installation, the `taxomesh` command is available on your PATH.

---

## Configuration (optional)

Create a `taxomesh.toml` in your project directory to configure storage:

```toml
# taxomesh.toml
[repository]
type = "json"
path = "my_taxonomy.json"
```

If this file is absent, taxomesh defaults to `JsonRepository` with `taxomesh.json`
in the current working directory. The JSON file is created automatically on first use.

Use `--config` to point to a config file at a custom path:

```bash
taxomesh --config /path/to/other.toml category list
```

---

## Categories

### Add a category

```bash
taxomesh category add --name "Music"
taxomesh category add --name "Jazz" --description "Improvisational genre"
```

### Add a category with a parent

```bash
# Creates "Jazz" and immediately links it as a child of "Music"
taxomesh category add --name "Jazz" --parent-id 3f4a1b2c-... --sort-index 1
```

### List all categories

```bash
taxomesh category list
```

### Update a category

```bash
# Rename
taxomesh category update 3f4a1b2c-... --name "World Music"

# Add a parent relationship (without changing name/description)
taxomesh category update 7e8d9f0a-... --parent-id 3f4a1b2c-... --sort-index 2
```

### Delete a category

```bash
taxomesh category delete 3f4a1b2c-...
```

---

## Items

### Add an item

```bash
# Integer external ID
taxomesh item add --external-id 42 --name "Blue Note Sessions"

# String slug with description
taxomesh item add --external-id "my-product-slug" --name "Widget Pro" --description "A great widget"

# UUID external ID
taxomesh item add --external-id "550e8400-e29b-41d4-a716-446655440000" --name "Track 01"
```

### Add an item and place it in a category and assign a tag — in one command

```bash
taxomesh item add \
  --external-id 42 \
  --name "Blue Note Sessions" \
  --category-id 7e8d9f0a-... \
  --sort-index 1 \
  --tag-id b2c3d4e5-...
```

### List all items

```bash
taxomesh item list
```

### Update an item

```bash
# Rename
taxomesh item update a1b2c3d4-... --name "New Title"

# Disable
taxomesh item update a1b2c3d4-... --disable

# Update name AND place in a category simultaneously
taxomesh item update a1b2c3d4-... --name "Renamed" --category-id 7e8d9f0a-...
```

### Place an existing item in a category

```bash
taxomesh item add-to-category a1b2c3d4-... --category-id 7e8d9f0a-... --sort-index 3
```

### Assign an existing tag to an existing item

```bash
taxomesh item add-to-tag a1b2c3d4-... --tag-id b2c3d4e5-...
```

### Delete an item

```bash
taxomesh item delete a1b2c3d4-...
```

---

## Tags

### Add a tag

```bash
taxomesh tag add --name "live"
```

### List all tags

```bash
taxomesh tag list
```

### Rename a tag

```bash
taxomesh tag update b2c3d4e5-... --name "studio"
```

### Delete a tag

```bash
taxomesh tag delete b2c3d4e5-...
```

---

## Error handling

All errors print a descriptive message to stderr and exit with code 1:

```bash
taxomesh category delete 00000000-0000-0000-0000-000000000000
# stderr: Error: Category not found: 00000000-0000-0000-0000-000000000000
# exit code: 1

taxomesh tag add --name "this-name-is-way-too-long-for-a-tag"
# stderr: Error: Validation error — name must be at most 25 characters
# exit code: 1

taxomesh category add --name "Jazz" --parent-id 00000000-0000-0000-0000-000000000000
# stderr: Error: Category not found: 00000000-... (Jazz was created; parent link failed)
# exit code: 1
```

---

## Getting help

```bash
taxomesh --help
taxomesh category --help
taxomesh category add --help
taxomesh item --help
taxomesh item add --help
taxomesh item add-to-category --help
taxomesh tag --help
```
