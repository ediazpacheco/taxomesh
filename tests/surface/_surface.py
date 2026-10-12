"""Render the public API surface as stable, diffable text.

The rendered text is committed as ``public_surface.txt``, the ledger of every public signature of
``TaxomeshService``, ``TaxomeshRepositoryBase`` and the three collections. A change nobody intended
(a parameter quietly becoming keyword-only, a return type widening, a method disappearing in a
merge) fails the build until the ledger is edited on purpose.

Two rendering details matter:

* **Defaults are rendered with their memory address stripped.** ``repr`` renders an object
  default as ``<module.Class object at 0x1077397f0>``. That address changes on every interpreter
  run, so the naive rendering would never match twice. Stripping it keeps the *value* of every
  ordinary default visible.
* **Signatures are read through** ``inspect.signature``, **which uses** ``__wrapped__``.
  The memoized reads of the service and its collections carry ``__wrapped__``, so introspection
  sees the member's own signature. Without it every one of them would render as
  ``(*args, **kwargs)`` and the ledger would pin nothing. ``test_public_surface.py`` asserts that
  it does not happen.
"""

import inspect
import re
from collections.abc import Callable, Iterator

from taxomesh.application.collections.categories import CategoryCollection
from taxomesh.application.collections.items import ItemCollection
from taxomesh.application.collections.tags import TagCollection
from taxomesh.application.service import TaxomeshService
from taxomesh.ports.repository import TaxomeshRepositoryBase

# The types the ledger covers. Order is fixed so the rendering is deterministic, and the three
# collections come after the service and the port, so each block keeps its place and a diff
# stays readable.
SUBJECTS: list[type] = [
    TaxomeshService,
    TaxomeshRepositoryBase,
    CategoryCollection,
    ItemCollection,
    TagCollection,
]

# ``<module.Class object at 0x7f...>`` — the address is the only unstable part.
_OBJECT_ADDRESS = re.compile(r" at 0x[0-9a-fA-F]+")

# What a signature renders as when introspection fails to see through a wrapper.
OPAQUE_SIGNATURE = "(*args, **kwargs)"


def _render_annotation(annotation: object) -> str:
    """Render a type annotation as stable text.

    Classes render as ``module.QualName`` rather than ``<class 'module.QualName'>``; unions and
    generics already render well under ``str``.
    """
    if annotation is inspect.Parameter.empty:
        return ""
    if isinstance(annotation, type):
        return f"{annotation.__module__}.{annotation.__qualname__}"
    return str(annotation)


def _render_default(default: object) -> str:
    """Render a parameter default, with any object memory address removed."""
    return _OBJECT_ADDRESS.sub("", repr(default))


def _render_parameter(parameter: inspect.Parameter) -> str:
    """Render one parameter: name, kind marker, annotation and default."""
    if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
        rendered = f"*{parameter.name}"
    elif parameter.kind is inspect.Parameter.VAR_KEYWORD:
        rendered = f"**{parameter.name}"
    else:
        rendered = parameter.name

    annotation = _render_annotation(parameter.annotation)
    if annotation:
        rendered = f"{rendered}: {annotation}"
    if parameter.default is not inspect.Parameter.empty:
        rendered = f"{rendered} = {_render_default(parameter.default)}"
    return rendered


def render_signature(target: Callable[..., object]) -> str:
    """Render a callable's full signature, both parameter-kind markers included.

    ``/`` closes the positional-only group and ``*`` opens the keyword-only one, where Python's
    own syntax puts them. Both are load-bearing: a positional-only parameter gaining a name is a
    new call shape, and ``memoize`` keys on the call shape.

    A callable hiding behind a wrapper that introspection cannot see through renders as
    ``OPAQUE_SIGNATURE`` — which is itself worth recording, so it is rendered rather than
    raised, and asserted against in ``test_public_surface.py``.
    """
    signature = inspect.signature(target)
    parts: list[str] = []
    in_positional_only = False
    seen_keyword_only = False
    for parameter in signature.parameters.values():
        if in_positional_only and parameter.kind is not inspect.Parameter.POSITIONAL_ONLY:
            parts.append("/")
        in_positional_only = parameter.kind is inspect.Parameter.POSITIONAL_ONLY
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY and not seen_keyword_only:
            parts.append("*")
            seen_keyword_only = True
        parts.append(_render_parameter(parameter))
    if in_positional_only:
        parts.append("/")

    returns = _render_annotation(signature.return_annotation)
    suffix = f" -> {returns}" if returns else ""
    return f"({', '.join(parts)}){suffix}"


def public_names(subject: type) -> list[str]:
    """Return the public member names of a class, sorted."""
    return sorted(name for name in dir(subject) if not name.startswith("_"))


def render_member(subject: type, name: str) -> str:
    """Render one public member as a single line of ledger text."""
    member: object = getattr(subject, name)
    qualified = f"{subject.__name__}.{name}"

    if isinstance(member, property):
        getter = member.fget
        returns = _render_annotation(inspect.signature(getter).return_annotation) if getter is not None else ""
        suffix = f" -> {returns}" if returns else ""
        return f"{qualified}: property{suffix}"

    if callable(member):
        return f"{qualified}{render_signature(member)}"

    return f"{qualified}: {type(member).__module__}.{type(member).__qualname__}"


def render_lines() -> Iterator[str]:
    """Yield one line per public member, across every subject, deterministically."""
    for subject in SUBJECTS:
        for name in public_names(subject):
            yield render_member(subject, name)


def render_surface() -> str:
    """Render the whole public surface as the text committed to ``public_surface.txt``."""
    return "\n".join(render_lines()) + "\n"
