"""Admin registration smoke tests for taxomesh Django models."""

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.contrib import admin  # noqa: E402

from taxomesh.contrib.django.models import (  # noqa: E402
    CategoryModel,
    ItemModel,
    TagModel,
)

pytestmark = pytest.mark.django_db


def test_core_models_registered_in_admin() -> None:
    registered = set(admin.site._registry.keys())
    expected = {CategoryModel, ItemModel, TagModel}
    missing = expected - registered
    assert not missing, f"Models not registered in admin: {missing}"
