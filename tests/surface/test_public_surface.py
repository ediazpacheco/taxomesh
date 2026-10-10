"""The ledger of public signatures.

``public_surface.txt`` records every public signature of ``TaxomeshService``,
``TaxomeshRepositoryBase`` and the three collections. This file exists for the changes nobody
meant: a parameter that quietly becomes keyword-only, a return type that widens, a method lost in
a merge, a signature that changes while the name stays put. A change to the surface updates the
ledger **on purpose**, and the diff shows what changed. A difference nobody intended
fails the build and names the member.

Updating the ledger is a deliberate act::

    python -c "import sys; sys.path.insert(0,'.'); \\
        from tests.surface._surface import render_surface; \\
        open('tests/surface/public_surface.txt','w').write(render_surface())"

Run that only when you meant to change the surface, and read the diff before committing it.
"""

import inspect
from pathlib import Path

from taxomesh.adapters.repositories.yaml_repository import YamlRepository
from taxomesh.application.collections.categories import CategoryCollection
from taxomesh.application.collections.items import ItemCollection
from taxomesh.application.collections.tags import TagCollection
from taxomesh.application.service import TaxomeshService
from taxomesh.utils.memoize import MemoizedFunction
from tests.surface._surface import (
    OPAQUE_SIGNATURE,
    SUBJECTS,
    public_names,
    render_member,
    render_signature,
    render_surface,
)

LEDGER = Path(__file__).parent / "public_surface.txt"

# Public members of ``TaxomeshService``. The facade has no public memoized member: the graph's
# cached read is a private flat loader, and the memoized public reads live on the collections.
SERVICE_MEMBERS = 3


class TestPublicSurfaceLedger:
    """The committed surface and the live surface agree."""

    def test_matches_the_committed_ledger(self) -> None:
        """Every public member renders exactly as recorded.

        If this fails, either the change was intended — regenerate the ledger and commit the
        diff — or it was not, in which case the diff is the bug report.
        """
        assert LEDGER.exists(), f"ledger missing: {LEDGER}"

        live = render_surface().splitlines()
        recorded = LEDGER.read_text(encoding="utf-8").splitlines()

        added = sorted(set(live) - set(recorded))
        removed = sorted(set(recorded) - set(live))

        report = ["public surface differs from the committed ledger."]
        if added:
            report.append(f"  in the code but not the ledger ({len(added)}):")
            report.extend(f"    + {line}" for line in added)
        if removed:
            report.append(f"  in the ledger but not the code ({len(removed)}):")
            report.extend(f"    - {line}" for line in removed)

        assert not added and not removed, "\n".join(report)

    def test_rendering_is_deterministic(self) -> None:
        """Two renderings in one process agree.

        Cheap, but it is the property the whole ledger rests on: the update methods carry a
        sentinel default whose ``repr`` embeds a memory address, so an un-normalised rendering
        would differ between runs and the ledger could never match twice.
        """
        assert render_surface() == render_surface()

    def test_no_member_renders_an_opaque_signature(self) -> None:
        """Introspection sees through the memoization wrapper.

        The collections' reads are decorated with ``@memoize``, whose wrapper carries
        ``__wrapped__``, ``__name__`` and ``__doc__`` so that ``inspect.signature`` still reports
        the decorated function's own parameters; ``tests/utils/test_memoize.py`` proves the
        mechanism.

        What is asserted here is the consequence for *this* file: if that ever regressed, the
        ledger would silently degrade to identical ``(*args, **kwargs)`` lines and
        would pin nothing at all, while still passing.
        """
        opaque = [line for line in render_surface().splitlines() if OPAQUE_SIGNATURE in line]

        assert not opaque, f"{len(opaque)} member(s) render an opaque signature:\n  " + "\n  ".join(opaque)

    def test_the_ledger_covers_the_memoized_reads(self) -> None:
        """The surface is populated, and a memoized member renders its real parameters.

        Guards the guard: ``test_no_member_renders_an_opaque_signature`` would also pass on an
        empty surface. The memoized public reads live on the collections, so one of those is
        asserted here beside the service's own entries.
        """
        rendered = render_surface()

        assert rendered.count("TaxomeshService.") == SERVICE_MEMBERS
        assert (
            "TaxomeshService.graph(self, *, root: CategoryRef | None = None, "
            "enabled: bool | None = True, include_items: builtins.bool = True) "
            "-> taxomesh.domain.graph.TaxomeshGraph" in rendered
        )
        assert "CategoryCollection.roots(self, *, enabled: bool | None = True)" in rendered


class TestIntrospectionThroughAService:
    """Every public member of the three collections, reached through a service, is what the ledger records.

    The ledger renders each member from its class. A caller, ``help()`` and an IDE reach it through
    an instance instead, where a memoized member is a bound view of the cache object; that view
    must present the member's own signature and identity, or every one of them reads as the cache
    class. The members are enumerated from the ledger's own subjects rather than named, so a member
    memoized later is covered without editing this test.
    """

    @staticmethod
    def _collections(tmp_path: Path) -> list[tuple[type, object]]:
        service = TaxomeshService(repository=YamlRepository(tmp_path / "surface.yaml"))
        pairs: list[tuple[type, object]] = [
            (CategoryCollection, service.categories),
            (ItemCollection, service.items),
            (TagCollection, service.tags),
        ]
        assert [subject for subject, _ in pairs] == SUBJECTS[2:]
        return pairs

    def test_every_signature_is_the_ledgers_without_self(self, tmp_path: Path) -> None:
        recorded = set(LEDGER.read_text(encoding="utf-8").splitlines())
        differing: list[str] = []
        for subject, collection in self._collections(tmp_path):
            for name in public_names(subject):
                through_instance = f"{subject.__name__}.{name}{render_signature(getattr(collection, name))}"
                from_ledger = render_member(subject, name).replace("(self, ", "(", 1).replace("(self)", "()", 1)
                assert render_member(subject, name) in recorded
                if through_instance != from_ledger:
                    differing.append(f"{through_instance}\n      ledger: {from_ledger}")

        assert not differing, "reached through a service:\n  " + "\n  ".join(differing)

    def test_every_member_carries_its_own_identity(self, tmp_path: Path) -> None:
        for subject, collection in self._collections(tmp_path):
            for name in public_names(subject):
                member = getattr(subject, name)
                bound = getattr(collection, name)
                assert bound.__name__ == member.__name__ == name
                assert bound.__qualname__ == member.__qualname__
                assert inspect.getdoc(bound) == inspect.getdoc(member)
                if isinstance(member, MemoizedFunction):
                    assert bound.__wrapped__.__func__ is member.__wrapped__
                    assert bound.__wrapped__.__self__ is collection


class TestSurfaceEnumeration:
    """The enumerator sees what it claims to see."""

    def test_covers_every_subject(self) -> None:
        """The service, the port and the three collections are all enumerated.

        Widened from "both subjects" when the collections joined ``SUBJECTS``. A new public
        surface that the ledger does not watch is the one thing this file exists to prevent, so
        the set is stated exhaustively rather than as a minimum: adding a sixth subject must
        fail here and be an explicit decision.
        """
        names = {subject.__name__ for subject in SUBJECTS}

        assert names == {
            "TaxomeshService",
            "TaxomeshRepositoryBase",
            "CategoryCollection",
            "ItemCollection",
            "TagCollection",
        }

    def test_excludes_private_members(self) -> None:
        """Nothing underscore-prefixed reaches the ledger."""
        for subject in SUBJECTS:
            assert not [name for name in public_names(subject) if name.startswith("_")]

    def test_no_layer_names_a_lookup_get_category(self) -> None:
        """The nullable and the raising category lookups have names no one can confuse.

        The port's nullable lookup is ``find_category``. The service's raising lookup is
        ``svc.categories[...]`` and its nullable one ``svc.categories.get(...)``, told apart by
        the container law: subscript raises, ``get*`` never does. A ``get_category`` on either
        layer would put one name on two contracts, so its absence from both is asserted.
        """
        port_line = render_member(SUBJECTS[1], "find_category")
        collection_line = render_member(SUBJECTS[2], "get")

        assert port_line.endswith("-> taxomesh.domain.models.category.Category | None")
        assert "get_category" not in public_names(SUBJECTS[0])
        assert "get_category" not in public_names(SUBJECTS[1])
        assert collection_line.endswith("| None")


class TestParameterKindMarkers:
    """Both parameter-kind markers reach the ledger, not only ``*``.

    A parameter's kind is part of its contract twice over. To a caller, a positional-only
    parameter gaining a name is a new way to call it. To the cache, it is a new key: ``memoize``
    builds ``(args, sorted kwargs)``, so ``get(key)`` and ``get(key=...)`` are different entries
    and a primed one is silently missed. Without ``/`` in the rendering, that
    change would leave the ledger byte-identical.
    """

    def test_positional_only_parameters_are_followed_by_a_slash(self) -> None:
        """``/`` closes the positional-only group, exactly where Python's own syntax puts it."""

        def subject(key: int, /, other: int, *, flag: bool) -> None: ...

        assert (
            render_signature(subject) == "(key: builtins.int, /, other: builtins.int, *, flag: builtins.bool) -> None"
        )

    def test_a_signature_that_is_entirely_positional_only_ends_with_the_slash(self) -> None:
        """The group can close at the very end, with nothing after it."""

        def subject(key: int, default: int = 0, /) -> None: ...

        assert render_signature(subject) == "(key: builtins.int, default: builtins.int = 0, /) -> None"

    def test_ordinary_parameters_carry_no_slash(self) -> None:
        """Nothing is emitted for a signature with no positional-only parameter."""

        def subject(key: int, *, flag: bool) -> None: ...

        assert render_signature(subject) == "(key: builtins.int, *, flag: builtins.bool) -> None"
