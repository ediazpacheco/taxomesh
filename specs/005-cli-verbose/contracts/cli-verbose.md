# CLI Contract: Verbose Flag & List Output

**Feature**: 005-cli-verbose  
**Date**: 2026-02-23

---

## Root Command: `--verbose` Option

### Synopsis
```
taxomesh [--verbose [N]] [--config PATH] COMMAND [ARGS]...
```

### Option Behaviour

| Invocation              | Verbosity level | Extra output? |
|-------------------------|-----------------|---------------|
| *(omitted)*             | 0               | No            |
| `--verbose`             | 1               | Yes           |
| `--verbose 0`           | 0               | No            |
| `--verbose 1`           | 1               | Yes           |
| `--verbose N` (N > 1)   | 1 (clamped)     | Yes           |

### Implementation Note
Implemented via Click's `is_flag=False, flag_value=1, default=0` pattern forwarded
through `typer.Option`. If that pattern is rejected at runtime, the fallback is
`Optional[int] = typer.Option(None)` treating `None` as level 0, and the `--verbose`
(no value) → 1 behaviour is dropped in favour of `--verbose 1`.

---

## Verbose Output Block

When verbosity level ≥ 1, the following block is printed to **stdout** before any
sub-command output. It is printed **unconditionally** — even when the sub-command
subsequently fails.

### Format
```
Repository  : <RepositoryClassName>
Config      : <get_config_summary() return value>
Config file : <absolute path to config file> [not found]
```

The `[not found]` suffix is present only when the config file does not exist.  
When the file exists, the line is:
```
Config file : <absolute path to config file>
```

### Example — file missing (defaults)
```
Repository  : JsonRepository
Config      : taxomesh.json
Config file : /home/user/project/taxomesh.toml [not found]
```

### Example — explicit config file, file exists
```
Repository  : JsonRepository
Config      : /data/my_taxonomy.json
Config file : /etc/taxomesh/custom.toml
```

### Destination
All three lines go to **stdout** (`typer.echo(...)`, not `err=True`).

---

## List Commands: Header & Footer

All three `list` sub-commands (`category list`, `item list`, `tag list`) produce
a header line, zero or more record lines, and a footer line.

### Format
```
--- <EntityLabel> ---
<record line 1>
<record line 2>
...
--- Total: N ---
```

Entity labels:

| Command           | Label        |
|-------------------|--------------|
| `category list`   | `Categories` |
| `item list`       | `Items`      |
| `tag list`        | `Tags`       |

### Example — three categories
```
--- Categories ---
Category(category_id=UUID('...'), name='Rock', description='')
Category(category_id=UUID('...'), name='Jazz', description='')
Category(category_id=UUID('...'), name='Pop', description='')
--- Total: 3 ---
```

### Example — zero items
```
--- Items ---
--- Total: 0 ---
```

### Notes
- `N` is always the count of records **actually printed** (after any filter).
- The header and footer are printed regardless of verbosity level.
- If the command errors (e.g. invalid `--category-id`), **no footer is printed**;
  only the verbose block (if active) and the error message appear.
- Record lines are the Pydantic `__repr__` of each entity (unchanged from current).
