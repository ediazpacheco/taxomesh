"""AppConfig for the taxomesh Django contrib app."""

from django.apps import AppConfig


class TaxomeshContribDjangoConfig(AppConfig):
    """Django application configuration for the taxomesh contrib package."""

    name = "taxomesh.contrib.django"
    label = "taxomesh_contrib_django"
    verbose_name = "Taxomesh"
