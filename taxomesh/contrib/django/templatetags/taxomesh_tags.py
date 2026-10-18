"""The template tags and filters of the taxomesh admin templates."""

from pathlib import Path

from django import template
from django.conf import settings

import taxomesh

register = template.Library()


@register.filter
def get_item(mapping: object, key: object) -> object:
    """Return ``mapping[key]`` when ``mapping`` is a dict and has the key, and ``None`` otherwise.

    In a template: ``{{ my_dict|get_item:some_key }}``.
    """
    if isinstance(mapping, dict):
        return mapping.get(key)
    return None


@register.simple_tag
def taxomesh_version_info() -> dict[str, str]:
    """Return the version of taxomesh and a description of its backend, for the admin pages.

    Returns:
        A dict with the keys ``version`` and ``backend``. ``version`` is ``taxomesh.__version__``,
        the version of the installed taxomesh package. ``backend`` is the path of ``taxomesh.toml``
        in ``settings.BASE_DIR`` when that file exists, and ``"Django ORM backend"`` otherwise.
    """
    backend = "Django ORM backend"
    base_dir = getattr(settings, "BASE_DIR", None)
    if base_dir is not None:
        toml_path = Path(str(base_dir)) / "taxomesh.toml"
        if toml_path.exists():
            backend = str(toml_path)

    return {"version": taxomesh.__version__, "backend": backend}
