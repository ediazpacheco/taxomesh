# Quickstart: CLI Verbose Mode & List Enhancements

**Feature**: 005-cli-verbose  
**Date**: 2026-02-23

---

## Using `--verbose`

Append `--verbose` to any taxomesh command to see which repository is active
and where the configuration file is expected.

```bash
# Verbose flag — default level (1)
taxomesh --verbose category list

# Output when taxomesh.toml does not exist:
# Repository  : JsonRepository
# Config      : taxomesh.json
# Config file : /home/user/project/taxomesh.toml [not found]
# --- Categories ---
# --- Total: 0 ---

# Explicit level — same as above
taxomesh --verbose 1 category list

# Suppress verbose explicitly (useful in scripts that set it via variable)
taxomesh --verbose 0 category list
```

---

## Verbose with a custom config file

```bash
taxomesh --config /etc/taxonomy.toml --verbose tag list

# Repository  : JsonRepository
# Config      : /data/taxonomy.json
# Config file : /etc/taxonomy.toml
# --- Tags ---
# Tag(tag_id=UUID('...'), name='live')
# --- Total: 1 ---
```

---

## List commands always show header and footer

Headers and footers appear on every `list` command, regardless of `--verbose`.

```bash
taxomesh category list
# --- Categories ---
# Category(category_id=UUID('...'), name='Rock', description='')
# Category(category_id=UUID('...'), name='Jazz', description='')
# --- Total: 2 ---

taxomesh item list --category-id <uuid>
# --- Items ---
# Item(item_id=UUID('...'), external_id=42, enabled=True)
# --- Total: 1 ---

taxomesh tag list
# --- Tags ---
# --- Total: 0 ---
```

---

## Verbose output on error

The verbose block is printed before command execution, so it appears even when
the command itself fails.

```bash
taxomesh --verbose category list --parent-id not-a-uuid
# Repository  : JsonRepository
# Config      : taxomesh.json
# Config file : /home/user/project/taxomesh.toml [not found]
# Error: invalid UUID value: 'not-a-uuid'
# (exit code 1, no footer printed)
```

---

## Programmatic repository introspection

```python
from taxomesh.adapters.repositories.json_repository import JsonRepository
from pathlib import Path

repo = JsonRepository(Path("/data/taxonomy.json"))
print(repo.get_config_summary())   # → /data/taxonomy.json
```
