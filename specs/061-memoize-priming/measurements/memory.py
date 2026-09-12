"""Retained memory of the read cache after one list_items(category_id=...) call, on Django.

Run with PYTHONPATH=<version dir>. Builds a corpus of N items in one category with
metadata sized to MEAN_METADATA_BYTES of JSON, then measures what the cache still holds
after the caller has dropped its own reference to the result.
"""

import gc
import json
import sys
import tempfile
import tracemalloc
from pathlib import Path

import django
from django.conf import settings

DB = Path(tempfile.mkdtemp()) / "mem.sqlite3"
settings.configure(
    DEBUG=False,
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(DB)}},
    INSTALLED_APPS=["django.contrib.contenttypes", "django.contrib.auth", "taxomesh.contrib.django"],
    DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    USE_TZ=True,
)
django.setup()
from django.core.management import call_command  # noqa: E402

call_command("migrate", verbosity=0)

from taxomesh import TaxomeshService  # noqa: E402
from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.utils.memoize import clear_all_caches  # noqa: E402

VERSION, N = sys.argv[1], int(sys.argv[2])
MEAN_METADATA_BYTES = 3258  # consumer-stated mean metadata size (spec 061); not re-measured here
DISABLED_EVERY = 10  # 10% disabled, so enabled=True and enabled=None differ


def metadata(i: int) -> dict:
    blocks = [{"type": "credit", "role": f"role-{k}", "name": f"Person {i}-{k}", "note": "x" * 60} for k in range(12)]
    md = {"hero": {"title": f"Hero {i}", "blocks": blocks}, "credits": [f"c{i}-{k}" for k in range(20)]}
    pad = MEAN_METADATA_BYTES - len(json.dumps(md))
    md["body"] = "y" * max(pad, 0)
    return md


svc = TaxomeshService(repository=DjangoRepository())
cat = svc.create_category("Big")
for i in range(N):
    it = svc.create_item(name=f"Item {i}", metadata=metadata(i))
    svc.place_item_in_category(it.item_id, cat.category_id)
    if i % DISABLED_EVERY == 0:
        svc.update_item(it.item_id, enabled=False)


def retained(call) -> int:
    clear_all_caches()
    gc.collect()
    tracemalloc.start()
    base = tracemalloc.get_traced_memory()[0]
    result = call()
    del result
    gc.collect()
    held = tracemalloc.get_traced_memory()[0] - base
    tracemalloc.stop()
    return held


mb = 1024 * 1024
r_enabled = retained(lambda: svc.list_items(category_id=cat.category_id, enabled=True))
r_all = retained(lambda: svc.list_items(category_id=cat.category_id, enabled=None))
r_cats = retained(lambda: svc.list_categories())
print(
    json.dumps(
        {
            "version": VERSION,
            "items": N,
            "metadata_json_bytes_mean": MEAN_METADATA_BYTES,
            "retained_list_items_enabled_true_MB": round(r_enabled / mb, 2),
            "retained_list_items_enabled_none_MB": round(r_all / mb, 2),
            "retained_per_item_KB_enabled_none": round(r_all / N / 1024, 2),
            "retained_list_categories_KB": round(r_cats / 1024, 1),
        }
    )
)
