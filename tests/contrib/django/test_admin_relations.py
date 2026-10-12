"""Django admin tests for ItemRelationLink."""

from unittest.mock import MagicMock, call, patch
from uuid import UUID, uuid4

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.contrib.admin.sites import AdminSite  # noqa: E402
from django.http import HttpRequest  # noqa: E402

from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.application.service import TaxomeshService  # noqa: E402
from taxomesh.contrib.django.admin import ItemModelAdmin  # noqa: E402
from taxomesh.contrib.django.models import ItemModel, ItemRelationLinkModel  # noqa: E402
from taxomesh.domain.models import ItemRelationLink  # noqa: E402
from taxomesh.exceptions import TaxomeshRelationError  # noqa: E402

pytestmark = pytest.mark.django_db

_PATCH_TARGET = "taxomesh.contrib.django.admin.TaxomeshService"


def _make_mock_request() -> MagicMock:
    return MagicMock(spec=HttpRequest)


def _relate_as_stored(
    source: UUID, target: UUID, relation_type: str, *, sort_index: int = 0, metadata: dict[str, object] | None = None
) -> ItemRelationLink:
    """Stand in for ``items.relate`` in a mocked service: return the link it would store."""
    return ItemRelationLink(
        source_item_id=source,
        target_item_id=target,
        relation_type=relation_type,
        sort_index=sort_index,
        metadata=metadata if metadata is not None else {},
    )


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


class TestSaveFormsetRelationEdit:
    """Regression tests: editing a relation inline must not duplicate the relation."""

    def _make_formset(
        self, instances: list[ItemRelationLinkModel], deleted: list[ItemRelationLinkModel], fk_name: str
    ) -> MagicMock:
        fs = MagicMock()
        fs.model = ItemRelationLinkModel
        fs.fk.name = fk_name
        fs.save.return_value = instances
        fs.deleted_objects = deleted
        return fs

    def test_edit_relation_target_removes_old_and_creates_new(self) -> None:
        """Changing target_item on an existing relation stores the new relation and removes the old one."""
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
            mock_svc.items.relate.side_effect = _relate_as_stored
            MockSvc.return_value = mock_svc
            admin_obj.save_formset(MagicMock(), MagicMock(), formset, True)

        mock_svc.items.unrelate.assert_called_once_with(item_a.item_id, item_b.item_id, "covers")
        mock_svc.items.relate.assert_called_once_with(
            item_a.item_id, item_c.item_id, "covers", sort_index=0, metadata={}
        )

    def test_edit_relation_type_removes_old_and_creates_new(self) -> None:
        """Changing relation_type on an existing relation stores the new relation and removes the old one."""
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
            mock_svc.items.relate.side_effect = _relate_as_stored
            MockSvc.return_value = mock_svc
            admin_obj.save_formset(MagicMock(), MagicMock(), formset, True)

        mock_svc.items.unrelate.assert_called_once_with(item_a.item_id, item_b.item_id, "covers")
        mock_svc.items.relate.assert_called_once_with(
            item_a.item_id, item_b.item_id, "replaces", sort_index=0, metadata={}
        )

    def test_edit_non_key_fields_does_not_remove_old_relation(self) -> None:
        """Changing only sort_index/metadata must NOT call items.unrelate."""
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
            mock_svc.items.relate.side_effect = _relate_as_stored
            MockSvc.return_value = mock_svc
            admin_obj.save_formset(MagicMock(), MagicMock(), formset, True)

        mock_svc.items.unrelate.assert_not_called()
        mock_svc.items.relate.assert_called_once_with(
            item_a.item_id, item_b.item_id, "covers", sort_index=5, metadata={}
        )

    def test_new_relation_does_not_call_remove(self) -> None:
        """Adding a new relation (pk=None) must not call items.unrelate."""
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
            mock_svc.items.relate.side_effect = _relate_as_stored
            MockSvc.return_value = mock_svc
            admin_obj.save_formset(MagicMock(), MagicMock(), formset, True)

        mock_svc.items.unrelate.assert_not_called()
        mock_svc.items.relate.assert_called_once()

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
            mock_svc.items.relate.side_effect = _relate_as_stored
            MockSvc.return_value = mock_svc
            admin_obj.save_formset(MagicMock(), MagicMock(), formset, True)

        mock_svc.items.unrelate.assert_called_once_with(item_a.item_id, item_b.item_id, "covers")
        mock_svc.items.relate.assert_called_once_with(
            item_c.item_id, item_b.item_id, "covers", sort_index=0, metadata={}
        )


class TestSaveFormsetRelationOrder:
    """Each row stores its new relation before it removes the old one, after the deleted rows go.

    A refused ``relate`` then leaves the row's stored relation as it was, and a row edited onto the
    key of a row deleted in the same submission keeps its relation.
    """

    @staticmethod
    def _save(
        instances: list[ItemRelationLinkModel],
        deleted: list[ItemRelationLinkModel],
        *,
        refusal: Exception | None = None,
    ) -> MagicMock:
        """Save the outgoing inline through a mocked service, whose ``relate`` raises ``refusal``."""
        formset = MagicMock()
        formset.model = ItemRelationLinkModel
        formset.fk.name = "source_item"
        formset.save.return_value = instances
        formset.deleted_objects = deleted
        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            mock_svc.items.relate.side_effect = _relate_as_stored if refusal is None else refusal
            MockSvc.return_value = mock_svc
            ItemModelAdmin(ItemModel, AdminSite()).save_formset(MagicMock(), MagicMock(), formset, True)
        return mock_svc

    @staticmethod
    def _retargeted(source: ItemModel, old: ItemModel, new: ItemModel) -> ItemRelationLinkModel:
        """A stored ``covers`` relation from ``source`` to ``old``, edited to point at ``new``."""
        stored = ItemRelationLinkModel.objects.create(source_item=source, target_item=old, relation_type="covers")
        edited = ItemRelationLinkModel(source_item=source, target_item=new, relation_type="covers", metadata={})
        edited.pk = stored.pk
        return edited

    def test_the_new_relation_is_stored_before_the_old_one_goes(self) -> None:
        item_a, item_b, item_c = (ItemModel.objects.create(name=name) for name in "ABC")

        mock_svc = self._save([self._retargeted(item_a, item_b, item_c)], [])

        assert mock_svc.items.mock_calls == [
            call.relate(item_a.item_id, item_c.item_id, "covers", sort_index=0, metadata={}),
            call.unrelate(item_a.item_id, item_b.item_id, "covers"),
        ]

    def test_a_refused_edit_keeps_the_old_relation(self) -> None:
        item_a, item_b, item_c = (ItemModel.objects.create(name=name) for name in "ABC")

        mock_svc = self._save([self._retargeted(item_a, item_b, item_c)], [], refusal=TaxomeshRelationError("Refused"))

        mock_svc.items.unrelate.assert_not_called()

    def test_a_deleted_row_goes_before_a_row_edited_onto_its_key(self) -> None:
        item_a, item_b, item_c = (ItemModel.objects.create(name=name) for name in "ABC")
        deleted = ItemRelationLinkModel.objects.create(source_item=item_a, target_item=item_b, relation_type="covers")

        mock_svc = self._save([self._retargeted(item_a, item_c, item_b)], [deleted])

        assert mock_svc.items.mock_calls == [
            call.unrelate(item_a.item_id, item_b.item_id, "covers"),
            call.relate(item_a.item_id, item_b.item_id, "covers", sort_index=0, metadata={}),
            call.unrelate(item_a.item_id, item_c.item_id, "covers"),
        ]


class TestSaveFormsetRelationKeepsItsKey:
    """An edit the service stores under the relation's own key keeps that relation, with its edits.

    ``relate`` stores a relation type stripped and lowercased, so a row edited to ``COVERS`` is the
    stored ``covers`` relation edited, not a new one. The real service and ORM run; only the formset
    is a stand-in.
    """

    @staticmethod
    def _save(edited: ItemRelationLinkModel, fk_name: str) -> None:
        """Save ``edited`` through the item admin's inline named by ``fk_name``."""
        formset = MagicMock()
        formset.model = ItemRelationLinkModel
        formset.fk.name = fk_name
        formset.save.return_value = [edited]
        formset.deleted_objects = []
        ItemModelAdmin(ItemModel, AdminSite()).save_formset(MagicMock(), MagicMock(), formset, True)

    @staticmethod
    def _edited(stored: ItemRelationLinkModel, *, target: UUID, relation_type: str) -> ItemRelationLinkModel:
        """The stored row as the inline's form hands it back: same pk, the edited fields."""
        edited = ItemRelationLinkModel(
            source_item_id=stored.source_item_id,
            target_item_id=target,
            relation_type=relation_type,
            sort_index=7,
            metadata={"edited": True},
        )
        edited.pk = stored.pk
        return edited

    @pytest.mark.parametrize("fk_name", ["source_item", "target_item"])
    @pytest.mark.parametrize("typed", ["COVERS", " covers "])
    def test_an_edit_onto_the_same_key_keeps_the_relation(self, fk_name: str, typed: str) -> None:
        svc = TaxomeshService(repository=DjangoRepository())
        item_a, item_b = svc.items.create("A"), svc.items.create("B")
        svc.items.relate(item_a, item_b, "covers")
        stored = ItemRelationLinkModel.objects.get()

        self._save(self._edited(stored, target=item_b.item_id, relation_type=typed), fk_name)

        kept = svc.items.list_relations(item_a)
        assert [(link.target_item_id, link.relation_type, link.sort_index) for link in kept] == [
            (item_b.item_id, "covers", 7)
        ]
        assert kept[0].metadata == {"edited": True}

    def test_a_retarget_still_removes_the_old_relation(self) -> None:
        svc = TaxomeshService(repository=DjangoRepository())
        item_a, item_b, item_c = (svc.items.create(name) for name in "ABC")
        svc.items.relate(item_a, item_b, "covers")
        stored = ItemRelationLinkModel.objects.get()

        self._save(self._edited(stored, target=item_c.item_id, relation_type="covers"), "source_item")

        kept = svc.items.list_relations(item_a)
        assert [(link.target_item_id, link.relation_type) for link in kept] == [(item_c.item_id, "covers")]


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
