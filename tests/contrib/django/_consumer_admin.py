"""A site's own admin with ``ItemCategoryAssignmentMixin``, and the URLs that serve it, for Django's test client.

Django's ``Group`` stands for a model of the site: the primary key of a group is the external id of
its item. Two admin sites register it. ``/admin/`` uses the mixin as its docstring shows it, with no
``fields``. ``/fields-admin/`` declares ``fields`` that do not name ``categories``.
"""

from typing import TYPE_CHECKING

from django.contrib.admin import AdminSite, ModelAdmin
from django.contrib.auth.models import Group
from django.urls import path

from taxomesh.contrib.django.admin import ItemCategoryAssignmentMixin

# Django cannot subscript ``ModelAdmin`` at run time; the type checker reads it with its model.
if TYPE_CHECKING:
    _GroupAdminBase = ModelAdmin[Group]
else:
    _GroupAdminBase = ModelAdmin


class GroupAdmin(ItemCategoryAssignmentMixin, _GroupAdminBase):
    """The admin of a site's model as the mixin's docstring writes it: it declares no ``fields``."""


class GroupAdminWithFields(ItemCategoryAssignmentMixin, _GroupAdminBase):
    """The admin of a site's model whose ``fields`` leave out ``categories``."""

    fields = ("name",)


site = AdminSite(name="admin")
site.register(Group, GroupAdmin)
fields_site = AdminSite(name="fields_admin")
fields_site.register(Group, GroupAdminWithFields)

urlpatterns = [
    path("admin/", site.urls),
    path("fields-admin/", fields_site.urls),
]
