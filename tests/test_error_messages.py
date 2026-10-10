"""Every error message the library writes has one style.

A message starts with a capital letter, as ``Category not found: …`` does, unless it opens with the
name of the parameter or field it is about, as ``limit must be an int, not str`` does, or with a
value it names. It ends without a period, as Python's own messages do. Each call of an exception
class under ``taxomesh/`` whose message is written out, as text or an f-string, is read, whether it
is raised there or returned to be raised. A ``_require_*`` helper's message opens with the name it
is given, so each call that gives it as text is read for that opening. Django's form errors keep
Django's style of whole sentences, so ``forms.ValidationError`` is left out.
"""

import ast
import inspect
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest
from pydantic import BaseModel

from taxomesh.adapters.repositories.django_repository import DjangoRepository
from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YamlRepository
from taxomesh.application.collections.categories import CategoryCollection
from taxomesh.application.collections.items import ItemCollection
from taxomesh.application.collections.tags import TagCollection
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.graph import CategoryNode, TaxomeshGraph
from taxomesh.domain.models import (
    Category,
    CategoryParentLink,
    Item,
    ItemParentLink,
    ItemRelationLink,
    ItemTagLink,
    Tag,
)
from taxomesh.ports.repository import TaxomeshRepositoryBase

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent

# The classes whose public signatures name the parameters a message may open with.
SIGNED: Final[list[type]] = [
    TaxomeshService,
    TaxomeshRepositoryBase,
    CategoryCollection,
    ItemCollection,
    TagCollection,
    TaxomeshGraph,
    CategoryNode,
    JsonRepository,
    YamlRepository,
    DjangoRepository,
]

ROWS: Final[list[type[BaseModel]]] = [
    Category,
    Item,
    Tag,
    CategoryParentLink,
    ItemParentLink,
    ItemRelationLink,
    ItemTagLink,
]

_FIRST_WORD: Final[re.Pattern[str]] = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _parameters(cls: type) -> Iterator[str]:
    """Yield the parameter names of every public member of *cls*, its constructor included."""
    for name, member in inspect.getmembers(cls, callable):
        if name.startswith("_") and name != "__init__":
            continue
        try:
            parameters = inspect.signature(member).parameters
        except (TypeError, ValueError):
            continue
        yield from (parameter for parameter in parameters if parameter != "self")


NAMES: Final[frozenset[str]] = frozenset(
    [name for cls in SIGNED for name in _parameters(cls)] + [field for row in ROWS for field in row.model_fields]
)


def _text(node: ast.expr) -> list[str | None] | None:
    """Return the message as its pieces, ``None`` standing for each placeholder, or ``None``."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.JoinedStr):
        return [
            part.value if isinstance(part, ast.Constant) and isinstance(part.value, str) else None
            for part in node.values
        ]
    return None


def _is_error_class(func: ast.expr) -> bool:
    """True for a call of a class named ``…Error``, Django's form error aside."""
    if isinstance(func, ast.Name):
        return func.id.endswith("Error")
    if isinstance(func, ast.Attribute):
        return func.attr.endswith("Error") and not (isinstance(func.value, ast.Name) and func.value.id == "forms")
    return False


def style_problem(pieces: list[str | None]) -> str | None:
    """Return what breaks the style in a message given as its pieces, or ``None``."""
    first, last = pieces[0], pieces[-1]
    if first is not None and first:
        word = _FIRST_WORD.match(first)
        if not first[0].isupper() and (word is None or word.group() not in NAMES):
            return "starts with neither a capital letter nor a parameter or field name"
    if last is not None and last.endswith("."):
        return "ends with a period"
    return None


def _is_require_helper(func: ast.expr) -> bool:
    """True for a call of a ``_require_*`` helper, whose message opens with its first argument."""
    return isinstance(func, ast.Name) and func.id.startswith("_require_")


def _messages() -> Iterator[tuple[str, list[str | None]]]:
    """Yield ``path:line`` and the pieces of each written-out message under ``taxomesh/``.

    A ``_require_*`` call given its name as text yields that name and a placeholder for the rest,
    which is the helper's own message.
    """
    for path in sorted((REPO_ROOT / "taxomesh").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            first = node.args[0]
            pieces = None
            if _is_error_class(node.func):
                pieces = _text(first)
            elif _is_require_helper(node.func) and isinstance(first, ast.Constant) and isinstance(first.value, str):
                pieces = [first.value, None]
            if pieces is not None:
                yield f"{path.relative_to(REPO_ROOT)}:{node.lineno}", pieces


SAMPLES: Final[dict[str, tuple[list[str | None], bool]]] = {
    "capitalised": (["Category not found: ", None], True),
    "opened by a parameter": (["limit must be ≥ 1, got ", None], True),
    "opened by a field": (["relation_type must not be empty"], True),
    "opened by a value": ([None, " changed since this repository read it"], True),
    "a helper given a parameter": (["relation_types", None], True),
    "a helper given prose": (["a relation type", None], False),
    "lower-case prose": (["could not write ", None], False),
    "a final period": (["Slug ", None, " is already in use."], False),
}


@pytest.mark.parametrize("name", SAMPLES)
def test_the_rule_on_its_samples(name: str) -> None:
    pieces, conforms = SAMPLES[name]
    assert (style_problem(pieces) is None) is conforms


def test_the_walk_reads_the_library_messages() -> None:
    """The walk reaches messages raised and returned alike, so a passing gate is not an empty one."""
    found = list(_messages())
    assert len(found) > 60
    assert any("_version.py" in where for where, _ in found)
    assert {"slug", "query", "relation_types"} <= {pieces[0] for _, pieces in found if pieces[1:] == [None]}
    assert {"limit", "relation_type", "external_id", "path", "cache_ttl"} <= NAMES


def test_every_message_has_the_style() -> None:
    offences = [
        f"{where}: {problem}: {''.join(piece or '{}' for piece in pieces)!r}"
        for where, pieces in _messages()
        if (problem := style_problem(pieces)) is not None
    ]
    assert not offences, f"{len(offences)} messages break the style:\n" + "\n".join(offences)
