"""Base model class for all taxomesh domain entities."""

from pydantic import BaseModel, ConfigDict


def _build_str_repr(emoji: str, name: str, id_value: object, slug: str, external_id: str) -> str:
    """Build the standard human-readable string representation for a domain model.

    Args:
        emoji: Leading emoji prefix (e.g. '📂' for Category, '🏷️' for Item).
        name: Human-readable display name.
        id_value: Internal UUID identifier.
        slug: URL-friendly slug; omitted from output when empty.
        external_id: External system identifier; omitted from output when empty.

    Returns:
        Formatted string: ``<emoji> <name> (slug: … - id: … - ext_id: …)``
        with slug and ext_id segments included only when non-empty.
    """
    parts = []
    if slug:
        parts.append(f"slug: {slug}")
    parts.append(f"id: {id_value}")
    if external_id:
        parts.append(f"ext_id: {external_id}")
    return f"{emoji} {name} ({' - '.join(parts)})"


class ModelBase(BaseModel):
    """Shared base for all taxomesh Pydantic models."""

    model_config = ConfigDict(populate_by_name=True, validate_assignment=True)
