"""The admin graph's two write views, and the view of a category's children, answer an error as the HTTP edge does.

A library error that the caller can correct answers 400 with its message, and so does an identifier
that is not a UUID in text. A storage failure, and any other exception, answers 500 with one generic
text and a log record, since their own text can name a table, a constraint or a path, whether it
happens as the view builds its service or as it moves. Every answer is JSON with the key ``error``,
which the graph page shows.
"""

import json
import logging
from collections.abc import Callable
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.test import Client  # noqa: E402
from django.urls import reverse  # noqa: E402

from taxomesh import Category, TaxomeshCategoryNotFoundError, TaxomeshRepositoryError, TaxomeshService  # noqa: E402
from taxomesh.contrib.api.errors import GENERIC_SERVER_ERROR_DETAIL  # noqa: E402
from taxomesh.repositories import DjangoRepository  # noqa: E402

pytestmark = pytest.mark.django_db

_PATCH_SERVICE = "taxomesh.contrib.django.admin.TaxomeshService"
SECRET = "no such table: taxomesh_secret_table"


def _reorder(client: Client) -> tuple[int, dict[str, str]]:
    payload = {"kind": "category", "parent_uuid": "", "ordered_uuids": [str(uuid4())]}
    response = client.post(
        reverse("admin:taxomesh_contrib_django_graph_reorder"),
        data=json.dumps(payload),
        content_type="application/json",
    )
    return response.status_code, json.loads(response.content)


def _reparent(client: Client) -> tuple[int, dict[str, str]]:
    payload = {
        "kind": "category",
        "node_uuid": str(uuid4()),
        "old_parent_uuid": "",
        "new_parent_uuid": "",
        "insert_before_uuid": None,
    }
    response = client.post(
        reverse("admin:taxomesh_contrib_django_graph_reparent"),
        data=json.dumps(payload),
        content_type="application/json",
    )
    return response.status_code, json.loads(response.content)


def _children(client: Client, parent: str | None = None) -> tuple[int, dict[str, str]]:
    response = client.get(
        reverse("admin:taxomesh_contrib_django_graph_children"), {"parent_uuid": parent or str(uuid4())}
    )
    return response.status_code, json.loads(response.content)


def _service_that_raises(error: Exception) -> MagicMock:
    service = MagicMock()
    service.categories.reorder.side_effect = error
    service.categories.move.side_effect = error
    service.categories.list.side_effect = error
    return service


VIEWS: dict[str, Callable[[Client], tuple[int, dict[str, str]]]] = {
    "reorder": _reorder,
    "reparent": _reparent,
    "children": _children,
}


def test_the_children_view_answers_a_bad_parameter_with_400_in_the_same_shape(admin_client: Client) -> None:
    assert _children(admin_client, parent="not a uuid") == (400, {"error": "Missing or invalid parent_uuid or depth"})


@pytest.mark.parametrize("view", VIEWS)
class TestAnErrorInAGraphView:
    def test_a_library_error_answers_400_with_its_message(self, admin_client: Client, view: str) -> None:
        error = TaxomeshCategoryNotFoundError("Category not found: sample")
        with patch(_PATCH_SERVICE, return_value=_service_that_raises(error)):
            status, body = VIEWS[view](admin_client)

        assert status == 400
        assert "Category not found: sample" in body["error"]

    def test_a_storage_failure_answers_500_with_the_generic_text_and_a_log_record(
        self, admin_client: Client, view: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        with (
            caplog.at_level(logging.ERROR, logger="taxomesh"),
            patch(_PATCH_SERVICE, return_value=_service_that_raises(TaxomeshRepositoryError(SECRET))),
        ):
            status, body = VIEWS[view](admin_client)

        assert status == 500
        assert body == {"error": GENERIC_SERVER_ERROR_DETAIL}
        ours = [record for record in caplog.records if record.name.startswith("taxomesh")]
        assert [record.levelno for record in ours] == [logging.ERROR]
        assert SECRET not in ours[0].getMessage()

    def test_any_other_exception_answers_500_with_the_generic_text_and_a_log_record(
        self, admin_client: Client, view: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        with (
            caplog.at_level(logging.ERROR, logger="taxomesh"),
            patch(_PATCH_SERVICE, return_value=_service_that_raises(RuntimeError(SECRET))),
        ):
            status, body = VIEWS[view](admin_client)

        assert status == 500
        assert body == {"error": GENERIC_SERVER_ERROR_DETAIL}
        ours = [record for record in caplog.records if record.name.startswith("taxomesh")]
        assert [record.levelno for record in ours] == [logging.ERROR]
        assert SECRET not in ours[0].getMessage()


@pytest.mark.parametrize(
    "url", ["admin:taxomesh_contrib_django_graph_reorder", "admin:taxomesh_contrib_django_graph_reparent"]
)
def test_a_move_whose_body_is_not_a_json_object_answers_400(admin_client: Client, url: str) -> None:
    response = admin_client.post(reverse(url), data="5", content_type="application/json")

    assert (response.status_code, json.loads(response.content)) == (400, {"error": "Invalid JSON"})


REORDER = "admin:taxomesh_contrib_django_graph_reorder"
REPARENT = "admin:taxomesh_contrib_django_graph_reparent"


def _post(client: Client, url: str, payload: dict[str, object]) -> tuple[int, dict[str, str]]:
    response = client.post(reverse(url), data=json.dumps(payload), content_type="application/json")
    return response.status_code, json.loads(response.content)


@pytest.fixture
def stored() -> tuple[TaxomeshService, Category, Category]:
    """Two top-level categories, A then B, in the database that the admin reads."""
    svc = TaxomeshService(DjangoRepository(), cache_ttl=0)
    return svc, svc.categories.create(name="A"), svc.categories.create(name="B")


def _move(url: str, a: Category, b: Category) -> dict[str, object]:
    """A valid body: B before A at the top level, or B moved under A."""
    if url == REORDER:
        return {"kind": "category", "parent_uuid": "", "ordered_uuids": [str(b.category_id), str(a.category_id)]}
    return {
        "kind": "category",
        "node_uuid": str(b.category_id),
        "old_parent_uuid": "",
        "new_parent_uuid": str(a.category_id),
        "insert_before_uuid": None,
    }


@pytest.mark.parametrize(
    ("url", "field"),
    [
        (REORDER, "parent_uuid"),
        (REORDER, "ordered_uuids"),
        (REPARENT, "node_uuid"),
        (REPARENT, "old_parent_uuid"),
        (REPARENT, "new_parent_uuid"),
        (REPARENT, "insert_before_uuid"),
    ],
)
def test_an_identifier_given_as_a_number_answers_400_and_moves_nothing(
    admin_client: Client, stored: tuple[TaxomeshService, Category, Category], url: str, field: str
) -> None:
    svc, a, b = stored
    payload = _move(url, a, b)
    payload[field] = [123] if field == "ordered_uuids" else 123

    assert _post(admin_client, url, payload) == (400, {"error": "Invalid UUID format"})
    assert [c.name for c in svc.categories.roots()] == ["A", "B"]


@pytest.mark.parametrize("url", [REORDER, REPARENT])
def test_a_storage_failure_as_the_view_builds_its_service_answers_500_in_json(
    admin_client: Client,
    stored: tuple[TaxomeshService, Category, Category],
    url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    svc, a, b = stored
    with (
        caplog.at_level(logging.ERROR, logger="taxomesh"),
        patch(_PATCH_SERVICE, side_effect=TaxomeshRepositoryError(SECRET)),
    ):
        answer = _post(admin_client, url, _move(url, a, b))

    assert answer == (500, {"error": GENERIC_SERVER_ERROR_DETAIL})
    assert [record.levelno for record in caplog.records if record.name.startswith("taxomesh")] == [logging.ERROR]
    assert [c.name for c in svc.categories.roots()] == ["A", "B"]


def test_a_storage_failure_as_the_move_reads_the_implicit_root_answers_500_in_json(
    admin_client: Client, stored: tuple[TaxomeshService, Category, Category], caplog: pytest.LogCaptureFixture
) -> None:
    svc, a, b = stored
    with (
        caplog.at_level(logging.ERROR, logger="taxomesh"),
        patch(_PATCH_SERVICE, return_value=MagicMock()),
        patch.object(DjangoRepository, "list_categories", side_effect=TaxomeshRepositoryError(SECRET)),
    ):
        answer = _post(admin_client, REPARENT, _move(REPARENT, a, b))

    assert answer == (500, {"error": GENERIC_SERVER_ERROR_DETAIL})
    assert [record.levelno for record in caplog.records if record.name.startswith("taxomesh")] == [logging.ERROR]
    assert [c.name for c in svc.categories.roots()] == ["A", "B"]
