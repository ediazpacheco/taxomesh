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

    def test_incoming_inline_registered_on_item_admin(self) -> None:
        from taxomesh.contrib.django.admin import IncomingRelationInline  # noqa: PLC0415

        site = AdminSite()
        admin_obj = ItemModelAdmin(ItemModel, site)
        inline_classes = [type(inline) for inline in admin_obj.get_inline_instances(MagicMock())]
        assert IncomingRelationInline in inline_classes

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


class TestSaveFormsetRelationEdit:
    """Regression tests: editing a relation inline must not duplicate the relation."""

    def _make_formset(self, instances: list, deleted: list, fk_name: str) -> MagicMock:
        fs = MagicMock()
        fs.model = ItemRelationLinkModel
        fs.fk.name = fk_name
        fs.save.return_value = instances
        fs.deleted_objects = deleted
        return fs

    def test_edit_relation_target_removes_old_and_creates_new(self) -> None:
        """Changing target_item on an existing relation must remove old relation first."""
        item_a = ItemModel.objects.create(name="A")
        item_b = ItemModel.objects.create(name="B")
        item_c = ItemModel.objects.create(name="C")

        existing = ItemRelationLinkModel.objects.create(source_item=item_a, target_item=item_b, relation_type="covers")

        modified = ItemRelationLinkModel(
            source_item=item_a, target_item=item_c, relation_type="covers", sort_index=0, metadata={}
        )
        modified.pk = existing.pk

        site = AdminSite()
        admin_obj = ItemModelAdmin(ItemModel, site)
        formset = self._make_formset([modified], [], "source_item")

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            admin_obj.save_formset(MagicMock(), MagicMock(), formset, True)

        mock_svc.remove_item_relation.assert_called_once_with(item_a.item_id, item_b.item_id, "covers")
        mock_svc.relate_items.assert_called_once_with(
            item_a.item_id, item_c.item_id, "covers", sort_index=0, metadata={}
        )

    def test_edit_relation_type_removes_old_and_creates_new(self) -> None:
        """Changing relation_type on an existing relation must remove old relation first."""
        item_a = ItemModel.objects.create(name="A")
        item_b = ItemModel.objects.create(name="B")

        existing = ItemRelationLinkModel.objects.create(source_item=item_a, target_item=item_b, relation_type="covers")

        modified = ItemRelationLinkModel(
            source_item=item_a, target_item=item_b, relation_type="replaces", sort_index=0, metadata={}
        )
        modified.pk = existing.pk

        site = AdminSite()
        admin_obj = ItemModelAdmin(ItemModel, site)
        formset = self._make_formset([modified], [], "source_item")

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            admin_obj.save_formset(MagicMock(), MagicMock(), formset, True)

        mock_svc.remove_item_relation.assert_called_once_with(item_a.item_id, item_b.item_id, "covers")
        mock_svc.relate_items.assert_called_once_with(
            item_a.item_id, item_b.item_id, "replaces", sort_index=0, metadata={}
        )

    def test_edit_non_key_fields_does_not_remove_old_relation(self) -> None:
        """Changing only sort_index/metadata must NOT call remove_item_relation."""
        item_a = ItemModel.objects.create(name="A")
        item_b = ItemModel.objects.create(name="B")

        existing = ItemRelationLinkModel.objects.create(
            source_item=item_a, target_item=item_b, relation_type="covers", sort_index=0
        )

        modified = ItemRelationLinkModel(
            source_item=item_a, target_item=item_b, relation_type="covers", sort_index=5, metadata={}
        )
        modified.pk = existing.pk

        site = AdminSite()
        admin_obj = ItemModelAdmin(ItemModel, site)
        formset = self._make_formset([modified], [], "source_item")

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            admin_obj.save_formset(MagicMock(), MagicMock(), formset, True)

        mock_svc.remove_item_relation.assert_not_called()
        mock_svc.relate_items.assert_called_once_with(
            item_a.item_id, item_b.item_id, "covers", sort_index=5, metadata={}
        )

    def test_new_relation_does_not_call_remove(self) -> None:
        """Adding a new relation (pk=None) must not call remove_item_relation."""
        item_a = ItemModel.objects.create(name="A")
        item_b = ItemModel.objects.create(name="B")

        new_obj = ItemRelationLinkModel(
            source_item=item_a, target_item=item_b, relation_type="covers", sort_index=0, metadata={}
        )
        # pk is None for a new (unsaved) instance

        site = AdminSite()
        admin_obj = ItemModelAdmin(ItemModel, site)
        formset = self._make_formset([new_obj], [], "source_item")

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            admin_obj.save_formset(MagicMock(), MagicMock(), formset, True)

        mock_svc.remove_item_relation.assert_not_called()
        mock_svc.relate_items.assert_called_once()

    def test_incoming_inline_edit_removes_old_relation(self) -> None:
        """Same bug applies to the incoming (target) inline: editing source must remove old relation."""
        item_a = ItemModel.objects.create(name="A")
        item_b = ItemModel.objects.create(name="B")
        item_c = ItemModel.objects.create(name="C")

        existing = ItemRelationLinkModel.objects.create(source_item=item_a, target_item=item_b, relation_type="covers")

        # From the target item's perspective: editing source_item from A to C
        modified = ItemRelationLinkModel(
            source_item=item_c, target_item=item_b, relation_type="covers", sort_index=0, metadata={}
        )
        modified.pk = existing.pk

        site = AdminSite()
        admin_obj = ItemModelAdmin(ItemModel, site)
        formset = self._make_formset([modified], [], "target_item")

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            admin_obj.save_formset(MagicMock(), MagicMock(), formset, True)

        mock_svc.remove_item_relation.assert_called_once_with(item_a.item_id, item_b.item_id, "covers")
        mock_svc.relate_items.assert_called_once_with(
            item_c.item_id, item_b.item_id, "covers", sort_index=0, metadata={}
        )


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
