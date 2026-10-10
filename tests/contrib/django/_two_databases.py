"""Migrate one of two SQLite databases, and print what each holds as one JSON object.

``python -m tests.contrib.django._two_databases <directory> <case>`` builds ``default`` and
``other`` as two files in ``<directory>``, prepares both, migrates ``other`` alone and prints both.
It runs in a process of its own, so its second database never reaches the settings the other
Django tests share. Rows are written and read through the migration state's historical models.
"""

import json
import sys
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import django
from django.apps.registry import Apps
from django.conf import settings
from django.core.management import call_command
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder

from taxomesh.domain.constants import ROOT_CATEGORY_NAME

APP = "taxomesh_contrib_django"
ALIASES = ("default", "other")
BEFORE_EXTERNAL_IDS = "0007_taxomeshdebugproxy"
EXTERNAL_IDS = "0008_unique_external_id"
BEFORE_ROOT_INVARIANT = "0010_item_relation_link_target_type_idx"
ROOT_INVARIANT = "0011_root_invariant"


def _configure(directory: Path) -> None:
    settings.configure(
        INSTALLED_APPS=["django.contrib.contenttypes", "taxomesh.contrib.django"],
        DATABASES={
            alias: {"ENGINE": "django.db.backends.sqlite3", "NAME": str(directory / f"{alias}.sqlite3")}
            for alias in ALIASES
        },
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        USE_TZ=True,
    )
    django.setup()


def _migrate(alias: str, target: str) -> None:
    call_command("migrate", APP, target, database=alias, verbosity=0)


def _models(alias: str, migration: str) -> Apps:
    """The app's models as they stand after ``migration``."""
    return MigrationExecutor(connections[alias]).loader.project_state((APP, migration)).apps


def _seed_root_links(alias: str) -> None:
    """A root link beside another parent, a category with no parent link, and an item in the root."""
    models = _models(alias, BEFORE_ROOT_INVARIANT)
    categories = models.get_model(APP, "CategoryModel").objects.using(alias)
    links = models.get_model(APP, "CategoryParentLinkModel").objects.using(alias)
    root = categories.create(category_id=uuid4(), name=ROOT_CATEGORY_NAME)
    jazz = categories.create(category_id=uuid4(), name="Jazz")
    bop = categories.create(category_id=uuid4(), name="Bop")
    categories.create(category_id=uuid4(), name="Orphan")
    links.create(category=jazz, parent_category=root)
    links.create(category=bop, parent_category=root)
    links.create(category=bop, parent_category=jazz)
    song = models.get_model(APP, "ItemModel").objects.using(alias).create(item_id=uuid4(), name="Song")
    models.get_model(APP, "ItemParentLinkModel").objects.using(alias).create(item=song, category=root)


def _links(alias: str) -> list[str]:
    """Each parent link and item placement, by name, and sorted."""
    models = _models(alias, BEFORE_ROOT_INVARIANT)
    names = dict(models.get_model(APP, "CategoryModel").objects.using(alias).values_list("pk", "name"))
    parents = models.get_model(APP, "CategoryParentLinkModel").objects.using(alias)
    placements = models.get_model(APP, "ItemParentLinkModel").objects.using(alias)
    held = [
        f"{names[child]} -> {names[parent]}" for child, parent in parents.values_list("category", "parent_category")
    ]
    held += [f"Song -> {names[category]}" for category in placements.values_list("category", flat=True)]
    return sorted(held)


def _external_ids(alias: str) -> dict[str, list[str | None]]:
    """The external id each item and each category holds."""
    models = _models(alias, BEFORE_EXTERNAL_IDS)
    return {
        model: list(models.get_model(APP, model).objects.using(alias).values_list("external_id", flat=True))
        for model in ("ItemModel", "CategoryModel")
    }


def _seed_external_id(alias: str, migration: str, external_id: str | None) -> None:
    """Two items and two categories holding ``external_id``, which no unique column takes twice."""
    models = _models(alias, migration)
    for name in ("Jazz", "Tango"):
        models.get_model(APP, "ItemModel").objects.using(alias).create(
            item_id=uuid4(), name=name, external_id=external_id
        )
        models.get_model(APP, "CategoryModel").objects.using(alias).create(
            category_id=uuid4(), name=name, external_id=external_id
        )


def root_invariant() -> dict[str, object]:
    """Both databases at the migration before the root invariant; ``other`` migrated to it."""
    for alias in ALIASES:
        _migrate(alias, BEFORE_ROOT_INVARIANT)
        _seed_root_links(alias)
    before = {alias: _links(alias) for alias in ALIASES}
    _migrate("other", ROOT_INVARIANT)
    return {
        alias: {
            "before": before[alias],
            "after": _links(alias),
            "recorded": (APP, ROOT_INVARIANT) in MigrationRecorder(connections[alias]).applied_migrations(),
        }
        for alias in ALIASES
    }


def empty_external_ids() -> dict[str, object]:
    """Both databases before the external-id migration, each with ``''``; ``other`` migrated."""
    for alias in ALIASES:
        _migrate(alias, BEFORE_EXTERNAL_IDS)
        _seed_external_id(alias, BEFORE_EXTERNAL_IDS, "")
    _migrate("other", EXTERNAL_IDS)
    return {alias: _external_ids(alias) for alias in ALIASES}


def null_external_ids() -> dict[str, object]:
    """Both databases at the external-id migration, each with no external id; ``other`` migrated back."""
    for alias in ALIASES:
        _migrate(alias, EXTERNAL_IDS)
        _seed_external_id(alias, EXTERNAL_IDS, None)
    _migrate("other", BEFORE_EXTERNAL_IDS)
    return {alias: _external_ids(alias) for alias in ALIASES}


def only_other() -> dict[str, object]:
    """Every migration on ``other``, with nothing migrated on ``default``."""
    call_command("migrate", database="other", verbosity=0)
    return {alias: sorted(connections[alias].introspection.table_names()) for alias in ALIASES}


CASES: dict[str, Callable[[], dict[str, object]]] = {
    "root-invariant": root_invariant,
    "empty-external-ids": empty_external_ids,
    "null-external-ids": null_external_ids,
    "only-other": only_other,
}


def main(directory: str, case: str) -> None:
    _configure(Path(directory))
    print(json.dumps(CASES[case]()))


if __name__ == "__main__":
    main(*sys.argv[1:])
