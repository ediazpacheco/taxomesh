"""The ``AppConfig`` of the taxomesh Django app."""

from django.apps import AppConfig


class TaxomeshContribDjangoConfig(AppConfig):
    """The Django configuration of the ``taxomesh.contrib.django`` app."""

    name = "taxomesh.contrib.django"
    label = "taxomesh_contrib_django"
    verbose_name = "Taxomesh"
