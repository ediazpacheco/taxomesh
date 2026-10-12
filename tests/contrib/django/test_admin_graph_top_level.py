"""The admin graph's drag-and-drop names the top level with an empty parent, never the root's id.

The graph page renders a top-level category with an empty ``data-parent-uuid``, and the reorder and
reparent endpoints read an empty parent as the top level: ``None`` in ``categories.reorder`` and
``categories.move``. The root's identifier is refused there, as everywhere a category is taken.
"""

import json
import re
from uuid import UUID

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.test import Client  # noqa: E402
from django.urls import reverse  # noqa: E402

from taxomesh import TaxomeshService  # noqa: E402
from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402

pytestmark = pytest.mark.django_db

GRAPH_URL_NAME = "admin:taxomesh_contrib_django_graph"
REORDER_URL_NAME = "admin:taxomesh_contrib_django_graph_reorder"
REPARENT_URL_NAME = "admin:taxomesh_contrib_django_graph_reparent"
TOP_LEVEL = ""


def _service() -> TaxomeshService:
    return TaxomeshService(repository=DjangoRepository())


def _post(client: Client, url_name: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    response = client.post(reverse(url_name), data=json.dumps(payload), content_type="application/json")
    return response.status_code, json.loads(response.content)


def _reparent(
    client: Client, node: UUID, old: str, new: str, before: UUID | None = None
) -> tuple[int, dict[str, object]]:
    return _post(
        client,
        REPARENT_URL_NAME,
        {
            "kind": "category",
            "node_uuid": str(node),
            "old_parent_uuid": old,
            "new_parent_uuid": new,
            "insert_before_uuid": None if before is None else str(before),
        },
    )


def _top_level() -> list[str]:
    return [category.name for category in _service().categories.roots(enabled=None)]


class TestTheGraphPage:
    def test_a_top_level_category_carries_an_empty_parent(self, admin_client: Client) -> None:
        svc = _service()
        music = svc.categories.create("Music")

        page = admin_client.get(reverse(GRAPH_URL_NAME)).content.decode()

        entry = re.search(rf'<[^>]*data-uuid="{music.category_id}"[^>]*>', page)
        assert entry is not None
        assert 'data-parent-uuid=""' in entry.group(0)
        assert str(svc._root_id) not in page


class TestReorder:
    def test_an_empty_parent_orders_the_top_level(self, admin_client: Client) -> None:
        svc = _service()
        alpha = svc.categories.create("Alpha")
        beta = svc.categories.create("Beta")
        gamma = svc.categories.create("Gamma")

        status, body = _post(
            admin_client,
            REORDER_URL_NAME,
            {
                "kind": "category",
                "parent_uuid": TOP_LEVEL,
                "ordered_uuids": [str(gamma.category_id), str(alpha.category_id), str(beta.category_id)],
            },
        )

        assert (status, body) == (200, {"ok": True})
        assert _top_level() == ["Gamma", "Alpha", "Beta"]

    def test_the_roots_identifier_is_refused(self, admin_client: Client) -> None:
        svc = _service()
        alpha = svc.categories.create("Alpha")

        status, _ = _post(
            admin_client,
            REORDER_URL_NAME,
            {"kind": "category", "parent_uuid": str(svc._root_id), "ordered_uuids": [str(alpha.category_id)]},
        )

        assert status == 400

    def test_an_empty_parent_is_no_category_for_items(self, admin_client: Client) -> None:
        svc = _service()
        song = svc.items.create("Song")

        status, _ = _post(
            admin_client,
            REORDER_URL_NAME,
            {"kind": "item", "parent_uuid": TOP_LEVEL, "ordered_uuids": [str(song.item_id)]},
        )

        assert status == 400


class TestReparent:
    def test_from_the_top_level_to_a_category(self, admin_client: Client) -> None:
        svc = _service()
        music = svc.categories.create("Music")
        jazz = svc.categories.create("Jazz")

        status, body = _reparent(admin_client, jazz.category_id, TOP_LEVEL, str(music.category_id))

        assert (status, body) == (200, {"ok": True})
        assert _top_level() == ["Music"]
        assert [c.name for c in svc.categories.list(parent=music.category_id)] == ["Jazz"]

    def test_from_a_category_to_the_top_level(self, admin_client: Client) -> None:
        svc = _service()
        music = svc.categories.create("Music")
        jazz = svc.categories.create("Jazz")
        svc.categories.add_parent(jazz.category_id, music.category_id)

        status, body = _reparent(
            admin_client, jazz.category_id, str(music.category_id), TOP_LEVEL, before=music.category_id
        )

        assert (status, body) == (200, {"ok": True})
        assert _top_level() == ["Jazz", "Music"]

    def test_within_the_top_level(self, admin_client: Client) -> None:
        svc = _service()
        alpha = svc.categories.create("Alpha")
        beta = svc.categories.create("Beta")
        svc.categories.reorder(None, [alpha.category_id, beta.category_id])

        status, body = _reparent(admin_client, beta.category_id, TOP_LEVEL, TOP_LEVEL, before=alpha.category_id)

        assert (status, body) == (200, {"ok": True})
        assert _top_level() == ["Beta", "Alpha"]

    def test_the_roots_identifier_is_refused(self, admin_client: Client) -> None:
        svc = _service()
        music = svc.categories.create("Music")
        jazz = svc.categories.create("Jazz")

        status, _ = _reparent(admin_client, jazz.category_id, str(svc._root_id), str(music.category_id))

        assert status == 400
        assert set(_top_level()) == {"Music", "Jazz"}
