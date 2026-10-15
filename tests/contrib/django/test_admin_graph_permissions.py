"""The admin graph's moves need the change permission of the kind they move; its reads need a staff user.

A move of a category, by drag and drop on the graph page, needs the permission to change categories,
and a move of an item the permission to change items, as their own admin pages do. A refusal answers
403 and changes nothing. The graph page and a category's children are open to every staff user. Every
view needs a login, and every move a CSRF token. The real Django test client posts to each URL.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.contrib.auth.models import Permission, User  # noqa: E402
from django.test import Client  # noqa: E402
from django.urls import reverse  # noqa: E402

from taxomesh import TaxomeshService  # noqa: E402
from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.domain.models import Category, Item  # noqa: E402

pytestmark = pytest.mark.django_db

REORDER: Final[str] = "admin:taxomesh_contrib_django_graph_reorder"
REPARENT: Final[str] = "admin:taxomesh_contrib_django_graph_reparent"
GRAPH: Final[str] = "admin:taxomesh_contrib_django_graph"
CHILDREN: Final[str] = "admin:taxomesh_contrib_django_graph_children"


@dataclass(frozen=True)
class Scene:
    """Categories A, B and C at the top level, and items I and J placed in A, in that order."""

    a: Category
    b: Category
    c: Category
    i: Item
    j: Item


@pytest.fixture
def scene() -> Scene:
    svc = TaxomeshService(DjangoRepository(), cache_ttl=0)
    a, b, c = (svc.categories.create(name) for name in "ABC")
    i, j = (svc.items.create(name) for name in "IJ")
    svc.items.place_in(i, a)
    svc.items.place_in(j, a)
    return Scene(a, b, c, i, j)


def _state(scene: Scene) -> dict[str, list[str]]:
    """The top level, A's children, and the items of A and of B, by name."""
    svc = TaxomeshService(DjangoRepository(), cache_ttl=0)
    return {
        "top": [category.name for category in svc.categories.roots()],
        "under A": [category.name for category in svc.categories.list(parent=scene.a)],
        "in A": [item.name for item in svc.items.list(category=scene.a)],
        "in B": [item.name for item in svc.items.list(category=scene.b)],
    }


def _client(*codenames: str, superuser: bool = False) -> Client:
    """A client logged in as a staff user who holds these permissions of the taxomesh app."""
    user = User.objects.create_user(f"user{User.objects.count()}", is_staff=True, is_superuser=superuser)
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
    client = Client()
    client.force_login(user)
    return client


def _post(client: Client, url: str, payload: Mapping[str, object]) -> int:
    response = client.post(reverse(url), data=json.dumps(payload), content_type="application/json")
    return response.status_code


def _move_category(client: Client, scene: Scene) -> int:
    payload = {
        "kind": "category",
        "node_uuid": str(scene.b.category_id),
        "old_parent_uuid": "",
        "new_parent_uuid": str(scene.a.category_id),
        "insert_before_uuid": None,
    }
    return _post(client, REPARENT, payload)


def _reorder_categories(client: Client, scene: Scene) -> int:
    order = [str(category.category_id) for category in (scene.c, scene.b, scene.a)]
    return _post(client, REORDER, {"kind": "category", "parent_uuid": "", "ordered_uuids": order})


def _move_item(client: Client, scene: Scene) -> int:
    payload = {
        "kind": "item",
        "node_uuid": str(scene.i.item_id),
        "old_parent_uuid": str(scene.a.category_id),
        "new_parent_uuid": str(scene.b.category_id),
        "insert_before_uuid": None,
    }
    return _post(client, REPARENT, payload)


def _reorder_items(client: Client, scene: Scene) -> int:
    order = [str(scene.j.item_id), str(scene.i.item_id)]
    return _post(client, REORDER, {"kind": "item", "parent_uuid": str(scene.a.category_id), "ordered_uuids": order})


UNCHANGED: Final[dict[str, list[str]]] = {"top": ["A", "B", "C"], "under A": [], "in A": ["I", "J"], "in B": []}


@pytest.mark.parametrize(
    "codenames",
    [(), ("view_categorymodel", "view_itemmodel"), ("change_itemmodel",)],
    ids=["no permission", "view only", "items only"],
)
def test_a_staff_user_who_may_not_change_categories_cannot_move_one(scene: Scene, codenames: tuple[str, ...]) -> None:
    client = _client(*codenames)

    assert (_move_category(client, scene), _reorder_categories(client, scene)) == (403, 403)
    assert _state(scene) == UNCHANGED


@pytest.mark.parametrize(
    "codenames",
    [(), ("view_categorymodel", "view_itemmodel"), ("change_categorymodel",)],
    ids=["no permission", "view only", "categories only"],
)
def test_a_staff_user_who_may_not_change_items_cannot_move_one(scene: Scene, codenames: tuple[str, ...]) -> None:
    client = _client(*codenames)

    assert (_move_item(client, scene), _reorder_items(client, scene)) == (403, 403)
    assert _state(scene) == UNCHANGED


def test_the_permission_to_change_categories_moves_categories(scene: Scene) -> None:
    client = _client("change_categorymodel")

    assert _reorder_categories(client, scene) == 200
    assert _move_category(client, scene) == 200
    assert _state(scene) == {"top": ["C", "A"], "under A": ["B"], "in A": ["I", "J"], "in B": []}


def test_the_permission_to_change_items_moves_items(scene: Scene) -> None:
    client = _client("change_itemmodel")

    assert _reorder_items(client, scene) == 200
    assert _move_item(client, scene) == 200
    assert _state(scene) == {"top": ["A", "B", "C"], "under A": [], "in A": ["J"], "in B": ["I"]}


def test_a_superuser_moves_both_kinds(scene: Scene) -> None:
    client = _client(superuser=True)

    assert [_move_category(client, scene), _move_item(client, scene)] == [200, 200]


@pytest.mark.parametrize("codenames", [(), ("view_categorymodel",)], ids=["no permission", "view only"])
def test_the_graph_and_a_categorys_children_answer_every_staff_user(scene: Scene, codenames: tuple[str, ...]) -> None:
    client = _client(*codenames)

    page = client.get(reverse(GRAPH))
    children = client.get(reverse(CHILDREN), {"parent_uuid": str(scene.a.category_id)})

    assert (page.status_code, children.status_code) == (200, 200)
    assert "I" in children.content.decode()


def test_an_anonymous_user_is_sent_to_the_login_page(scene: Scene) -> None:
    client = Client()
    answers = [
        client.get(reverse(GRAPH)),
        client.get(reverse(CHILDREN), {"parent_uuid": str(scene.a.category_id)}),
        client.post(reverse(REPARENT), data="{}", content_type="application/json"),
        client.post(reverse(REORDER), data="{}", content_type="application/json"),
    ]

    assert [answer.status_code for answer in answers] == [302, 302, 302, 302]
    assert all("/login/" in answer["Location"] for answer in answers)


def test_a_move_without_a_csrf_token_is_refused(scene: Scene) -> None:
    client = Client(enforce_csrf_checks=True)
    client.force_login(User.objects.create_user("checked", is_staff=True, is_superuser=True))

    assert _move_category(client, scene) == 403
    assert _state(scene) == UNCHANGED
