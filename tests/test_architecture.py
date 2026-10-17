"""The dependency direction the package's layers keep, and how its interfaces are named.

The application layer orchestrates the domain through the repository port and knows no concrete
adapter and no integration. Resolving a repository from ``taxomesh.toml`` lives outside it, in
``taxomesh._config``, which the service reaches only when it is given no repository. The domain
imports neither the application nor anything outside it. Every public abstract interface, a
``Protocol`` or an ``ABC``, is named with the ``Base`` suffix, as the port ``TaxomeshRepositoryBase``
is.
"""

import ast
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Final

PACKAGE: Final[Path] = Path(__file__).resolve().parent.parent / "taxomesh"
# The adapters and the integrations, and ``taxomesh.repositories``, which re-exports the adapters.
OUTER_LAYERS: Final[tuple[str, ...]] = ("taxomesh.adapters", "taxomesh.contrib", "taxomesh.repositories")


def _package_of(path: Path) -> str:
    """Return the dotted name of the package that holds the module at *path*."""
    parts = path.relative_to(PACKAGE.parent).with_suffix("").parts
    return ".".join(parts[:-1])


def _imported_modules(path: Path) -> Iterator[tuple[int, str]]:
    """Yield the line and the absolute name of every module this file imports, at any depth.

    An import inside a function body counts as much as one at the top: a lazy import is still a
    dependency, only a deferred one. A relative import is resolved against the file's package, and
    ``from package import name`` also yields ``package.name``, since the name may be a module.
    """
    package = _package_of(path)
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            base = package.rsplit(".", node.level - 1)[0] if node.level else ""
            module = ".".join(part for part in (base, node.module) if part)
            yield node.lineno, module
            for alias in node.names:
                yield node.lineno, f"{module}.{alias.name}"


def _reaching_out(layer: str, outward: tuple[str, ...]) -> list[str]:
    """Return one ``path:line imports module`` entry for each import under *layer* of a module in *outward*."""
    return [
        f"{path.relative_to(PACKAGE.parent)}:{line} imports {module}"
        for path in sorted((PACKAGE / layer).rglob("*.py"))
        for line, module in _imported_modules(path)
        if any(module == name or module.startswith(f"{name}.") for name in outward)
    ]


def test_the_application_layer_imports_no_adapter_and_no_integration() -> None:
    reaching_out = _reaching_out("application", OUTER_LAYERS)

    assert not reaching_out, "\n".join(reaching_out)


def test_the_domain_imports_no_layer_outside_it() -> None:
    reaching_out = _reaching_out("domain", ("taxomesh.application", "taxomesh._config", *OUTER_LAYERS))

    assert not reaching_out, "\n".join(reaching_out)


def test_a_service_given_a_repository_never_resolves_one(tmp_path: Path) -> None:
    """The configuration module is imported only on the path that needs it."""
    probe = (
        "import sys\n"
        "from pathlib import Path\n"
        "from taxomesh import TaxomeshService\n"
        "from taxomesh.adapters.repositories.json_repository import JsonRepository\n"
        f"TaxomeshService(repository=JsonRepository(Path({str(tmp_path / 'store.json')!r})))\n"
        "print('taxomesh._config' in sys.modules)\n"
    )

    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)

    assert result.stdout.strip() == "False"


INTERFACE_BASES: Final[frozenset[str]] = frozenset({"Protocol", "ABC"})


def _base_name(node: ast.expr) -> str | None:
    """The name a class base is spelled with: ``Protocol``, ``typing.Protocol`` or ``Protocol[T]``."""
    if isinstance(node, ast.Subscript):
        return _base_name(node.value)
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def test_every_public_interface_ends_in_base() -> None:
    """A public ``Protocol`` or ``ABC`` defined in the package is named ``…Base``."""
    misnamed = [
        f"{path.relative_to(PACKAGE.parent)}:{node.lineno} {node.name}"
        for path in sorted(PACKAGE.rglob("*.py"))
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ClassDef)
        and not node.name.startswith("_")
        and any(_base_name(base) in INTERFACE_BASES for base in node.bases)
        and not node.name.endswith("Base")
    ]

    assert not misnamed, "\n".join(misnamed)
