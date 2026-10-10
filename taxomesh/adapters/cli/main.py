"""The ``taxomesh`` command.

It has three groups of commands, ``category``, ``item`` and ``tag``, one for each collection of
the service. Each command is the name of the collection member that it calls, with ``_`` written
``-``: ``taxomesh item place-in`` calls ``svc.items.place_in``. Each command calls one member. The
configuration is ``taxomesh.toml`` in the working directory, or the file that ``--config`` names.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Final
from uuid import UUID

import typer
from rich.console import Console
from rich.markup import escape as _markup_escape
from rich.table import Table
from rich.tree import Tree

import taxomesh
from taxomesh._config import effective_repository_config
from taxomesh.adapters.cli.config import BuildResult, build, dump_config
from taxomesh.contrib.api.errors import TaxomeshGraphTooLargeError
from taxomesh.contrib.api.serializers import MAX_EMITTED_NODES
from taxomesh.domain.constants import MAX_TAG_NAME_LENGTH
from taxomesh.domain.graph import CategoryNode
from taxomesh.domain.models import Item
from taxomesh.domain.related import RelatedItems
from taxomesh.domain.types import UNSET, Direction, UnsetType
from taxomesh.exceptions import TaxomeshConfigError, TaxomeshError

ENABLED_ICON: Final[str] = "✓"
DISABLED_ICON: Final[str] = "✗"
MAX_DEPTH_UNLIMITED: Final[int] = 0
GRAPH_DEFAULT_MAX_DEPTH: Final[int] = 3
CYCLE_MARK: Final[str] = "↻ cycle"
"""What ``graph`` draws after a category already on the path being drawn: a cycle in stored data."""
DIRECTION_HELP: Final[str] = "Which relations to read: outgoing (default), incoming, or both"
EXTERNAL_ID_HELP: Final[str] = "External id, stored as written; optional"
ENABLED_HELP: Final[str] = "Enable or disable; when both are omitted, the state stays"


class EnabledState(StrEnum):
    """Which rows a listing returns, by their enabled state.

    A ``StrEnum`` and not a plain ``Enum``, so that the members are ordinary strings: Typer shows
    them as the choices of ``--state``, refuses any other value, and passes the member itself to
    the command.

    This is how the command line names the three values of the service's ``enabled`` filter. The
    domain has no such type: it takes ``bool | None``. So this class is here, and not beside
    :class:`~taxomesh.domain.types.Direction`.

    Attributes:
        ENABLED: Only the enabled rows. The default, as a member that finds rows defaults to
            ``enabled=True``.
        DISABLED: Only the disabled rows.
        ALL: Every row, whatever its state.
    """

    ENABLED = "enabled"
    DISABLED = "disabled"
    ALL = "all"


STATE_FILTERS: Final[Mapping[EnabledState, bool | None]] = {
    EnabledState.ENABLED: True,
    EnabledState.DISABLED: False,
    EnabledState.ALL: None,
}
"""The one place where the command line's state names become the service's ``enabled`` filter."""

app = typer.Typer(no_args_is_help=True)
category_app = typer.Typer(no_args_is_help=True, help="Read and change categories, and their parents.")
item_app = typer.Typer(no_args_is_help=True, help="Read and change items: their placements, tags and relations.")
tag_app = typer.Typer(no_args_is_help=True, help="Read and change tags.")

app.add_typer(category_app, name="category")
app.add_typer(item_app, name="item")
app.add_typer(tag_app, name="tag")


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
    """Print the repository block to stdout when ``verbose`` is ``True``.

    The block is three aligned lines: the class of the repository, its ``config_summary``, and
    the path of the config file, with ``[not found]`` after it when the file does not exist. Each
    command calls this before its own output, so the block comes first, also when the command
    fails after it.
    """
    if verbose:
        config_file = str(result.config_file_path)
        if not result.config_file_exists:
            config_file += " [not found]"
        typer.echo(f"Repository  : {type(result.repository).__name__}")
        typer.echo(f"Config      : {result.repository.config_summary}")
        typer.echo(f"Config file : {config_file}")


def _err(msg: str) -> None:
    typer.echo(msg, err=True)
    raise typer.Exit(code=1)


def _given[V](option: V | None) -> V | UnsetType:
    """Return the option's value, or ``UNSET`` when the command line omits it: the stored value stays."""
    return UNSET if option is None else option


def _echo_rows(title: str, rows: Sequence[object]) -> None:
    """Print a listing: a header, one row per line, and the total."""
    typer.echo(f"--- {title} ---")
    for row in rows:
        typer.echo(row)
    typer.echo(f"--- Total: {len(rows)} ---")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    config: Path | None = typer.Option(
        None, "--config", help="Path of the config file; by default taxomesh.toml in the working directory"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Print the repository, its configuration and the config file before the output"
    ),
    show_config: bool = typer.Option(
        False, "--show-config", help="Print the configuration in effect, as TOML, and exit"
    ),  # noqa: E501
) -> None:
    """Read and change the categories, items and tags that taxomesh stores."""
    ctx.ensure_object(dict)
    # Any: ctx.obj is a typed dict accessed only via _verbose()/_config_path() helpers
    ctx.obj = {"config_path": config, "verbose": verbose}
    if show_config:
        try:
            repo_type, repo_path = effective_repository_config(config)
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
    parent_id: UUID | None = typer.Option(None, "--parent-id", help="Only this parent's children"),
    item_id: UUID | None = typer.Option(None, "--item-id", help="Only the categories this item is placed in"),
    state: EnabledState = typer.Option(
        EnabledState.ENABLED, "--state", help="Which categories to list: enabled (default), disabled, or all"
    ),
) -> None:
    """List categories: every one, the children of a parent, or the categories an item is placed in."""
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        categories = svc.categories.list(parent=parent_id, item=item_id, enabled=STATE_FILTERS[state])
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")
    _echo_rows("Categories", categories)


@category_app.command("roots")
def category_roots(
    ctx: typer.Context,
    state: EnabledState = typer.Option(
        EnabledState.ENABLED, "--state", help="Which categories to list: enabled (default), disabled, or all"
    ),
) -> None:
    """List the top level: the categories that have no parent."""
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        categories = svc.categories.roots(enabled=STATE_FILTERS[state])
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")
    _echo_rows("Categories", categories)


@category_app.command("create")
def category_create(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", help="Category name"),
    description: str = typer.Option("", "--description", help="Category description"),
    slug: str = typer.Option("", "--slug", help="Optional slug (unique when non-empty)"),
    external_id: str | None = typer.Option(None, "--external-id", help=EXTERNAL_ID_HELP),
) -> None:
    """Create a category at the top level."""
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        cat = svc.categories.create(name=name, description=description, slug=slug, external_id=external_id)
        typer.echo(cat)
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


@category_app.command("add-parent")
def category_add_parent(
    ctx: typer.Context,
    category_id: UUID = typer.Argument(..., help="Category UUID"),
    parent_id: UUID = typer.Option(..., "--parent-id", help="Parent category UUID to add"),
    sort_index: int = typer.Option(0, "--sort-index", help="Sort index within the parent"),
) -> None:
    """Add a parent to a category; a category with a parent leaves the top level."""
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        link = svc.categories.add_parent(category_id, parent_id, sort_index=sort_index)
        typer.echo(
            f"Added parent {link.parent_category_id} to category {link.category_id} at sort index {link.sort_index}"
        )
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


@category_app.command("remove-parent")
def category_remove_parent(
    ctx: typer.Context,
    category_id: UUID = typer.Argument(..., help="Category UUID"),
    parent_id: UUID = typer.Option(..., "--parent-id", help="Parent category UUID to remove"),
) -> None:
    """Remove one parent from a category; its other parents stay (idempotent).

    \f
    Args:
        ctx: Typer context carrying verbose flag and config path.
        category_id: The category losing a parent.
        parent_id: The parent to remove. A category that loses its last parent is back at the
            top level.
    """
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        svc.categories.remove_parent(category_id, parent_id)
        typer.echo(f"Removed parent {parent_id} from category {category_id}")
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
    enabled: bool | None = typer.Option(None, "--enable/--disable", help=ENABLED_HELP),
) -> None:
    """Update a category's name, description, slug or enabled state; an omitted option keeps the stored value."""
    if name is None and description is None and slug is None and enabled is None:
        _err("At least one of --name, --description, --slug or --enable/--disable is required")
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        updated = svc.categories.update(
            category_id,
            name=_given(name),
            description=_given(description),
            slug=_given(slug),
            enabled=_given(enabled),
        )
        typer.echo(updated)
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


@category_app.command("delete")
def category_delete(
    ctx: typer.Context,
    category_id: UUID = typer.Argument(..., help="Category UUID to delete"),
) -> None:
    """Delete a category, and every link that names it."""
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        svc.categories.delete(category_id)
        typer.echo(f"Deleted category {category_id}")
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
    category_id: UUID | None = typer.Option(None, "--category-id", help="Only the items in this category"),
    recursive: bool = typer.Option(
        False, "--recursive", help="With --category-id, also list the items in the category's descendants"
    ),
    tag_id: UUID | None = typer.Option(None, "--tag-id", help="Only the items with this tag"),
    state: EnabledState = typer.Option(
        EnabledState.ENABLED, "--state", help="Which items to list: enabled (default), disabled, or all"
    ),
) -> None:
    """List items: every one, the items in a category, the items with a tag, or both."""
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        items = svc.items.list(category=category_id, recursive=recursive, tag=tag_id, enabled=STATE_FILTERS[state])
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")
    _echo_rows("Items", items)


@item_app.command("create")
def item_create(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", help="Item name"),
    slug: str = typer.Option("", "--slug", help="Optional slug (unique when non-empty)"),
    external_id: str | None = typer.Option(None, "--external-id", help=EXTERNAL_ID_HELP),
) -> None:
    """Create an item."""
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        item = svc.items.create(name=name, slug=slug, external_id=external_id)
        typer.echo(item)
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


@item_app.command("update")
def item_update(
    ctx: typer.Context,
    item_id: UUID = typer.Argument(..., help="Item UUID to update"),
    name: str | None = typer.Option(None, "--name", help="New name"),
    slug: str | None = typer.Option(None, "--slug", help="New slug (empty string to clear)"),
    enabled: bool | None = typer.Option(None, "--enable/--disable", help=ENABLED_HELP),
) -> None:
    """Update an item's name, slug or enabled state; an omitted option keeps the stored value."""
    if name is None and slug is None and enabled is None:
        _err("At least one of --name, --slug or --enable/--disable is required")
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        updated = svc.items.update(item_id, name=_given(name), slug=_given(slug), enabled=_given(enabled))
        typer.echo(updated)
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


@item_app.command("delete")
def item_delete(
    ctx: typer.Context,
    item_id: UUID = typer.Argument(..., help="Item UUID to delete"),
) -> None:
    """Delete an item, and every link that names it."""
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        svc.items.delete(item_id)
        typer.echo(f"Deleted item {item_id}")
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


@item_app.command("place-in")
def item_place_in(
    ctx: typer.Context,
    item_id: UUID = typer.Argument(..., help="Item UUID"),
    category_id: UUID = typer.Option(..., "--category-id", help="Category UUID"),
    sort_index: int = typer.Option(0, "--sort-index", help="Sort index within the category"),
) -> None:
    """Place an item in a category (idempotent)."""
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        link = svc.items.place_in(item_id, category_id, sort_index=sort_index)
        typer.echo(f"Placed item {link.item_id} in category {link.category_id} at sort index {link.sort_index}")
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


@item_app.command("remove-from")
def item_remove_from(
    ctx: typer.Context,
    item_id: UUID = typer.Argument(..., help="Item UUID"),
    category_id: UUID = typer.Option(..., "--category-id", help="Category UUID"),
) -> None:
    """Remove an item from one category; its other placements stay (idempotent).

    \f
    Args:
        ctx: Typer context carrying verbose flag and config path.
        item_id: The item losing a placement.
        category_id: The category to remove it from.
    """
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        svc.items.remove_from(item_id, category_id)
        typer.echo(f"Removed item {item_id} from category {category_id}")
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


@item_app.command("tag")
def item_tag(
    ctx: typer.Context,
    item_id: UUID = typer.Argument(..., help="Item UUID"),
    tag_id: UUID = typer.Option(..., "--tag-id", help="Tag UUID"),
) -> None:
    """Tag an item (idempotent)."""
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        svc.items.tag(item_id, tag_id)
        typer.echo(f"Added tag {tag_id} to item {item_id}")
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


@item_app.command("untag")
def item_untag(
    ctx: typer.Context,
    item_id: UUID = typer.Argument(..., help="Item UUID"),
    tag_id: UUID = typer.Option(..., "--tag-id", help="Tag UUID"),
) -> None:
    """Remove a tag from an item (idempotent).

    \f
    Args:
        ctx: Typer context carrying verbose flag and config path.
        item_id: The item losing the tag.
        tag_id: The tag to remove.
    """
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        svc.items.untag(item_id, tag_id)
        typer.echo(f"Removed tag {tag_id} from item {item_id}")
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


def _parse_metadata(raw: list[str]) -> dict[str, str]:
    """Parse a list of 'KEY=VALUE' strings into a dict."""
    result: dict[str, str] = {}
    for entry in raw:
        if "=" not in entry:
            typer.echo(f"--metadata must be KEY=VALUE, not {entry!r}", err=True)
            raise typer.Exit(code=1)
        key, _, value = entry.partition("=")
        result[key] = value
    return result


@item_app.command("relate")
def item_relate(
    ctx: typer.Context,
    source_item_id: UUID = typer.Argument(..., help="Source item UUID"),
    target_item_id: UUID = typer.Argument(..., help="Target item UUID"),
    relation_type: str = typer.Argument(..., help="Relation type, such as related_to"),
    sort_index: int = typer.Option(0, "--sort-index", help="Sort index among the relations of the source item"),
    metadata: list[str] | None = typer.Option(None, "--metadata", help="KEY=VALUE pairs (repeatable)"),
) -> None:
    """Create or update a directed relation between two items."""
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    meta = _parse_metadata(metadata or [])
    try:
        link = svc.items.relate(source_item_id, target_item_id, relation_type, sort_index=sort_index, metadata=meta)
        typer.echo(f"Stored relation: {link.source_item_id} --[{link.relation_type}]--> {link.target_item_id}")
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


@item_app.command("unrelate")
def item_unrelate(
    ctx: typer.Context,
    source_item_id: UUID = typer.Argument(..., help="Source item UUID"),
    target_item_id: UUID = typer.Argument(..., help="Target item UUID"),
    relation_type: str = typer.Argument(..., help="Relation type"),
) -> None:
    """Remove a directed relation between two items (idempotent)."""
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        svc.items.unrelate(source_item_id, target_item_id, relation_type)
        typer.echo(f"Removed relation: {source_item_id} --[{relation_type}]--> {target_item_id}")
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


@item_app.command("list-relations")
def item_list_relations(
    ctx: typer.Context,
    item_id: UUID = typer.Argument(..., help="Item UUID"),
    relation_types: list[str] | None = typer.Option(
        None, "--relation-type", help="Only this relation type; repeat the option for several"
    ),
    direction: Direction = typer.Option(Direction.OUTGOING, "--direction", help=DIRECTION_HELP),
) -> None:
    """List an item's relations."""
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        links = svc.items.list_relations(item_id, relation_types=relation_types, direction=direction.value)
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")
    table = Table(title=f"Relations ({direction}) for {item_id}")
    table.add_column("Source")
    table.add_column("Type")
    table.add_column("Target")
    table.add_column("Sort")
    for lnk in links:
        table.add_row(str(lnk.source_item_id), lnk.relation_type, str(lnk.target_item_id), str(lnk.sort_index))
    Console().print(table)
    typer.echo(f"--- Total: {len(links)} ---")


@item_app.command("list-related")
def item_list_related(
    ctx: typer.Context,
    item_id: UUID = typer.Argument(..., help="Item UUID"),
    relation_types: list[str] | None = typer.Option(
        None, "--relation-type", help="Only this relation type; repeat the option for several"
    ),
    direction: Direction = typer.Option(Direction.OUTGOING, "--direction", help=DIRECTION_HELP),
    state: EnabledState = typer.Option(
        EnabledState.ENABLED, "--state", help="Which related items to list: enabled (default), disabled, or all"
    ),
) -> None:
    """List the items related to an item."""
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        items = svc.items.list_related(
            item_id,
            relation_types=relation_types,
            direction=direction.value,
            enabled=STATE_FILTERS[state],
        )
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")
    _echo_rows(f"Related items ({direction}) for {item_id}", items)


# ---------------------------------------------------------------------------
# Tag commands
# ---------------------------------------------------------------------------


@tag_app.command("list")
def tag_list(
    ctx: typer.Context,
    item_id: UUID | None = typer.Option(None, "--item-id", help="Only the tags on this item"),
) -> None:
    """List tags: every one, or the tags on an item."""
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        tags = svc.tags.list(item=item_id)
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")
    _echo_rows("Tags", tags)


@tag_app.command("create")
def tag_create(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", help=f"Tag name, at most {MAX_TAG_NAME_LENGTH} characters"),
) -> None:
    """Create a tag."""
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        tag = svc.tags.create(name=name)
        typer.echo(tag)
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


@tag_app.command("update")
def tag_update(
    ctx: typer.Context,
    tag_id: UUID = typer.Argument(..., help="Tag UUID to update"),
    name: str | None = typer.Option(None, "--name", help="New name"),
) -> None:
    """Rename a tag."""
    if name is None:
        _err("--name is required")
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        updated = svc.tags.update(tag_id, name=_given(name))
        typer.echo(updated)
    except TaxomeshError as exc:
        _err(str(exc))
    except Exception as exc:
        _err(f"Unexpected error: {exc}")


@tag_app.command("delete")
def tag_delete(
    ctx: typer.Context,
    tag_id: UUID = typer.Argument(..., help="Tag UUID to delete"),
) -> None:
    """Delete a tag, and every link that names it."""
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    svc = result.service
    try:
        svc.tags.delete(tag_id)
        typer.echo(f"Deleted tag {tag_id}")
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


@dataclass(frozen=True, slots=True)
class _Enter:
    """A category to draw, the branch to draw it under, and its depth below the top level."""

    node: CategoryNode
    parent: Tree
    depth: int


@dataclass(frozen=True, slots=True)
class _Leave:
    """A marker that the descent has finished with a category, so it leaves the current path."""

    category_id: UUID


def _state_icon(enabled: bool) -> str:
    """The coloured enabled mark drawn after a row."""
    return f"[green]{ENABLED_ICON}[/green]" if enabled else f"[red]{DISABLED_ICON}[/red]"


def _draw_graph(
    tree: Tree,
    roots: Sequence[CategoryNode],
    *,
    max_depth: int = MAX_DEPTH_UNLIMITED,
) -> list[tuple[Tree, Item]]:
    """Draw the categories reachable from ``roots`` onto ``tree``, and return each drawn item.

    Each category is a bold cyan branch, and each of its items a yellow leaf, both followed by
    their enabled mark. A category deeper than ``max_depth`` is drawn without its items or
    children; ``0`` (``MAX_DEPTH_UNLIMITED``) sets no limit.

    The descent is iterative, and its guard is path-local, as ``serializers.graph_to_dict``'s
    is: a category reachable through several parents is drawn under each of them, and a category
    already on the path being drawn, which only a cycle in stored data produces, is drawn with
    :data:`CYCLE_MARK` and its items, and not descended into. So the drawing ends on any stored
    shape at every ``max_depth``, and no chain is too deep for it. Drawing once per path is
    exponential in shared parents, so it keeps the serializer's budget too.

    Args:
        tree: The Rich tree to draw onto.
        roots: The categories to draw from, in order.
        max_depth: Maximum depth to draw; 0 means unlimited.

    Returns:
        Each drawn item with the leaf it was drawn as, in drawing order. An item drawn under
        several paths appears once per path.

    Raises:
        TaxomeshGraphTooLargeError: If the drawing would pass ``MAX_EMITTED_NODES`` categories.
    """
    drawn: list[tuple[Tree, Item]] = []
    emitted = 0
    path: set[UUID] = set()
    depth_limited = max_depth != MAX_DEPTH_UNLIMITED
    stack: list[_Enter | _Leave] = [_Enter(node, tree, 0) for node in reversed(roots)]
    while stack:
        frame = stack.pop()
        if isinstance(frame, _Leave):
            path.remove(frame.category_id)
            continue
        emitted += 1
        if emitted > MAX_EMITTED_NODES:
            raise TaxomeshGraphTooLargeError(
                f"This graph would draw more than {MAX_EMITTED_NODES} categories: a category reachable through "
                "several parents is drawn once per path, so give a smaller --max-depth"
            )
        category = frame.node.category
        repeated = category.category_id in path
        label = f"[bold cyan]{category}[/bold cyan]  {_state_icon(category.enabled)}"
        branch = frame.parent.add(f"{label}  [dim]{CYCLE_MARK}[/dim]" if repeated else label)
        if depth_limited and frame.depth + 1 > max_depth:
            continue
        drawn.extend(
            (branch.add(f"[yellow]{item}[/yellow]  {_state_icon(item.enabled)}"), item) for item in frame.node.items
        )
        if repeated:
            continue
        path.add(category.category_id)
        # Pushed before the children so it pops after them: the path holds for the whole descent.
        stack.append(_Leave(category.category_id))
        # Reversed, so that popping restores the children's stored order.
        stack.extend(_Enter(child, branch, frame.depth + 1) for child in reversed(frame.node.children))
    return drawn


def _draw_relations(drawn: Sequence[tuple[Tree, Item]], related: Mapping[UUID, RelatedItems]) -> None:
    """Add the related items of each drawn item under its leaf, as one dim ``[type] → name`` line each."""
    for leaf, item in drawn:
        found = related.get(item.item_id)
        if found is None:
            continue
        for relation_type in found.relation_types:
            relation_label = _markup_escape(f"[{relation_type}]")
            for target in found.of_type(relation_type):
                leaf.add(f"[dim]{relation_label} → {target.name}[/dim]")


@app.command("graph")
def graph_cmd(
    ctx: typer.Context,
    show_relations: bool = typer.Option(
        True, "--show-relations/--no-show-relations", help="Draw each item's outgoing relations"
    ),
    max_depth: int = typer.Option(
        GRAPH_DEFAULT_MAX_DEPTH, "--max-depth", help="Maximum depth to draw; 0 draws every level"
    ),
    state: EnabledState = typer.Option(
        EnabledState.ENABLED, "--state", help="Which rows to draw: enabled (default), disabled, or all"
    ),
) -> None:
    """Draw the taxonomy as a colour-coded tree, from the top-level categories down.

    A category reachable through several parents is drawn under each of them.
    A category already on the path being drawn, which only a cycle in stored
    data produces, is marked ↻ cycle and is not descended into. A drawing with
    too many categories stops with an error that gives the limit and asks for
    a smaller --max-depth.

    \f
    Args:
        ctx: Typer context carrying verbose flag and config path.
        show_relations: When True, draw each drawn item's outgoing relations as dim leaves. They
            are read in one batch for every item drawn.
        max_depth: Maximum depth to render; 0 means unlimited.
        state: Which rows to draw: enabled only (default), disabled only, or all. A filtered
            tree is not the whole tree with rows hidden: a link is kept only when both of its
            ends pass the filter, so a disabled category under an enabled parent loses that
            link. It stays under any parent that the filter keeps; with none, it is not drawn.
            A relation is drawn when its related item passes the filter too.
    """
    result = build(_config_path(ctx))
    _print_verbose(result, _verbose(ctx))
    enabled = STATE_FILTERS[state]
    try:
        graph = result.service.graph(enabled=enabled)
    except TaxomeshError as exc:
        _err(str(exc))
    if not graph.roots:
        typer.echo("No categories found. Add one with: taxomesh category create --name <name>")
        return
    tree = Tree("Taxonomy")
    try:
        drawn = _draw_graph(tree, graph.roots, max_depth=max_depth)
    except TaxomeshError as exc:
        _err(str(exc))
    if show_relations:
        try:
            related = result.service.items.get_many_related([item for _, item in drawn], enabled=enabled)
        except TaxomeshError as exc:
            _err(str(exc))
        _draw_relations(drawn, related)
    Console().print(tree)


if __name__ == "__main__":
    app()
