"""Django admin tests for ItemRelationLink (US7)."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.contrib.admin.sites import AdminSite  # noqa: E402
from django.http import HttpRequest  # noqa: E402

from taxomesh.contrib.django.admin import ItemModelAdmin  # noqa: E402
from taxomesh.contrib.django.models import ItemModel, ItemRelationLinkModel  # noqa: E402

pytestmark = pytest.mark.django_db

_PATCH_TARGET = "taxomesh.contrib.django.admin.TaxomeshService"


def _make_mock_request() -> MagicMock:
    return MagicMock(spec=HttpRequest)


class TestOutgoingRelationInline:
    def test_outgoing_inline_registered_on_item_admin(self) -> None:
        from taxomesh.contrib.django.admin import OutgoingRelationInline  # noqa: PLC0415

        site = AdminSite()
        admin_obj = ItemModelAdmin(ItemModel, site)
        inline_classes = [type(inline) for inline in admin_obj.get_inline_instances(MagicMock())]
        assert OutgoingRelationInline in inline_classes

    def test_incoming_inline_not_registered_on_item_admin(self) -> None:
        from taxomesh.contrib.django.models import ItemRelationLinkModel  # noqa: PLC0415

        site = AdminSite()
        admin_obj = ItemModelAdmin(ItemModel, site)
        inlines = admin_obj.get_inline_instances(MagicMock())
        incoming = [
            i
            for i in inlines
            if getattr(i, "model", None) is ItemRelationLinkModel and getattr(i, "fk_name", None) == "target_item"
        ]
        assert incoming == [], "IncomingRelationInline must not be registered on ItemModelAdmin"

    def test_outgoing_inline_save_calls_service_relate_items(self) -> None:
        from taxomesh.contrib.django.admin import OutgoingRelationInline  # noqa: PLC0415

        site = AdminSite()
        inline = OutgoingRelationInline(ItemModel, site)
        request = _make_mock_request()

        src_id = uuid4()
        tgt_id = uuid4()

        obj = MagicMock(spec=ItemRelationLinkModel)
        obj.source_item_id = src_id
        obj.target_item_id = tgt_id
        obj.relation_type = "covers"
        obj.sort_index = 0
        obj.metadata = {}

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            inline.save_model(request, obj, MagicMock(), False)
            mock_svc.relate_items.assert_called_once_with(src_id, tgt_id, "covers", sort_index=0, metadata={})

    def test_outgoing_inline_delete_calls_service_remove_relation(self) -> None:
        from taxomesh.contrib.django.admin import OutgoingRelationInline  # noqa: PLC0415

        site = AdminSite()
        inline = OutgoingRelationInline(ItemModel, site)
        request = _make_mock_request()

        src_id = uuid4()
        tgt_id = uuid4()

        obj = MagicMock(spec=ItemRelationLinkModel)
        obj.source_item_id = src_id
        obj.target_item_id = tgt_id
        obj.relation_type = "covers"

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            inline.delete_model(request, obj)
            mock_svc.remove_item_relation.assert_called_once_with(src_id, tgt_id, "covers")


class TestItemRelationLinkSelfRelationValidation:
    def test_self_relation_form_raises_validation_error(self) -> None:
        from taxomesh.contrib.django.admin import ItemRelationLinkForm  # noqa: PLC0415

        item_id = uuid4()
        src = ItemModel(item_id=item_id, name="A")
        tgt = ItemModel(item_id=item_id, name="A")  # same ID

        form = ItemRelationLinkForm(
            data={
                "source_item": item_id,
                "target_item": item_id,
                "relation_type": "covers",
                "sort_index": 0,
            }
        )
        form.cleaned_data = {
            "source_item": src,
            "target_item": tgt,
            "relation_type": "covers",
            "sort_index": 0,
            "metadata": {},
        }
        from django import forms as dj_forms  # noqa: PLC0415

        with pytest.raises(dj_forms.ValidationError):
            form.clean()
