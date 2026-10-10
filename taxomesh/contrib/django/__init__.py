"""The Django app of taxomesh.

It has the ORM models behind ``DjangoRepository`` (``taxomesh.contrib.django.models``), the
admin, and ``get_taxomesh_service_with_django``, which builds a service over the Django ORM.
Importing this package imports no Django: the function imports it when it runs.

To use it in a Django project, add ``"taxomesh.contrib.django"`` to ``INSTALLED_APPS`` and run
``python manage.py migrate``.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from taxomesh.application.service import TaxomeshService

default_app_config = "taxomesh.contrib.django.apps.TaxomeshContribDjangoConfig"


def get_taxomesh_service_with_django(
    using: str | None = None,
) -> "TaxomeshService":
    """Return a new ``TaxomeshService`` whose repository is a ``DjangoRepository``.

    ``DjangoRepository`` and ``TaxomeshService`` are imported inside this function, so that
    ``from taxomesh.contrib.django import get_taxomesh_service_with_django`` succeeds when Django is
    not installed.

    Args:
        using: The Django database alias. When ``None``, the alias ``"default"``.

    Returns:
        A service over the Django ORM, on that database.

    Raises:
        TaxomeshRepositoryError: If Django is not installed, or if its settings are not
            configured.
    """
    from taxomesh import TaxomeshService  # noqa: PLC0415
    from taxomesh.adapters.repositories.django_repository import (  # noqa: PLC0415
        _USING_DEFAULT,
        DjangoRepository,
    )

    resolved_using: str = using if using is not None else _USING_DEFAULT
    return TaxomeshService(repository=DjangoRepository(using=resolved_using))
