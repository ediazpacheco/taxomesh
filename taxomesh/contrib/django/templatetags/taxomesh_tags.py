"""Custom template tags and filters for taxomesh admin templates."""

import importlib.metadata
from pathlib import Path

from django import template
from django.conf import settings

register = template.Library()


@register.filter
def get_item(mapping: object, key: object) -> object:
    """Return mapping[key] if mapping is a dict, else None.

    Usage in templates: ``{{ my_dict|get_item:some_key }}``
    """
    if isinstance(mapping, dict):
        return mapping.get(key)  # type: ignore[arg-type]
    return None


@register.simple_tag
def taxomesh_version_info() -> dict[str, str]:
    """Return a dict with taxomesh version and active backend info.

    Returns:
        A dict with keys ``version`` and ``backend``.
        ``version`` is the installed taxomesh package version, or ``"unknown"`` on lookup failure.
        ``backend`` is the path to taxomesh.toml in ``settings.BASE_DIR`` if it exists,
        else ``"Django ORM backend"``.
    """
    try:
        version = importlib.metadata.version("taxomesh")
    except importlib.metadata.PackageNotFoundError:
        version = "unknown"

    backend = "Django ORM backend"
    base_dir = getattr(settings, "BASE_DIR", None)
    if base_dir is not None:
        toml_path = Path(str(base_dir)) / "taxomesh.toml"
        if toml_path.exists():
            backend = str(toml_path)

    return {"version": version, "backend": backend}
