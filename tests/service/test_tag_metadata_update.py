"""Tag metadata is updatable after creation, as a category's and an item's is.

The rule mirrors ``items.update`` rather than inventing one: a metadata dict **replaces** what
was stored, and leaving it out leaves it alone. Two members of the same facade must not
disagree about what passing metadata to an update means.

Every assertion reads the tag back through ``service.tags[...]`` instead of trusting the
returned object, so what is asserted is what was stored.
"""

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import TaxomeshTagNotFoundError


class TestTagMetadata:
    """``service.tags.update`` and its ``metadata`` parameter."""

    def test_update_sets_metadata(self, service: TaxomeshService) -> None:
        """Metadata passed to an update reaches storage."""
        created = service.tags.create("Blue")

        service.tags.update(created.tag_id, metadata={"k": "v"})

        assert service.tags[created.tag_id].metadata == {"k": "v"}

    def test_update_returns_the_updated_tag(self, service: TaxomeshService) -> None:
        """The returned tag already carries the new metadata.

        Not a duplicate of the assertion above: that one reads storage back, this one pins what
        the call hands its caller. Three of the four repositories store the same instance that the
        call returns, so the two questions can only be told apart by asking them separately.
        """
        created = service.tags.create("Blue")

        updated = service.tags.update(created.tag_id, name="Green", metadata={"k": "v"})

        assert (updated.name, updated.metadata) == ("Green", {"k": "v"})

    def test_update_replaces_metadata_wholesale(self, service: TaxomeshService) -> None:
        """A new dict replaces the stored one rather than merging into it.

        The same rule as ``items.update``. Merging would make removing a key impossible.
        """
        created = service.tags.create("Blue", metadata={"old": "value"})

        service.tags.update(created.tag_id, metadata={"new": "value"})

        assert service.tags[created.tag_id].metadata == {"new": "value"}

    def test_metadata_left_out_is_left_alone(self, service: TaxomeshService) -> None:
        """Renaming a tag does not clear its metadata."""
        created = service.tags.create("Blue", metadata={"k": "v"})

        service.tags.update(created.tag_id, name="Green")

        stored = service.tags[created.tag_id]
        assert (stored.name, stored.metadata) == ("Green", {"k": "v"})

    def test_name_and_metadata_update_together(self, service: TaxomeshService) -> None:
        """Both fields can change in one call."""
        created = service.tags.create("Blue", metadata={"old": "value"})

        service.tags.update(created.tag_id, name="Green", metadata={"new": "value"})

        stored = service.tags[created.tag_id]
        assert (stored.name, stored.metadata) == ("Green", {"new": "value"})

    def test_updating_an_unknown_tag_raises(self, service: TaxomeshService) -> None:
        """A metadata-only update on a tag that is not stored still raises rather than creating one."""
        created = service.tags.create("Blue")
        service.tags.delete(created.tag_id)

        with pytest.raises(TaxomeshTagNotFoundError):
            service.tags.update(created.tag_id, metadata={"k": "v"})
