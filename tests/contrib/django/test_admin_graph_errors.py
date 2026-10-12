"""The admin graph's two write views answer an error as the HTTP edge does.

A library error that the caller can correct answers 400 with its message. A storage failure, and
any other exception, answers 500 with one generic text and a log record, since their own text can
name a table, a constraint or a path.
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

from taxomesh import TaxomeshCategoryNotFoundError, TaxomeshRepositoryError  # noqa: E402
from taxomesh.contrib.api.errors import GENERIC_SERVER_ERROR_DETAIL  # noqa: E402

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


def _service_that_raises(error: Exception) -> MagicMock:
    service = MagicMock()
    service.categories.reorder.side_effect = error
    service.categories.move.side_effect = error
    return service


VIEWS: dict[str, Callable[[Client], tuple[int, dict[str, str]]]] = {"reorder": _reorder, "reparent": _reparent}


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
