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

The public functions are ``extensions()`` (list installed names) and
``load_extension(name)`` (import one by name). Both live here; ``__getattr__`` delegates to
``_extension_entry_points``.
"""

from __future__ import annotations

import importlib.metadata
from types import ModuleType
from typing import TYPE_CHECKING, Any

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


# Extension-usage provenance. Extensions use durable view-name markers so save() records the
# packages that produced a figure. View names survive composition, unlike custom usermeta.
_EXT_MARKER_PREFIX = "__dysonsphere_ext_"
_EXT_MARKER_SEPARATOR = "::"
_ext_marker_counter = 0


def _tag_extension(chart: _AltairChart, name: str) -> _AltairChart:
    """Tag ``chart`` as produced by the extension ``name`` (e.g. ``"biology"``) so ``save()``
    records that extension's version in provenance.

    The unique view-name marker survives composition and is stripped from the written spec.
    An existing name is carried inside it so statistical identity is not overwritten and a
    user-supplied name can be restored when internal markers are removed.
    """
    global _ext_marker_counter
    _ext_marker_counter += 1
    previous = getattr(chart, "name", None)
    suffix = f"{_EXT_MARKER_SEPARATOR}{previous}" if isinstance(previous, str) else ""
    return chart.properties(name=f"{_EXT_MARKER_PREFIX}{name}_{_ext_marker_counter}{suffix}")


def _parse_extension_marker(value: object) -> tuple[str, str | None] | None:
    """Return an extension marker's registered name and carried view name, if present."""
    if not isinstance(value, str) or not value.startswith(_EXT_MARKER_PREFIX):
        return None
    marker, separator, previous = value.partition(_EXT_MARKER_SEPARATOR)
    body = marker[len(_EXT_MARKER_PREFIX) :]
    name, counter_separator, counter = body.rpartition("_")
    if not counter_separator or not name or not counter.isdigit():
        return None
    return name, previous if separator else None


def _unwrap_extension_markers(value: object) -> tuple[list[str], str | None]:
    """Return every nested extension name and the underlying non-extension view name."""
    names: list[str] = []
    current = value
    while (parsed := _parse_extension_marker(current)) is not None:
        names.append(parsed[0])
        current = parsed[1]
    return names, current if isinstance(current, str) else None


def _used_extensions(spec: dict[str, Any]) -> dict[str, str]:
    """``{name: version}`` for every extension whose usage marker (see :func:`_tag_extension`)
    appears in ``spec`` - the extensions that actually produced this figure, not just the
    installed ones. Empty when none. Versions come from the installed entry points' dists."""
    names: set[str] = set()

    def walk(o: object) -> None:
        if isinstance(o, dict):
            marker_names, _ = _unwrap_extension_markers(o.get("name"))
            names.update(marker_names)
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
