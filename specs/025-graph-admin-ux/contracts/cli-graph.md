# CLI Contract: `taxomesh graph` (updated)

**Feature**: `025-graph-admin-ux`

## Command Signature

```
taxomesh graph [--max-depth INTEGER] [--show-relations]
```

## Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--max-depth INTEGER` | int | `3` | Maximum depth of categories/items to display. `0` = unlimited. |
| `--show-relations` / `--no-show-relations` | bool | `False` | Show outgoing item relations as leaves (unchanged from 024). |

(Inherits global: `--config PATH`, `--verbose`.)

## Depth Semantics

| Depth | What is shown |
|-------|--------------|
| 0 | Root categories only (no items, no children) |
| 1 | Root categories + their direct items + their direct child categories |
| 2 | …+ grandchild categories + their items |
| N | All nodes at hierarchy levels ≤ N |
| `--max-depth 0` | Complete taxonomy (no limit) |

## Output Examples

**`taxomesh graph`** (default `--max-depth 3`):
```
Taxonomy
└── Animals  ✓          # depth 0
    ├── Dog  ✓           # depth 1 (item)
    └── Mammals  ✓       # depth 1 (child category)
        ├── Whale  ✓     # depth 2 (item)
        └── Primates ✓   # depth 2 (child category)
            └── Chimp ✓  # depth 3 (item) — last shown
            # depth-3 child categories would be omitted
```

**`taxomesh graph --max-depth 0`** (unlimited):
```
Taxonomy
└── Animals  ✓
    └── Mammals  ✓
        └── Primates  ✓
            └── Hominids ✓
                └── Human ✓
```

**`taxomesh graph --show-relations`** (with `--max-depth 3`):
- Relations only appear under items within the depth limit.
