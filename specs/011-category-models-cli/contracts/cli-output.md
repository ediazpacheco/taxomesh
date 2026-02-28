# Contract: CLI Graph Output Format

**Feature**: 011-category-models-cli
**Date**: 2026-02-27

## Category Line Format

```text
[external_id]  [bold cyan]name[/bold cyan]  [dim]category_id[/dim]  [icon]
```

- `external_id`: Shown in yellow only when non-empty. Omitted entirely for categories with `external_id == ""`.
- `name`: Bold cyan (unchanged).
- `category_id`: Dim UUID (unchanged).
- Icon: `[green]✓[/green]` when `enabled=True`, `[red]✗[/red]` when `enabled=False`.

### Examples

Enabled category with external_id:
```text
[yellow]genre-rock[/yellow]  [bold cyan]Rock[/bold cyan]  [dim]abc-123[/dim]  [green]✓[/green]
```

Enabled category without external_id (legacy):
```text
[bold cyan]Jazz[/bold cyan]  [dim]def-456[/dim]  [green]✓[/green]
```

Disabled category:
```text
[bold cyan]Archived[/bold cyan]  [dim]ghi-789[/dim]  [red]✗[/red]
```

## Item Line Format

```text
[yellow]external_id[/yellow]  [dim]item_id[/dim]  [icon]
```

- `external_id`: Yellow (unchanged, always present — required field on Item).
- `item_id`: Dim UUID (unchanged).
- Icon: `[green]✓[/green]` when `enabled=True`, `[red]✗[/red]` when `enabled=False`.
- The text `enabled=True` / `enabled=False` is removed entirely.

### Examples

Enabled item:
```text
[yellow]song-42[/yellow]  [dim]abc-123[/dim]  [green]✓[/green]
```

Disabled item:
```text
[yellow]song-99[/yellow]  [dim]def-456[/dim]  [red]✗[/red]
```
