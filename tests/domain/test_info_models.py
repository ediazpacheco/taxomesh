"""The typed introspection read models.

On the **repository** side the repositories differ in what they report: JSON and YAML a path,
Django a database alias, the in-memory test backend nothing. :class:`RepositoryInfo` splits that
into the part every backend can answer (which class, and its path if it has one) and the part
only some can (everything else), typed ``Mapping[str, str | int | None]``.

On the **service** side, :class:`TaxomeshInfo` names each field it reports, and embeds the
repository's model rather than flattening it into a free-form dict. No ``Any`` appears anywhere in
the introspection path.

Three design points these tests pin, because none is obvious from the class bodies:

* **Frozen and slotted, not Pydantic.** Read models are immutable *and* slotted, and Pydantic
  gives no slots. Pydantic is for domain *entities*, and these are read models, not entities,
  so stdlib dataclasses are correct.
* **Two types, not one.** One type is not reused for both layers: a service reports a
  version and corpus sizes, a backend reports a file path or a database connection. Those are
  unlike things and one class describing both would nest itself.
* **The service's model embeds the repository's.** ``TaxomeshInfo.repository`` is a
  ``RepositoryInfo``, so the boundary survives into the result instead of being flattened.
"""

import dataclasses
from collections.abc import Mapping
from typing import get_type_hints

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.info import RepositoryInfo, TaxomeshInfo

# Cross-package import: pytest fixture visibility is per-directory and ``tests/domain/`` has no
# ``conftest.py``, so the fourth port implementation is imported rather than injected. The same
# pattern as ``tests/adapters/repositories/test_repository_contract.py`` and ``tests/surface/test_api_law.py``.
from tests.service.conftest import InMemoryRepository


def _sample() -> RepositoryInfo:
    """A populated instance — the Django shape, the only one with a non-empty diagnostics map."""
    return RepositoryInfo(backend="DjangoRepository", path=None, diagnostics={"database_alias": "default"})


class TestItIsAReadModel:
    """Immutable and slotted, as every read model is."""

    def test_a_field_cannot_be_reassigned(self) -> None:
        """Frozen. A read model that a caller can edit invites edits that persist nowhere.

        The whole value of returning a model rather than the live repository is that the
        caller holds a snapshot. Silently accepting a write would make it look otherwise.
        """
        info = _sample()

        with pytest.raises(dataclasses.FrozenInstanceError):
            info.backend = "JsonRepository"  # type: ignore[misc]

    def test_it_is_slotted(self) -> None:
        """Slotted, so a typo cannot become a new attribute.

        ``slots=True`` is what Pydantic cannot supply, and it is the reason this is a stdlib
        dataclass rather than a model.

        Asserted structurally — the slots tuple and the absent ``__dict__`` — rather than by
        provoking a misspelled write. The absent ``__dict__`` *is* the guarantee: there is
        nowhere for an unexpected attribute to go. Pinning the exception type instead would
        pin a CPython quirk, because ``frozen=True, slots=True`` recreates the class and the
        generated ``__setattr__`` closes over the pre-slots one, so a misspelled name raises
        ``TypeError`` while a real field raises ``FrozenInstanceError``.
        """
        info = _sample()

        assert RepositoryInfo.__slots__ == ("backend", "path", "diagnostics")
        assert not hasattr(info, "__dict__")


class TestItsFields:
    """The split between what every repository answers and what only some do."""

    def test_it_declares_exactly_the_three_fields(self) -> None:
        """Three fields, in this order — the ledger and every repository agree on it."""
        assert [f.name for f in dataclasses.fields(RepositoryInfo)] == ["backend", "path", "diagnostics"]

    def test_path_is_optional_because_two_backends_have_none(self) -> None:
        """``path`` is ``str | None``, and ``None`` is a real answer, not a missing one.

        Django and the in-memory backend have no file to name. Reporting that as ``None``
        rather than omitting the field is what lets ``svc.info.repository.path`` exist on every
        backend instead of being a field that sometimes exists.
        """
        assert get_type_hints(RepositoryInfo)["path"] == (str | None)
        assert _sample().path is None

    def test_diagnostics_is_narrowed_rather_than_any(self) -> None:
        """The point of the whole exercise: the escape hatch is typed.

        Backend-specific extras still vary, so *some* open container is unavoidable — but
        ``Mapping[str, str | int | None]`` says what may travel in it, and ``Mapping`` rather
        than ``dict`` says the caller must not write to it, so no ``Any`` remains anywhere in the
        introspection path.
        """
        assert get_type_hints(RepositoryInfo)["diagnostics"] == Mapping[str, str | int | None]


class TestItIsNotTheServicesType:
    """The two layers describe different things and must not share one type."""

    def test_the_service_does_not_return_a_repository_info(self) -> None:
        """A ``RepositoryInfo`` never escapes as the service's own introspection result."""
        info = TaxomeshService(repository=InMemoryRepository()).info

        assert type(info) is TaxomeshInfo
        assert not isinstance(info, RepositoryInfo)

    def test_the_repository_model_travels_inside_rather_than_instead(self) -> None:
        """The backend's model is a *field* of the service's, not a substitute for it.

        This is the half the negative assertion above cannot state: keeping the two types
        distinct would be worth nothing if the service simply flattened the repository's back
        into loose keys.
        """
        info = TaxomeshService(repository=InMemoryRepository()).info

        assert isinstance(info.repository, RepositoryInfo)


def _service_sample() -> TaxomeshInfo:
    """A populated instance — the Django shape, which has no working path."""
    return TaxomeshInfo(
        version="1.2.3",
        config_name=None,
        item_corpus_size=None,
        category_corpus_size=3,
        repository=_sample(),
    )


class TestTheServiceModelIsAReadModel:
    """``TaxomeshInfo`` is immutable and slotted for the same reasons."""

    def test_a_field_cannot_be_reassigned(self) -> None:
        """Frozen. The caller holds a snapshot of one moment, not a live view of the service.

        Corpus sizes in particular go stale the instant a create, update or delete invalidates a
        corpus.
        Accepting an assignment would suggest the object tracks the service; it does not.
        """
        info = _service_sample()

        with pytest.raises(dataclasses.FrozenInstanceError):
            info.version = "9.9.9"  # type: ignore[misc]

    def test_it_is_slotted(self) -> None:
        """Slotted, so a typo cannot become a new attribute.

        Asserted structurally, as for :class:`RepositoryInfo` above and for the same reason:
        the absent ``__dict__`` *is* the guarantee, while the exception type a misspelled write
        raises is a CPython detail of ``frozen=True, slots=True``.
        """
        info = _service_sample()

        assert TaxomeshInfo.__slots__ == (
            "version",
            "config_name",
            "item_corpus_size",
            "category_corpus_size",
            "repository",
        )
        assert not hasattr(info, "__dict__")


class TestTheServiceModelsFields:
    """The service's fields, declared rather than merely present."""

    def test_it_declares_exactly_the_five_fields(self) -> None:
        """Five fields, in this order.

        The version, the config name, both corpus sizes, and the embedded repository model. The
        backend's name and its path are that model's ``backend`` and ``path``, and are not
        repeated beside it.
        """
        assert [f.name for f in dataclasses.fields(TaxomeshInfo)] == [
            "version",
            "config_name",
            "item_corpus_size",
            "category_corpus_size",
            "repository",
        ]

    def test_the_embedded_repository_model_is_typed_not_a_dict(self) -> None:
        """``repository`` is a ``RepositoryInfo``, not a dict.

        A dict merging the one key every repository answers with the ones only some do would leave
        a caller unable to tell which was which without knowing the backend.
        """
        assert get_type_hints(TaxomeshInfo)["repository"] is RepositoryInfo

    def test_corpus_sizes_are_optional_because_a_corpus_may_be_unbuilt(self) -> None:
        """``None`` means *not built*, and is a real answer rather than a missing one.

        A corpus is built lazily by the first unfiltered search and held for the lifetime of the
        service's cache, or until the service's next create, update or delete of its entity, so
        "no corpus right now" is a state the service is genuinely in most of the time. It is
        distinct from ``0``, which means a corpus was built and found nothing.
        """
        hints = get_type_hints(TaxomeshInfo)

        assert hints["item_corpus_size"] == (int | None)
        assert hints["category_corpus_size"] == (int | None)
        assert _service_sample().item_corpus_size is None

    def test_config_name_stays_optional(self) -> None:
        """It is absent on a real, ordinary configuration rather than only in an edge case.

        A service built with an explicit repository loaded no ``taxomesh.toml``, so it has no
        config name.
        """
        assert get_type_hints(TaxomeshInfo)["config_name"] == (str | None)
