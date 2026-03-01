"""taxomesh Django integration app.

Provides:
- Django ORM models for taxomesh domain objects (via ``taxomesh.contrib.django.models``)
- ``get_taxomesh_service_with_django`` convenience factory (deferred imports — Django not required
  at import time)

To use in a Django project, add ``"taxomesh.contrib.django"`` to ``INSTALLED_APPS`` and run
``python manage.py migrate``.
"""

from typing import Any

default_app_config = "taxomesh.contrib.django.apps.TaxomeshContribDjangoConfig"


def get_taxomesh_service_with_django(
    using: str | None = None,
) -> Any:
    """Return a TaxomeshService backed by DjangoRepository.

    Both ``DjangoRepository`` and ``TaxomeshService`` are imported inside this
    function body so that ``from taxomesh.contrib.django import
    get_taxomesh_service_with_django`` succeeds even when Django is not installed.

    Args:
        using: Django database alias. Defaults to ``DJANGO_REPO_USING_DEFAULT``
            (``"default"``) when ``None``.

    Returns:
        A fully configured ``TaxomeshService`` instance using the Django ORM backend.

    Raises:
        TaxomeshRepositoryError: If Django is not installed.
    """
    from taxomesh import TaxomeshService  # noqa: PLC0415
    from taxomesh.adapters.repositories.django_repository import (  # noqa: PLC0415
        _USING_DEFAULT,
        DjangoRepository,
    )

    resolved_using: str = using if using is not None else _USING_DEFAULT
    return TaxomeshService(repository=DjangoRepository(using=resolved_using))
