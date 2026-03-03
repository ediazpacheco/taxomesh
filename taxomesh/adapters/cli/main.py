"""CLI entry point for taxomesh.

Provides three sub-command groups: category, item, tag.
Configuration is read from taxomesh.toml in the current working directory,
or from an explicit path supplied via --config.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final
from uuid import UUID

import typer
from rich.console import Console
from rich.tree import Tree

import taxomesh
from taxomesh.adapters.cli.config import BuildResult, _resolve_effective_config, build, dump_config
from taxomesh.domain.graph import CategoryNode
from taxomesh.domain.types import ExternalId
from taxomesh.exceptions import TaxomeshConfigError, TaxomeshError

ENABLED_ICON: Final[str] = "✓"
DISABLED_ICON: Final[str] = "✗"

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


def _verbose(ctx: typer.Context) -> bool:
    """Extract the verbose flag from the Typer context object."""
    obj: dict[str, Any] = ctx.obj  # Any: ctx.obj is a typed dict accessed only via _verbose()/_config_path() helpers
    return bool(obj.get("verbose", False))


def _config_path(ctx: typer.Context) -> Path | None:
    """Extract the config file path from the Typer context object."""
    obj: dict[str, Any] = ctx.obj  # Any: ctx.obj is a typed dict accessed only via _verbose()/_config_path() helpers
    value = obj.get("config_path")
    return Path(value) if value is not None else None


def _print_verbose(result: BuildResult, verbose: bool) -> None:
    """Print the repository diagnostic block to stdout when verbose is True.

    Outputs three aligned lines showing the repository type, its configuration
    string, and the config file path (with a "[not found]" suffix when absent).
    This function is called before any sub-command output so the block always
    appears first, even if the command subsequently fails.
    """
    if verbose:
        config_file = str(result.config_file_path)
        if not result.config_file_exists:
            config_file += " [not found]"
        typer.echo(f"Repository  : {type(result.repository).__name__}")
        typer.echo(f"Config      : {result.repository.get_config_summary()}")
        typer.echo(f"Config file : {config_file}")


def _err(msg: str) -> None:
    typer.echo(msg, err=True)
    raise typer.Exit(code=1)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    config: Path | None = typer.Option(None, "--config", help="Path to taxomesh.toml"),
    verbose: bool = typer.Option(False, "--verbose", help="Show repository type and config file path before output."),
    show_config: bool = typer.Option(
        False, "--show-config", help="Print effective configuration in TOML format and exit."
    ),  # noqa: E501
) -> None:
    """taxomesh — multi-parent taxonomy management CLI."""
    ctx.ensure_object(dict)
    # Any: ctx.obj is a typed dict accessed only via _verbose()/_config_path() helpers
    ctx.obj = {"config_path": config, "verbose": verbose}
    if show_config:
        try:
            repo_type, repo_path = _resolve_effective_config(config)
            typer.echo(dump_config(repo_type, repo_path), nl=False)
            raise typer.Exit()
        except TaxomeshConfigError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from None


# ---------------------------------------------------------------------------
# Category commands
# ---------------------------------------------------------------------------


@category_app.command("list")
def category_list(
    ctx: typer.Context,
    parent_id: UUID | None = typer.Option(None, "--parent-id", help="Filter by parent category UUID"),
) -> None:
    """List categories."""
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        categories = svc.list_categories(parent_id=parent_id)
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")
    typer.echo("--- Categories ---")
    for cat in categories:
        typer.echo(cat)
    typer.echo(f"--- Total: {len(categories)} ---")


@category_app.command("add")
def category_add(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", help="Category name"),
    description: str = typer.Option("", "--description", help="Category description"),
    slug: str = typer.Option("", "--slug", help="Optional slug (unique when non-empty)"),
    parent_id: UUID | None = typer.Option(None, "--parent-id", help="Parent category UUID"),
    sort_index: int = typer.Option(0, "--sort-index", help="Sort index within parent"),
) -> None:
    """Create a new category."""
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        cat = svc.create_category(name=name, description=description, slug=slug)
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
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
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
    slug: str | None = typer.Option(None, "--slug", help="New slug (empty string to clear)"),
    parent_id: UUID | None = typer.Option(None, "--parent-id", help="Parent category UUID to add"),
    sort_index: int = typer.Option(0, "--sort-index", help="Sort index within parent"),
) -> None:
    """Update a category's name, description, slug, or add a parent."""
    if name is None and description is None and slug is None and parent_id is None:
        typer.echo("Error: at least one of --name, --description, --slug, --parent-id must be provided.", err=True)
        raise typer.Exit(code=1)
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        if name is not None or description is not None or slug is not None:
            updated = svc.update_category(category_id, name=name, description=description, slug=slug)
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
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        items = svc.list_items(category_id=category_id)
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")
    typer.echo("--- Items ---")
    for item in items:
        typer.echo(item)
    typer.echo(f"--- Total: {len(items)} ---")


@item_app.command("add")
def item_add(
    ctx: typer.Context,
    name: str = typer.Option("", "--name", help="Human-readable item name"),
    external_id: str = typer.Option("", "--external-id", help="External identifier (UUID, int, or string); optional"),
    slug: str = typer.Option("", "--slug", help="Optional slug (unique when non-empty)"),
    category_id: UUID | None = typer.Option(None, "--category-id", help="Place item in this category"),
    sort_index: int = typer.Option(0, "--sort-index", help="Sort index within category"),
    tag_id: UUID | None = typer.Option(None, "--tag-id", help="Assign this tag to the item"),
) -> None:
    """Register a new item."""
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        parsed_id = _parse_external_id(external_id)
        item = svc.create_item(name=name, external_id=parsed_id, slug=slug)
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
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
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
    slug: str | None = typer.Option(None, "--slug", help="New slug (empty string to clear)"),
    name: str | None = typer.Option(None, "--name", help="New name"),
    category_id: UUID | None = typer.Option(None, "--category-id", help="Place item in this category"),
    sort_index: int = typer.Option(0, "--sort-index", help="Sort index within category"),
    tag_id: UUID | None = typer.Option(None, "--tag-id", help="Assign this tag to the item"),
) -> None:
    """Update an item's enabled state, slug, name, category placement, or tag assignment."""
    if not enable and not disable and slug is None and name is None and category_id is None and tag_id is None:
        typer.echo(
            "Error: at least one of --enable, --disable, --slug, --name, --category-id, --tag-id must be provided.",
            err=True,
        )
        raise typer.Exit(code=1)
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        if enable or disable or slug is not None or name is not None:
            enabled_val: bool | None = bool(enable) if (enable or disable) else None
            updated = svc.update_item(item_id, enabled=enabled_val, slug=slug, name=name)
            typer.echo(updated)
        if category_id is not None:
            link = svc.place_item_in_category(item_id, category_id, sort_index=sort_index)
            typer.echo(f"Placed in category: {link}")
        if tag_id is not None:
            svc.assign_tag(tag_id, item_id)
            typer.echo(f"Assigned tag {tag_id}")
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
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
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
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
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
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        tags = svc.list_tags()
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")
    typer.echo("--- Tags ---")
    for tag in tags:
        typer.echo(tag)
    typer.echo(f"--- Total: {len(tags)} ---")


@tag_app.command("add")
def tag_add(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", help="Tag name (max 25 chars)"),
) -> None:
    """Create a new tag."""
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
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
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
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
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        updated = svc.update_tag(tag_id, name=name)
        typer.echo(updated)
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


# ---------------------------------------------------------------------------
# Version command
# ---------------------------------------------------------------------------


@app.command("version")
def version_cmd() -> None:
    """Print the taxomesh package version and exit."""
    typer.echo(taxomesh.__version__)


# ---------------------------------------------------------------------------
# Graph command
# ---------------------------------------------------------------------------


def _add_graph_node(tree_node: Tree, category_node: CategoryNode) -> None:
    """Recursively populate a Rich Tree node from a CategoryNode.

    Adds a styled branch for the category (bold cyan name) and a leaf for
    each item showing ``external_id``, ``item_id``, and ``enabled`` status.
    Recurses into child categories.

    Args:
        tree_node: The Rich Tree node to attach category and item branches to.
        category_node: The CategoryNode supplying category and item data.
    """
    cat = category_node.category
    cat_icon = ENABLED_ICON if cat.enabled else DISABLED_ICON
    cat_icon_style = "green" if cat.enabled else "red"
    cat_label = f"[bold cyan]{cat}[/bold cyan]  [{cat_icon_style}]{cat_icon}[/{cat_icon_style}]"
    branch = tree_node.add(cat_label)
    for item in category_node.items:
        item_icon = ENABLED_ICON if item.enabled else DISABLED_ICON
        item_icon_style = "green" if item.enabled else "red"
        label = f"[yellow]{item}[/yellow]  [{item_icon_style}]{item_icon}[/{item_icon_style}]"
        branch.add(label)
    for child in category_node.children:
        _add_graph_node(branch, child)


@app.command("graph")
def graph_cmd(ctx: typer.Context) -> None:
    """Display the full taxonomy as a colour-coded tree.

    Retrieves the complete taxonomy snapshot via the service and renders it
    as a Rich tree in the terminal.  Categories are shown in bold cyan,
    items in yellow with dim UUID and colour-coded enabled status.

    Args:
        ctx: Typer context carrying verbose flag and config path.
    """
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    try:
        graph = result.service.get_graph()
    except TaxomeshError as exc:
        _err(str(exc))
    if not graph.roots:
        typer.echo("No categories were found. Add one with: taxomesh category add --name <name>")
        return
    tree = Tree("Taxonomy")
    for root_node in graph.roots:
        _add_graph_node(tree, root_node)
    Console().print(tree)


if __name__ == "__main__":
    app()
