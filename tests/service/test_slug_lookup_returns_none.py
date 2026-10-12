"""``get_by_slug`` answers ``None`` on a miss, on both collections.

Six cases, on all four backends: an unknown slug and the empty slug answer ``None`` on
categories and on items, and a known slug returns its row on both.

The empty slug is no slug, and both collections answer it with ``None`` before reading storage.
On categories that is what keeps the root out: the implicit root is a real stored row — created as
``Category(name=ROOT_CATEGORY_NAME)``, and ``slug`` defaults to ``""`` — so
``find_category_by_slug("")`` *finds* it on every backend. On items there is nothing to find.
Both facts are pinned below rather than asserted in prose.

A miss is cached like any other answer: ``memoize`` tells a stored ``None`` from an absent entry
through ``Miss``, so the second lookup of a slug that does not exist is served from memory
instead of returning to storage, and the next write clears it with everything else. The cached
read is ``_by_slug``, behind ``get_by_slug``.
"""

from taxomesh.application.service import TaxomeshService
from taxomesh.utils.memoize import Miss


class TestCategorySlugLookup:
    """``svc.categories.get_by_slug`` — the row, or ``None``."""

    def test_a_known_slug_returns_its_row(self, service: TaxomeshService) -> None:
        created = service.categories.create("Books", slug="books")

        assert service.categories.get_by_slug("books") == created

    def test_an_unknown_slug_returns_none(self, service: TaxomeshService) -> None:
        assert service.categories.get_by_slug("no-such-slug") is None

    def test_the_empty_slug_returns_none(self, service: TaxomeshService) -> None:
        assert service.categories.get_by_slug("") is None


class TestItemSlugLookup:
    """``svc.items.get_by_slug`` — the row, or ``None``."""

    def test_a_known_slug_returns_its_row(self, service: TaxomeshService) -> None:
        created = service.items.create(name="Widget", slug="widget")

        assert service.items.get_by_slug("widget") == created

    def test_an_unknown_slug_returns_none(self, service: TaxomeshService) -> None:
        assert service.items.get_by_slug("no-such-slug") is None

    def test_the_empty_slug_returns_none(self, service: TaxomeshService) -> None:
        assert service.items.get_by_slug("") is None


class TestWhyTheEmptySlugIsNoSlug:
    """Equal answers, and what each would be without the shortcut — stated as assertions."""

    def test_the_root_is_found_by_the_port_and_excluded_by_the_collection(self, service: TaxomeshService) -> None:
        """The root does carry the empty slug, so reading it would return the root."""
        assert service.repository.find_category_by_slug("") is not None
        assert service.categories.get_by_slug("") is None

    def test_no_item_carries_the_empty_slug_at_all(self, service: TaxomeshService) -> None:
        """Nothing was created, so a read would find nothing either."""
        assert service.repository.find_item_by_slug("") is None
        assert service.items.get_by_slug("") is None


class TestTheMissIsCached:
    """A ``None`` is a cached answer, not an absent entry."""

    def test_a_missing_slug_is_cached_rather_than_read_again(self, service: TaxomeshService) -> None:
        """``Miss`` is what keeps the two apart; without it the negative would never cache."""
        assert service.categories.get_by_slug("no-such-slug") is None

        assert not isinstance(service.categories._by_slug.cached("no-such-slug"), Miss)
