# CLI Reference

After installation, the `taxomesh` command is available.

## Common commands

```bash
# Categories
taxomesh category add --name "Music"
taxomesh category list
taxomesh category update <category-uuid> --name "World Music"
taxomesh category delete <category-uuid>

# Items
taxomesh item add --external-id "kind-of-blue"
taxomesh item add-to-category <item-uuid> --category-id <category-uuid>
taxomesh item list --category-id <category-uuid>
taxomesh item update <item-uuid> --disable
taxomesh item delete <item-uuid>

# Tags
taxomesh tag add --name "classic"
taxomesh item add-to-tag <item-uuid> --tag-id <tag-uuid>
taxomesh tag list

# Graph
taxomesh graph
```

## Example output

```text
Taxonomy
└── Music  11111111-1111-1111-1111-111111111111  ✓
    └── Jazz  22222222-2222-2222-2222-222222222222  ✓
        └── kind-of-blue  33333333-3333-3333-3333-333333333333  ✓
```

## Verbose mode

```bash
taxomesh --verbose category list
```

← [Back to README](../README.md)
