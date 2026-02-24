# Service API Contract: get_graph()

**Feature**: 006-taxonomy-graph
**Module**: `taxomesh.application.service`

---

## `TaxomeshService.get_graph`

```python
def get_graph(self) -> TaxomeshGraph:
    """Build and return a full taxonomy snapshot.

    Reads all categories (excluding the internal root), all category-parent
    relationships, and all item placements from the configured repository.
    Constructs a tree of CategoryNode instances rooted at the implicit
    taxonomy root.

    Returns:
        A TaxomeshGraph snapshot. Returns a graph with an empty roots list
        when no user-created categories exist.

    Raises:
        TaxomeshRepositoryError: If the underlying repository fails during read.
    """
```

### Contract Rules

1. **Completeness**: The returned graph MUST contain every non-root category
   exactly once per explicit parent it belongs to.
2. **Root exclusion**: The `__root__` category MUST NOT appear anywhere in the
   returned graph.
3. **Tag exclusion**: No tag data appears in `TaxomeshGraph` or `CategoryNode`.
4. **Item ordering**: Within each `CategoryNode.items`, items are sorted by
   `ItemParentLink.sort_index` ascending.
5. **Children ordering**: Within each `CategoryNode.children`, children are
   sorted by `CategoryParentLink.sort_index` ascending on the explicit link.
6. **Top-level rule**: A category is a root (`TaxomeshGraph.roots` member) if
   and only if it has no explicit parents (only the implicit root link).
7. **Multi-parent categories**: A category with N explicit parents appears as N
   independent `CategoryNode` instances, one under each parent.
8. **Empty taxonomy**: Returns `TaxomeshGraph(roots=[])`. Never raises an error
   for an empty taxonomy.
9. **Snapshot semantics**: The graph reflects the repository state at the
   moment of the call. Subsequent mutations to the taxonomy are not reflected.

---

## `taxomesh graph` CLI Command

```text
Usage: taxomesh graph [OPTIONS]

  Display the full taxonomy as a colour-coded tree.

Options:
  --config PATH   Path to taxomesh.toml  [default: None]
  --verbose       Show repository type and config file path before output.
  --help          Show this message and exit.
```

### Contract Rules

1. **Exit 0** on both empty and non-empty taxonomy.
2. **Empty output**: When graph is empty, prints a human-readable message
   (not blank output, not an error).
3. **Tree structure**: Non-empty output contains tree connector characters
   (│ / ├── / └──) conveying hierarchy.
4. **Item display**: Every item leaf MUST display all three fields — `external_id`,
   `item_id`, and `enabled` — always, regardless of enabled state.
   `enabled=True` and `enabled=False` MUST be visually distinct (e.g., different colors).
5. **No tags**: Tag data never appears.
6. **Verbose support**: Supports `--verbose` flag per existing convention.
