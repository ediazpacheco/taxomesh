"""Minimal URL configuration for the taxomesh Django test suite."""

from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
