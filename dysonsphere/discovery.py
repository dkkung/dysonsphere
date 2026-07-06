"""Discovery of optional dysonsphere extension packages (e.g. ``dysonsphere-biology``).

Extensions are separate, independently released distributions - not part of core - that
register themselves under the ``dysonsphere.extensions`` entry-point group in their own
``pyproject.toml``::

    [project.entry-points."dysonsphere.extensions"]
    biology = "dysonsphere_biology"

Core discovers them lazily. Accessing ``dysonsphere.<name>`` (resolved by the package-level
``__getattr__`` in ``dysonsphere/__init__.py``) imports and returns the registered module, so
``dysonsphere.biology.volcano(df)`` works once ``dysonsphere-biology`` is pip-installed. The
extension is also importable directly (``import dysonsphere_biology``); the entry point only
adds the ``dysonsphere.<name>`` alias and lets core enumerate what is installed.

Public surface: ``extensions()`` (list installed names) and ``load_extension(name)`` (import
one by name). Both live here; ``__getattr__`` delegates to ``_extension_entry_points``.
"""

from __future__ import annotations

import importlib.metadata
from types import ModuleType

__all__ = ["extensions", "load_extension"]

# Entry-point group extension distributions register under. Kept as a module constant so the
# package __getattr__ and the tests reference one string.
_ENTRY_POINT_GROUP = "dysonsphere.extensions"


def _extension_entry_points() -> dict[str, importlib.metadata.EntryPoint]:
    """Return installed extension entry points keyed by their registered name."""
    return {ep.name: ep for ep in importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP)}


def extensions() -> list[str]:
    """Return the sorted names of installed dysonsphere extensions.

    Each name is also accessible as an attribute of the top-level ``dysonsphere`` module
    (e.g. ``dysonsphere.biology`` when ``dysonsphere-biology`` is installed).
    """
    return sorted(_extension_entry_points())


def load_extension(name: str) -> ModuleType:
    """Import and return the extension registered under ``name``.

    Equivalent to accessing ``dysonsphere.<name>`` but explicit. Raises ``ImportError`` with
    the list of installed extensions if no extension is registered under ``name``.
    """
    ep = _extension_entry_points().get(name)
    if ep is None:
        available = extensions()
        hint = f"installed extensions: {', '.join(available)}" if available else "no extensions are installed"
        raise ImportError(f"no dysonsphere extension named {name!r} is installed ({hint})")
    return ep.load()
