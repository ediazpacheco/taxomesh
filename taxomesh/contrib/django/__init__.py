"""The Django app of taxomesh.

It has the ORM models behind ``DjangoRepository`` (``taxomesh.contrib.django.models``), the
admin, and ``get_taxomesh_service_with_django``, which builds a service over the Django ORM.
Importing this package imports no Django: the function imports it when it runs.

To use it in a Django project, add ``"taxomesh.contrib.django"`` to ``INSTALLED_APPS`` and run
``python manage.py migrate``.
"""

from typing import TYPE_CHECKING

from taxomesh.adapters.repositories.django_repository import DEFAULT_DJANGO_USING

if TYPE_CHECKING:
    from taxomesh.application.service import TaxomeshService


def get_taxomesh_service_with_django(
    using: str = DEFAULT_DJANGO_USING,
) -> "TaxomeshService":
    """Return a new ``TaxomeshService`` whose repository is a ``DjangoRepository``.

    ``DjangoRepository`` and ``TaxomeshService`` are imported inside this function, so that
    ``from taxomesh.contrib.django import get_taxomesh_service_with_django`` succeeds when Django is
    not installed.

    Args:
        using: The Django database alias. The default is ``"default"``.

    Returns:
        A service over the Django ORM, on that database.

    Raises:
        TaxomeshRepositoryError: If Django is not installed, or if its settings are not
            configured.
        TypeError: If ``using`` is not a ``str``.
    """
    from taxomesh import TaxomeshService  # noqa: PLC0415
    from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

    return TaxomeshService(repository=DjangoRepository(using=using))
