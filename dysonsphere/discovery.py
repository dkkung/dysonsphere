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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .export import _AltairChart

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


# ── Extension-usage provenance ──────────────────────────────────────────────────────────────
# An extension tags each chart it builds with a durable view-``name`` marker so ``save()`` can
# record which extensions actually PRODUCED a figure (not merely which are installed). Reuses the
# same layer-``name`` channel as the stats markers: it survives ``+``/layer/concat, unlike custom
# ``usermeta`` (which Altair strips across ``+``). ``metadata._strip_markers`` already deletes any
# name starting with ``__dysonsphere_``, so these are cleaned from the written spec for free.
_EXT_MARKER_PREFIX = "__dysonsphere_ext_"


def _tag_extension(chart: _AltairChart, name: str) -> _AltairChart:
    """Tag ``chart`` as produced by the extension ``name`` (e.g. ``"biology"``) so ``save()``
    records that extension's version in provenance. The tag is a view-``name`` marker that
    survives composition (``+``/layer/concat) and is stripped from the written spec."""
    return chart.properties(name=f"{_EXT_MARKER_PREFIX}{name}")


def _used_extensions(spec: dict) -> dict[str, str]:
    """``{name: version}`` for every extension whose usage marker (see :func:`_tag_extension`)
    appears in ``spec`` - the extensions that actually produced this figure, not just the
    installed ones. Empty when none. Versions come from the installed entry points' dists."""
    names: set[str] = set()

    def walk(o: object) -> None:
        if isinstance(o, dict):
            nm = o.get("name")
            if isinstance(nm, str) and nm.startswith(_EXT_MARKER_PREFIX):
                names.add(nm[len(_EXT_MARKER_PREFIX) :])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(spec)
    eps = _extension_entry_points()
    out: dict[str, str] = {}
    for n in sorted(names):
        ep = eps.get(n)
        if ep is not None and ep.dist is not None:
            out[n] = ep.dist.version
    return out
