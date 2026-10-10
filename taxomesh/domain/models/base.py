"""The base class of every taxomesh model, and the ``str()`` of a row."""

from pydantic import BaseModel, ConfigDict


def _build_str_repr(name: str, id_value: object, slug: str = "", external_id: str | None = None) -> str:
    """Build a row's ``str()``: a plain-text label naming it and the keys it is found by.

    Args:
        name: The row's name.
        id_value: The row's identifier.
        slug: The row's slug; left out when empty, which is no slug.
        external_id: The row's external id; left out when ``None``.

    Returns:
        ``<name> (slug: …, id: …, external_id: …)``, with the slug and the external id only when
        the row has one, such as ``Music (slug: music, id: …)``.
    """
    parts = []
    if slug:
        parts.append(f"slug: {slug}")
    parts.append(f"id: {id_value}")
    if external_id is not None:
        parts.append(f"external_id: {external_id}")
    return f"{name} ({', '.join(parts)})"


class ModelBase(BaseModel):
    """The base class of every taxomesh Pydantic model: the rows and the links.

    The models are frozen. A row never changes in place, and an assignment to a field raises
    pydantic's ``ValidationError``, which is a ``ValueError``. A changed row is a new object, built
    by ``model_copy(update=…)`` or validated again.
    """

    model_config = ConfigDict(populate_by_name=True, frozen=True)
