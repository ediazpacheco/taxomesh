"""LetrasTango's pre-rewrite category walk, on a COPY of its DB, per taxomesh version.

The walk body is copied verbatim from letrastango c842522fc^ views/catalog.py
(_category_paths_from_main), minus its own @memoize. Cold: clear_all_caches() before
every rep. Counted with CaptureQueriesContext, split by table. Median of 3.
"""

import hashlib
import json
import statistics
import sys
from pathlib import Path
from uuid import UUID

import django
from django.conf import settings

DB = Path(__file__).resolve().parent.parent / "lt" / "db_copy.sqlite3"
settings.configure(
    DEBUG=False,
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(DB)}},
    INSTALLED_APPS=["django.contrib.contenttypes", "django.contrib.auth", "taxomesh.contrib.django"],
    DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    USE_TZ=True,
)
django.setup()
from django.db import connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

import taxomesh  # noqa: E402
from taxomesh import TaxomeshService  # noqa: E402
from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.exceptions import TaxomeshCategoryNotFoundError  # noqa: E402
from taxomesh.utils.memoize import clear_all_caches  # noqa: E402

VERSION = sys.argv[1]
ROOT = UUID("d5e8e27d-ba99-4999-b991-3cbec17cbf12")  # MAIN_CATALOG_CATEGORY_ID
service = TaxomeshService(repository=DjangoRepository())


def category_paths_from_main():
    paths_by_category_id = {}

    def _walk(parent_id, path_categories, ancestor_ids):
        try:
            children = service.list_categories(parent_id=parent_id, enabled=True)
        except TaxomeshCategoryNotFoundError:
            return
        for child in children:
            if child.category_id in ancestor_ids:
                continue
            current_path = [*path_categories, child]
            paths_by_category_id.setdefault(child.category_id, current_path)
            _walk(child.category_id, current_path, {child.category_id, *ancestor_ids})

    _walk(ROOT, [], {ROOT})
    return paths_by_category_id


def by_table(queries):
    link = sum('"taxomesh_category_parent_link"' in q["sql"] for q in queries)
    cat = sum('FROM "taxomesh_category"' in q["sql"] and "parent_link" not in q["sql"] for q in queries)
    return link, cat


runs, result = [], None
for _ in range(3):
    clear_all_caches()
    with CaptureQueriesContext(connection) as ctx:
        result = category_paths_from_main()
    runs.append((len(ctx.captured_queries), *by_table(ctx.captured_queries)))
fingerprint = sorted((str(k), [str(c.category_id) for c in v]) for k, v in result.items())
print(
    json.dumps(
        {
            "version": VERSION,
            "file": taxomesh.__file__.split("scratchpad/")[-1],
            "entries": len(result),
            "total": statistics.median(r[0] for r in runs),
            "link": statistics.median(r[1] for r in runs),
            "category": statistics.median(r[2] for r in runs),
            "fingerprint": hashlib.sha256(json.dumps(fingerprint).encode()).hexdigest()[:16],
        }
    )
)
