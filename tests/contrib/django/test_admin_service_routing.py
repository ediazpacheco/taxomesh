"""Tests verifying that every Django admin mutation routes through TaxomeshService.

All tests in this module patch ``taxomesh.contrib.django.admin.TaxomeshService``
to inject a mock service instance, then trigger the relevant admin method and
assert the correct service method was called with the right arguments.

No test in this module calls ``super()`` methods or writes directly to the ORM.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.contrib.admin.sites import AdminSite  # noqa: E402
from django.http import HttpRequest  # noqa: E402

from taxomesh.contrib.django.admin import CategoryModelAdmin  # noqa: E402
from taxomesh.contrib.django.models import (  # noqa: E402
    CategoryModel,
    CategoryParentLinkModel,
    ItemModel,
    ItemParentLinkModel,
    ItemTagLinkModel,
    TagModel,
)

pytestmark = pytest.mark.django_db

_PATCH_TARGET = "taxomesh.contrib.django.admin.TaxomeshService"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_request() -> MagicMock:
    """Return a minimal mock HttpRequest."""
    return MagicMock(spec=HttpRequest)


# ---------------------------------------------------------------------------
# T010 — CategoryParentLinkInline tests
# ---------------------------------------------------------------------------


class TestCategoryParentLinkInline:
    """Tests for CategoryParentLinkInline service routing."""

    def test_inline_registered_on_category_admin(self) -> None:
        """CategoryParentLinkInline must appear in CategoryModelAdmin.inlines."""
        from taxomesh.contrib.django.admin import CategoryParentLinkInline  # noqa: PLC0415

        site = AdminSite()
        admin_obj = CategoryModelAdmin(CategoryModel, site)
        inline_classes = [type(inline) for inline in admin_obj.get_inline_instances(MagicMock())]
        assert CategoryParentLinkInline in inline_classes

    def test_add_parent_link_via_inline_calls_service(self) -> None:
        """Inline save_model calls service.add_category_parent with correct IDs."""
        from taxomesh.contrib.django.admin import CategoryParentLinkInline  # noqa: PLC0415

        site = AdminSite()
        inline = CategoryParentLinkInline(CategoryModel, site)
        request = _make_mock_request()

        obj = MagicMock(spec=CategoryParentLinkModel)
        obj.category_id = uuid4()
        obj.parent_category_id = uuid4()
        obj.sort_index = 0

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            inline.save_model(request, obj, MagicMock(), False)
            mock_svc.add_category_parent.assert_called_once_with(
                category_id=obj.category_id,
                parent_id=obj.parent_category_id,
                sort_index=obj.sort_index,
            )

    def test_cycle_detection_raises_validation_error(self) -> None:
        """When service raises TaxomeshCyclicDependencyError in save_model, message_user is called."""
        from taxomesh.contrib.django.admin import CategoryParentLinkInline  # noqa: PLC0415
        from taxomesh.exceptions import TaxomeshCyclicDependencyError  # noqa: PLC0415

        site = AdminSite()
        inline = CategoryParentLinkInline(CategoryModel, site)
        request = _make_mock_request()

        obj = MagicMock(spec=CategoryParentLinkModel)
        obj.category_id = uuid4()
        obj.parent_category_id = uuid4()
        obj.sort_index = 0

        # Verify: cycle detection calls message_user on the inline; no data written
        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            mock_svc.add_category_parent.side_effect = TaxomeshCyclicDependencyError("cycle!")
            with patch.object(inline, "message_user", create=True) as mock_msg:
                inline.save_model(request, obj, MagicMock(), False)
                mock_msg.assert_called_once()
                # Assert service was NOT called a second time (no data written beyond the error)
                mock_svc.add_category_parent.assert_called_once()

    def test_delete_parent_link_via_inline_calls_service(self) -> None:
        """Inline delete_model calls service.remove_category_parent."""
        from taxomesh.contrib.django.admin import CategoryParentLinkInline  # noqa: PLC0415

        site = AdminSite()
        inline = CategoryParentLinkInline(CategoryModel, site)
        request = _make_mock_request()

        obj = MagicMock(spec=CategoryParentLinkModel)
        obj.category_id = uuid4()
        obj.parent_category_id = uuid4()

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            inline.delete_model(request, obj)
            mock_svc.remove_category_parent.assert_called_once_with(
                category_id=obj.category_id,
                parent_id=obj.parent_category_id,
            )


# ---------------------------------------------------------------------------
# T015 — CategoryModelAdmin service routing
# ---------------------------------------------------------------------------


class TestCategoryModelAdminServiceRouting:
    """Tests for CategoryModelAdmin CRUD routing through TaxomeshService."""

    def test_save_model_create_calls_service(self) -> None:
        """save_model with change=False calls service.create_category."""
        site = AdminSite()
        admin_obj = CategoryModelAdmin(CategoryModel, site)
        request = _make_mock_request()

        mock_obj = MagicMock(spec=CategoryModel)
        mock_obj.name = "TestCat"
        mock_obj.description = "desc"
        mock_obj.enabled = True
        mock_obj.external_id = ""
        mock_obj._state = MagicMock()  # _state is a runtime instance attr; not in spec

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            admin_obj.save_model(request, mock_obj, MagicMock(), False)
            mock_svc.create_category.assert_called_once()

    def test_save_model_update_calls_service(self) -> None:
        """save_model with change=True calls service.update_category."""
        site = AdminSite()
        admin_obj = CategoryModelAdmin(CategoryModel, site)
        request = _make_mock_request()

        mock_obj = MagicMock(spec=CategoryModel)
        mock_obj.category_id = uuid4()
        mock_obj.name = "UpdatedCat"
        mock_obj.description = "desc"
        mock_obj.enabled = True
        mock_obj.external_id = ""

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            admin_obj.save_model(request, mock_obj, MagicMock(), True)
            mock_svc.update_category.assert_called_once()

    def test_delete_model_calls_service(self) -> None:
        """delete_model calls service.delete_category(category_id)."""
        site = AdminSite()
        admin_obj = CategoryModelAdmin(CategoryModel, site)
        request = _make_mock_request()

        mock_obj = MagicMock(spec=CategoryModel)
        mock_obj.category_id = uuid4()

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            admin_obj.delete_model(request, mock_obj)
            mock_svc.delete_category.assert_called_once_with(mock_obj.category_id)

    def test_delete_queryset_calls_service_per_object(self) -> None:
        """delete_queryset calls service.delete_category once per object."""
        site = AdminSite()
        admin_obj = CategoryModelAdmin(CategoryModel, site)
        request = _make_mock_request()

        obj1 = MagicMock(spec=CategoryModel)
        obj1.category_id = uuid4()
        obj2 = MagicMock(spec=CategoryModel)
        obj2.category_id = uuid4()

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            admin_obj.delete_queryset(request, [obj1, obj2])
            assert mock_svc.delete_category.call_count == 2

    def test_validation_error_in_save_model_surfaced_via_message(self) -> None:
        """TaxomeshValidationError in save_model surfaces via message_user(ERROR), no ORM write."""
        from taxomesh.exceptions import TaxomeshValidationError  # noqa: PLC0415

        site = AdminSite()
        admin_obj = CategoryModelAdmin(CategoryModel, site)
        request = _make_mock_request()

        mock_obj = MagicMock(spec=CategoryModel)
        mock_obj.name = "Bad"
        mock_obj.description = ""
        mock_obj.enabled = True
        mock_obj.external_id = ""

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            mock_svc.create_category.side_effect = TaxomeshValidationError("bad name")
            with patch.object(admin_obj, "message_user") as mock_msg:
                admin_obj.save_model(request, mock_obj, MagicMock(), False)
                mock_msg.assert_called_once()

    def test_error_in_delete_model_surfaced_via_message(self) -> None:
        """TaxomeshError in delete_model surfaces via message_user(ERROR)."""
        from taxomesh.exceptions import TaxomeshError  # noqa: PLC0415

        site = AdminSite()
        admin_obj = CategoryModelAdmin(CategoryModel, site)
        request = _make_mock_request()

        mock_obj = MagicMock(spec=CategoryModel)
        mock_obj.category_id = uuid4()

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            mock_svc.delete_category.side_effect = TaxomeshError("cannot delete")
            with patch.object(admin_obj, "message_user") as mock_msg:
                admin_obj.delete_model(request, mock_obj)
                mock_msg.assert_called_once()

    def test_save_model_create_syncs_obj_state(self) -> None:
        """After save_model(change=False), obj.category_id matches the service result and
        obj._state.adding is False so Django can use obj as a FK target for inline saves."""
        from taxomesh.domain.models.category import Category  # noqa: PLC0415

        site = AdminSite()
        admin_obj = CategoryModelAdmin(CategoryModel, site)
        request = _make_mock_request()

        obj = CategoryModel(name="New Cat")  # real instance; _state.adding=True initially
        created_category_id = uuid4()
        mock_domain_cat = MagicMock(spec=Category)
        mock_domain_cat.category_id = created_category_id

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            mock_svc.create_category.return_value = mock_domain_cat
            admin_obj.save_model(request, obj, MagicMock(), False)

        assert obj.category_id == created_category_id
        assert obj._state.adding is False


# ---------------------------------------------------------------------------
# T020 — ItemModelAdmin service routing
# ---------------------------------------------------------------------------


class TestItemModelAdminServiceRouting:
    """Tests for ItemModelAdmin CRUD routing through TaxomeshService."""

    def test_save_model_create_calls_service(self) -> None:
        """save_model with change=False calls service.create_item."""
        from taxomesh.contrib.django.admin import ItemModelAdmin  # noqa: PLC0415

        site = AdminSite()
        admin_obj = ItemModelAdmin(ItemModel, site)
        request = _make_mock_request()

        mock_obj = MagicMock(spec=ItemModel)
        mock_obj.external_id = "ext-1"
        mock_obj.enabled = True
        mock_obj._state = MagicMock()  # _state is a runtime instance attr; not in spec

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            admin_obj.save_model(request, mock_obj, MagicMock(), False)
            mock_svc.create_item.assert_called_once()

    def test_save_model_update_calls_service(self) -> None:
        """save_model with change=True calls service.update_item."""
        from taxomesh.contrib.django.admin import ItemModelAdmin  # noqa: PLC0415

        site = AdminSite()
        admin_obj = ItemModelAdmin(ItemModel, site)
        request = _make_mock_request()

        mock_obj = MagicMock(spec=ItemModel)
        mock_obj.item_id = uuid4()
        mock_obj.enabled = False

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            admin_obj.save_model(request, mock_obj, MagicMock(), True)
            mock_svc.update_item.assert_called_once()

    def test_delete_model_calls_service(self) -> None:
        """delete_model calls service.delete_item(item_id)."""
        from taxomesh.contrib.django.admin import ItemModelAdmin  # noqa: PLC0415

        site = AdminSite()
        admin_obj = ItemModelAdmin(ItemModel, site)
        request = _make_mock_request()

        mock_obj = MagicMock(spec=ItemModel)
        mock_obj.item_id = uuid4()

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            admin_obj.delete_model(request, mock_obj)
            mock_svc.delete_item.assert_called_once_with(mock_obj.item_id)

    def test_delete_queryset_calls_service_per_object(self) -> None:
        """delete_queryset calls service.delete_item once per object."""
        from taxomesh.contrib.django.admin import ItemModelAdmin  # noqa: PLC0415

        site = AdminSite()
        admin_obj = ItemModelAdmin(ItemModel, site)
        request = _make_mock_request()

        obj1 = MagicMock(spec=ItemModel)
        obj1.item_id = uuid4()
        obj2 = MagicMock(spec=ItemModel)
        obj2.item_id = uuid4()

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            admin_obj.delete_queryset(request, [obj1, obj2])
            assert mock_svc.delete_item.call_count == 2

    def test_error_in_save_model_surfaced_via_message(self) -> None:
        """TaxomeshError in save_model surfaces via message_user(ERROR)."""
        from taxomesh.contrib.django.admin import ItemModelAdmin  # noqa: PLC0415
        from taxomesh.exceptions import TaxomeshValidationError  # noqa: PLC0415

        site = AdminSite()
        admin_obj = ItemModelAdmin(ItemModel, site)
        request = _make_mock_request()

        mock_obj = MagicMock(spec=ItemModel)
        mock_obj.external_id = "bad"
        mock_obj.enabled = True

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            mock_svc.create_item.side_effect = TaxomeshValidationError("bad external_id")
            with patch.object(admin_obj, "message_user") as mock_msg:
                admin_obj.save_model(request, mock_obj, MagicMock(), False)
                mock_msg.assert_called_once()

    def test_save_model_create_syncs_obj_state(self) -> None:
        """After save_model(change=False), obj.item_id matches the service result and
        obj._state.adding is False so Django can use obj as a FK target for inline saves."""
        from taxomesh.contrib.django.admin import ItemModelAdmin  # noqa: PLC0415
        from taxomesh.domain.models.item import Item  # noqa: PLC0415

        site = AdminSite()
        admin_obj = ItemModelAdmin(ItemModel, site)
        request = _make_mock_request()

        obj = ItemModel(external_id="ext-1")  # real instance; _state.adding=True initially
        created_item_id = uuid4()
        mock_domain_item = MagicMock(spec=Item)
        mock_domain_item.item_id = created_item_id

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            mock_svc.create_item.return_value = mock_domain_item
            admin_obj.save_model(request, obj, MagicMock(), False)

        assert obj.item_id == created_item_id
        assert obj._state.adding is False


# ---------------------------------------------------------------------------
# T021 — TagModelAdmin service routing
# ---------------------------------------------------------------------------


class TestTagModelAdminServiceRouting:
    """Tests for TagModelAdmin CRUD routing through TaxomeshService."""

    def test_save_model_create_calls_service(self) -> None:
        """save_model with change=False calls service.create_tag."""
        from taxomesh.contrib.django.admin import TagModelAdmin  # noqa: PLC0415

        site = AdminSite()
        admin_obj = TagModelAdmin(TagModel, site)
        request = _make_mock_request()

        mock_obj = MagicMock(spec=TagModel)
        mock_obj.name = "mytag"

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            admin_obj.save_model(request, mock_obj, MagicMock(), False)
            mock_svc.create_tag.assert_called_once()

    def test_save_model_update_calls_service(self) -> None:
        """save_model with change=True calls service.update_tag."""
        from taxomesh.contrib.django.admin import TagModelAdmin  # noqa: PLC0415

        site = AdminSite()
        admin_obj = TagModelAdmin(TagModel, site)
        request = _make_mock_request()

        mock_obj = MagicMock(spec=TagModel)
        mock_obj.tag_id = uuid4()
        mock_obj.name = "updated"

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            admin_obj.save_model(request, mock_obj, MagicMock(), True)
            mock_svc.update_tag.assert_called_once()

    def test_delete_model_calls_service(self) -> None:
        """delete_model calls service.delete_tag(tag_id)."""
        from taxomesh.contrib.django.admin import TagModelAdmin  # noqa: PLC0415

        site = AdminSite()
        admin_obj = TagModelAdmin(TagModel, site)
        request = _make_mock_request()

        mock_obj = MagicMock(spec=TagModel)
        mock_obj.tag_id = uuid4()

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            admin_obj.delete_model(request, mock_obj)
            mock_svc.delete_tag.assert_called_once_with(mock_obj.tag_id)

    def test_delete_queryset_calls_service_per_object(self) -> None:
        """delete_queryset calls service.delete_tag once per object."""
        from taxomesh.contrib.django.admin import TagModelAdmin  # noqa: PLC0415

        site = AdminSite()
        admin_obj = TagModelAdmin(TagModel, site)
        request = _make_mock_request()

        obj1 = MagicMock(spec=TagModel)
        obj1.tag_id = uuid4()
        obj2 = MagicMock(spec=TagModel)
        obj2.tag_id = uuid4()

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            admin_obj.delete_queryset(request, [obj1, obj2])
            assert mock_svc.delete_tag.call_count == 2

    def test_error_in_delete_model_surfaced_via_message(self) -> None:
        """TaxomeshError in delete_model surfaces via message_user(ERROR)."""
        from taxomesh.contrib.django.admin import TagModelAdmin  # noqa: PLC0415
        from taxomesh.exceptions import TaxomeshError  # noqa: PLC0415

        site = AdminSite()
        admin_obj = TagModelAdmin(TagModel, site)
        request = _make_mock_request()

        mock_obj = MagicMock(spec=TagModel)
        mock_obj.tag_id = uuid4()

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            mock_svc.delete_tag.side_effect = TaxomeshError("cannot delete")
            with patch.object(admin_obj, "message_user") as mock_msg:
                admin_obj.delete_model(request, mock_obj)
                mock_msg.assert_called_once()


# ---------------------------------------------------------------------------
# T022 — ItemParentLinkInline tests
# ---------------------------------------------------------------------------


class TestItemParentLinkInline:
    """Tests for ItemParentLinkInline service routing."""

    def test_save_model_calls_place_item_in_category(self) -> None:
        """Inline save_model calls service.place_item_in_category with correct args."""
        from taxomesh.contrib.django.admin import ItemParentLinkInline  # noqa: PLC0415

        site = AdminSite()
        inline = ItemParentLinkInline(ItemModel, site)
        request = _make_mock_request()

        obj = MagicMock(spec=ItemParentLinkModel)
        obj.item_id = uuid4()
        obj.category_id = uuid4()
        obj.sort_index = 1

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            inline.save_model(request, obj, MagicMock(), False)
            mock_svc.place_item_in_category.assert_called_once_with(obj.item_id, obj.category_id, obj.sort_index)

    def test_delete_model_calls_remove_item_from_category(self) -> None:
        """Inline delete_model calls service.remove_item_from_category."""
        from taxomesh.contrib.django.admin import ItemParentLinkInline  # noqa: PLC0415

        site = AdminSite()
        inline = ItemParentLinkInline(ItemModel, site)
        request = _make_mock_request()

        obj = MagicMock(spec=ItemParentLinkModel)
        obj.item_id = uuid4()
        obj.category_id = uuid4()

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            inline.delete_model(request, obj)
            mock_svc.remove_item_from_category.assert_called_once_with(obj.item_id, obj.category_id)


# ---------------------------------------------------------------------------
# T023 — ItemTagLinkInline tests
# ---------------------------------------------------------------------------


class TestItemTagLinkInline:
    """Tests for ItemTagLinkInline service routing."""

    def test_save_model_calls_assign_tag(self) -> None:
        """Inline save_model calls service.assign_tag with correct args."""
        from taxomesh.contrib.django.admin import ItemTagLinkInline  # noqa: PLC0415

        site = AdminSite()
        inline = ItemTagLinkInline(ItemModel, site)
        request = _make_mock_request()

        obj = MagicMock(spec=ItemTagLinkModel)
        obj.tag_id = uuid4()
        obj.item_id = uuid4()

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            inline.save_model(request, obj, MagicMock(), False)
            mock_svc.assign_tag.assert_called_once_with(obj.tag_id, obj.item_id)

    def test_delete_model_calls_remove_tag(self) -> None:
        """Inline delete_model calls service.remove_tag."""
        from taxomesh.contrib.django.admin import ItemTagLinkInline  # noqa: PLC0415

        site = AdminSite()
        inline = ItemTagLinkInline(ItemModel, site)
        request = _make_mock_request()

        obj = MagicMock(spec=ItemTagLinkModel)
        obj.tag_id = uuid4()
        obj.item_id = uuid4()

        with patch(_PATCH_TARGET) as MockSvc:
            mock_svc = MagicMock()
            MockSvc.return_value = mock_svc
            inline.delete_model(request, obj)
            mock_svc.remove_tag.assert_called_once_with(obj.tag_id, obj.item_id)


# ---------------------------------------------------------------------------
# T024 — CategoryParentLinkForm.clean() cycle and self-reference validation
# ---------------------------------------------------------------------------

_PATCH_REPO = "taxomesh.contrib.django.admin.DjangoRepository"


def _make_form_cleaned_data(category_id: object, parent_category_id: object) -> tuple[object, dict[str, object]]:
    """Return (form, cleaned_data) with mock CategoryModel FKs pre-set."""
    from taxomesh.contrib.django.admin import CategoryParentLinkForm  # noqa: PLC0415

    form = CategoryParentLinkForm.__new__(CategoryParentLinkForm)

    cat = MagicMock(spec=CategoryModel)
    cat.category_id = category_id
    parent = MagicMock(spec=CategoryModel)
    parent.category_id = parent_category_id

    form.cleaned_data = {"category": cat, "parent_category": parent, "sort_index": 0}
    return form, form.cleaned_data


class TestCategoryParentLinkForm:
    """Tests for CategoryParentLinkForm.clean() — self-reference and cycle detection."""

    def test_inline_uses_category_parent_link_form(self) -> None:
        """CategoryParentLinkInline.form must be CategoryParentLinkForm."""
        from taxomesh.contrib.django.admin import (  # noqa: PLC0415
            CategoryParentLinkForm,
            CategoryParentLinkInline,
        )

        site = AdminSite()
        inline = CategoryParentLinkInline(CategoryModel, site)
        assert inline.form is CategoryParentLinkForm

    def test_clean_self_reference_raises_validation_error(self) -> None:
        """clean() raises ValidationError when category and parent_category are the same."""
        from django.core.exceptions import ValidationError  # noqa: PLC0415

        same_id = uuid4()
        form, _ = _make_form_cleaned_data(same_id, same_id)

        with patch(_PATCH_REPO) as MockRepo:
            MockRepo.return_value.list_category_parent_links.return_value = []
            with pytest.raises(ValidationError, match="cannot be its own parent"):
                form.clean()

    def test_clean_cycle_raises_validation_error(self) -> None:
        """clean() raises ValidationError when the proposed link would create a cycle."""
        from django.core.exceptions import ValidationError  # noqa: PLC0415

        from taxomesh.domain.models import CategoryParentLink  # noqa: PLC0415

        cat_a = uuid4()
        cat_b = uuid4()
        # A → B already exists; attempting to add B → A would create a cycle
        existing = [CategoryParentLink(category_id=cat_a, parent_category_id=cat_b, sort_index=0)]

        form, _ = _make_form_cleaned_data(cat_b, cat_a)

        with patch(_PATCH_REPO) as MockRepo:
            MockRepo.return_value.list_category_parent_links.return_value = existing
            with pytest.raises(ValidationError):
                form.clean()

    def test_clean_valid_link_passes(self) -> None:
        """clean() returns cleaned_data without raising when the link is valid."""
        cat_a = uuid4()
        cat_b = uuid4()
        form, expected = _make_form_cleaned_data(cat_a, cat_b)

        with patch(_PATCH_REPO) as MockRepo:
            MockRepo.return_value.list_category_parent_links.return_value = []
            result = form.clean()

        assert result is expected
