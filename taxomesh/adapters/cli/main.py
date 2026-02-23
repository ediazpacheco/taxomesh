"""CLI entry point for taxomesh.

Provides three sub-command groups: category, item, tag.
Configuration is read from taxomesh.toml in the current working directory,
or from an explicit path supplied via --config.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import typer

from taxomesh import TaxomeshService
from taxomesh.adapters.cli.config import build_service
from taxomesh.domain.types import ExternalId
from taxomesh.exceptions import TaxomeshError

app = typer.Typer(no_args_is_help=True)
category_app = typer.Typer(no_args_is_help=True)
item_app = typer.Typer(no_args_is_help=True)
tag_app = typer.Typer(no_args_is_help=True)

app.add_typer(category_app, name="category")
app.add_typer(item_app, name="item")
app.add_typer(tag_app, name="tag")


def _parse_external_id(raw: str) -> ExternalId:
    """Parse raw CLI string as UUID → int → str."""
    try:
        return UUID(raw)
    except ValueError:
        pass
    try:
        return int(raw)
    except ValueError:
        pass
    return raw


def _get_service(ctx: typer.Context) -> TaxomeshService:
    config_path: Path | None = ctx.obj
    return build_service(config_path=config_path)


def _err(msg: str) -> None:
    typer.echo(msg, err=True)
    raise typer.Exit(code=1)


@app.callback()
def main(
    ctx: typer.Context,
    config: Path | None = typer.Option(None, "--config", help="Path to taxomesh.toml"),
) -> None:
    """taxomesh — multi-parent taxonomy management CLI."""
    ctx.ensure_object(dict)
    ctx.obj = config


# ---------------------------------------------------------------------------
# Category commands
# ---------------------------------------------------------------------------


@category_app.command("list")
def category_list(
    ctx: typer.Context,
    parent_id: UUID | None = typer.Option(None, "--parent-id", help="Filter by parent category UUID"),
) -> None:
    """List categories."""
    svc = _get_service(ctx)
    try:
        categories = svc.list_categories(parent_id=parent_id)
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")
    for cat in categories:
        typer.echo(cat)


@category_app.command("add")
def category_add(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", help="Category name"),
    description: str = typer.Option("", "--description", help="Category description"),
    parent_id: UUID | None = typer.Option(None, "--parent-id", help="Parent category UUID"),
    sort_index: int = typer.Option(0, "--sort-index", help="Sort index within parent"),
) -> None:
    """Create a new category."""
    svc = _get_service(ctx)
    try:
        cat = svc.create_category(name=name, description=description)
        typer.echo(cat)
        if parent_id is not None:
            link = svc.add_category_parent(cat.category_id, parent_id, sort_index=sort_index)
            typer.echo(f"Parent link created: {link}")
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


@category_app.command("delete")
def category_delete(
    ctx: typer.Context,
    category_id: UUID = typer.Argument(..., help="Category UUID to delete"),
) -> None:
    """Delete a category."""
    svc = _get_service(ctx)
    try:
        svc.delete_category(category_id)
        typer.echo(f"Deleted category {category_id}")
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


@category_app.command("update")
def category_update(
    ctx: typer.Context,
    category_id: UUID = typer.Argument(..., help="Category UUID to update"),
    name: str | None = typer.Option(None, "--name", help="New name"),
    description: str | None = typer.Option(None, "--description", help="New description"),
    parent_id: UUID | None = typer.Option(None, "--parent-id", help="Parent category UUID to add"),
    sort_index: int = typer.Option(0, "--sort-index", help="Sort index within parent"),
) -> None:
    """Update a category's name, description, or add a parent."""
    if name is None and description is None and parent_id is None:
        typer.echo("Error: at least one of --name, --description, --parent-id must be provided.", err=True)
        raise typer.Exit(code=1)
    svc = _get_service(ctx)
    try:
        if name is not None or description is not None:
            updated = svc.update_category(category_id, name=name, description=description)
            typer.echo(updated)
        if parent_id is not None:
            link = svc.add_category_parent(category_id, parent_id, sort_index=sort_index)
            typer.echo(f"Parent link created: {link}")
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


# ---------------------------------------------------------------------------
# Item commands
# ---------------------------------------------------------------------------


@item_app.command("list")
def item_list(
    ctx: typer.Context,
    category_id: UUID | None = typer.Option(None, "--category-id", help="Filter by category UUID"),
) -> None:
    """List items."""
    svc = _get_service(ctx)
    try:
        items = svc.list_items(category_id=category_id)
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")
    for item in items:
        typer.echo(item)


@item_app.command("add")
def item_add(
    ctx: typer.Context,
    external_id: str = typer.Option(..., "--external-id", help="External identifier (UUID, int, or string)"),
    category_id: UUID | None = typer.Option(None, "--category-id", help="Place item in this category"),
    sort_index: int = typer.Option(0, "--sort-index", help="Sort index within category"),
    tag_id: UUID | None = typer.Option(None, "--tag-id", help="Assign this tag to the item"),
) -> None:
    """Register a new item."""
    svc = _get_service(ctx)
    try:
        parsed_id = _parse_external_id(external_id)
        item = svc.create_item(external_id=parsed_id)
        typer.echo(item)
        if category_id is not None:
            link = svc.place_item_in_category(item.item_id, category_id, sort_index=sort_index)
            typer.echo(f"Placed in category: {link}")
        if tag_id is not None:
            svc.assign_tag(tag_id, item.item_id)
            typer.echo(f"Assigned tag {tag_id}")
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


@item_app.command("delete")
def item_delete(
    ctx: typer.Context,
    item_id: UUID = typer.Argument(..., help="Item UUID to delete"),
) -> None:
    """Delete an item."""
    svc = _get_service(ctx)
    try:
        svc.delete_item(item_id)
        typer.echo(f"Deleted item {item_id}")
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


@item_app.command("update")
def item_update(
    ctx: typer.Context,
    item_id: UUID = typer.Argument(..., help="Item UUID to update"),
    enable: bool = typer.Option(False, "--enable/--no-enable", help="Enable the item"),
    disable: bool = typer.Option(False, "--disable/--no-disable", help="Disable the item"),
) -> None:
    """Update an item's enabled state."""
    if not enable and not disable:
        typer.echo("Error: at least one of --enable or --disable must be provided.", err=True)
        raise typer.Exit(code=1)
    svc = _get_service(ctx)
    try:
        enabled = bool(enable)
        updated = svc.update_item(item_id, enabled=enabled)
        typer.echo(updated)
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


@item_app.command("add-to-category")
def item_add_to_category(
    ctx: typer.Context,
    item_id: UUID = typer.Argument(..., help="Item UUID"),
    category_id: UUID = typer.Option(..., "--category-id", help="Category UUID"),
    sort_index: int = typer.Option(0, "--sort-index", help="Sort index within category"),
) -> None:
    """Place an existing item in a category (idempotent)."""
    svc = _get_service(ctx)
    try:
        link = svc.place_item_in_category(item_id, category_id, sort_index=sort_index)
        typer.echo(f"Placed item in category: {link}")
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


@item_app.command("add-to-tag")
def item_add_to_tag(
    ctx: typer.Context,
    item_id: UUID = typer.Argument(..., help="Item UUID"),
    tag_id: UUID = typer.Option(..., "--tag-id", help="Tag UUID"),
) -> None:
    """Assign an existing tag to an existing item (idempotent)."""
    svc = _get_service(ctx)
    try:
        svc.assign_tag(tag_id, item_id)
        typer.echo(f"Assigned tag {tag_id} to item {item_id}")
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


# ---------------------------------------------------------------------------
# Tag commands
# ---------------------------------------------------------------------------


@tag_app.command("list")
def tag_list(ctx: typer.Context) -> None:
    """List all tags."""
    svc = _get_service(ctx)
    try:
        tags = svc.list_tags()
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")
    for tag in tags:
        typer.echo(tag)


@tag_app.command("add")
def tag_add(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", help="Tag name (max 25 chars)"),
) -> None:
    """Create a new tag."""
    svc = _get_service(ctx)
    try:
        tag = svc.create_tag(name=name)
        typer.echo(tag)
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


@tag_app.command("delete")
def tag_delete(
    ctx: typer.Context,
    tag_id: UUID = typer.Argument(..., help="Tag UUID to delete"),
) -> None:
    """Delete a tag."""
    svc = _get_service(ctx)
    try:
        svc.delete_tag(tag_id)
        typer.echo(f"Deleted tag {tag_id}")
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


@tag_app.command("update")
def tag_update(
    ctx: typer.Context,
    tag_id: UUID = typer.Argument(..., help="Tag UUID to update"),
    name: str = typer.Option(..., "--name", help="New name"),
) -> None:
    """Rename a tag."""
    svc = _get_service(ctx)
    try:
        updated = svc.update_tag(tag_id, name=name)
        typer.echo(updated)
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


if __name__ == "__main__":
    app()
