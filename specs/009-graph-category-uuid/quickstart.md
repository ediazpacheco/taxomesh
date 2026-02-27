# Quickstart: Graph Category UUID Display

**Feature**: 009-graph-category-uuid
**Date**: 2026-02-26

## What Changed

The `taxomesh graph` command now displays the `category_id` (UUID) on each
category line in the tree output.

## Before

```
Taxonomy
├── Animals
│   ├── lion  a1b2c3d4-...  enabled=True
│   └── eagle e5f6g7h8-...  enabled=True
└── Plants
```

## After

```
Taxonomy
├── Animals  f47ac10b-58cc-4372-a567-0e02b2c3d479
│   ├── lion  a1b2c3d4-...  enabled=True
│   └── eagle e5f6g7h8-...  enabled=True
└── Plants  550e8400-e29b-41d4-a716-446655440000
```

## Verification

```bash
taxomesh graph
```

Every category line should now show name + UUID (dim style).
