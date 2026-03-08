# CLI Contract: `taxomesh graph`

**Feature**: `024-graph-enhancements`

## Command Signature

```
taxomesh graph [--show-relations]
```

## Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--show-relations` / `--no-show-relations` | bool | `False` | When set, each item's outgoing item-to-item relations are printed indented below the item in the tree. |

(Inherits global options: `--config PATH`, `--verbose`.)

## Output: Without `--show-relations` (current behaviour, unchanged)

```
Taxonomy
└── Animals  ✓
    ├── Dog  ✓
    └── Cat  ✗
        └── Kittens  ✓
            └── Fluffy (slug:fluffy · abc123)  ✓
```

## Output: With `--show-relations`

Relations appear as additional leaves under the item, indented one further level.
Each relation line shows the relation type and the target item's display name.

```
Taxonomy
└── Animals  ✓
    ├── Dog  ✓
    │   └── [related-to] → Cat
    │   └── [sibling-of] → Fluffy (slug:fluffy · abc123)
    └── Cat  ✗
```

## Behaviour

- Only **outgoing** relations are shown (source = this item).
- Relations are displayed in their normalised (lowercased) form.
- If an item has no outgoing relations, no relation leaves are added.
- If the taxonomy has no item relations at all, output is identical to `--no-show-relations`.
- Relation target names are resolved via `TaxomeshService.get_item()`.

## Error Handling

No new error states. If a target item cannot be found (data inconsistency), the existing
exception hierarchy propagates normally (non-silent).
