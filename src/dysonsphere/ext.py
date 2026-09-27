"""Extension discovery implementation and author API (``dysonsphere.ext``).

Optional distributions register an entry point under ``dysonsphere.extensions``, for example
``biology = "dysonsphere_biology"``. Core uses these entry points to enumerate extensions and lazily
resolve aliases such as ``ds.biology``. Users discover and explicitly load extensions through the
canonical ``ds.extensions()`` and ``ds.load_extension()`` call paths, not through ``ds.ext``.

Extension authors use the supported names below to match core chart behavior for metadata filtering
and theme styling. Import them from ``dysonsphere.ext`` rather than private core modules. These names
are stable and changes follow the usual public-API deprecation process.

The current API supports the composite annotation used by the volcano plot:

- **``AltairChart``** – the chart-object union (``alt.Chart | LayerChart | FacetChart |
  VConcatChart | HConcatChart | ConcatChart``). Use it as the return annotation for a
  composite constructor, matching core's ``save()`` signature.

- **``opt(key)``** – read an active-theme option (``opt("markSize")``, ``opt("width")``,
  ``opt("fontSize")``, ``opt("darkmode")``, …). Falls back to the derived built-in default
  when called before any ``ds.theme()``, so styling code receives derived defaults rather than
  ``None`` values.
  Unknown keys raise ``KeyError``. This is the supported way to read theme options
  outside core.

- **``internal_data(data)``** – tag a dysonsphere-generated annotation dataset (label
  coordinates, computed reference frames, …) so ``ds.metadata.read(what="data")`` filters it out and
  returns only the user's dataframe(s). Accepts a ``list[dict]`` (→ ``alt.Data``) or a
  polars/pandas DataFrame (→ tagged polars df); pass the result straight to
  ``alt.Chart(...)``.

  Route every generated data source through ``internal_data`` –
  ``alt.Chart(internal_data(rows_or_df))``. An untagged dataset can appear as a user dataframe
  or cause a false multi-frame error in ``read``. Do not tag the user's frame; tagging it hides
  that data from ``read``. Tag data computed by the extension and leave caller-provided data alone.

  **Facet caveat:** an ``internal_data`` dataset gives its layer its own data source, which prevents
  the composite from being faceted (Altair requires all layers of a faceted chart to share one
  data variable). Core's facet-safe annotations accept a ``data=`` parameter and build on a shared
  base. Their helper (``_datum_base``) is not part of this API.

- **``tag_extension(chart, name)``** – tag a chart your extension built so ``ds.save()`` records
  your extension's version in the figure's provenance (``environment["dysonsphere-extensions"]``,
  alongside ``dysonsphere``). Call it once on the chart you return:
  ``return ext.tag_extension(chart, "biology")``. The tag is a durable, unique
  view-name marker that survives ``+``/layer/concat and is stripped from the written spec, so it
  affects provenance but not the rendered output. ``name`` is your extension's registered
  entry-point name (the ``ds.<name>`` alias); its version is looked up from the installed
  distribution. It returns a tagged chart copy and does not mutate ``chart``. Only extensions that
  actually produced a figure are recorded (not merely installed).
"""

from __future__ import annotations

import importlib.metadata
from types import ModuleType
from typing import Any, Union

import altair as alt

from .theme import _opt as opt
from .utils import _internal_data as internal_data

__all__ = ["AltairChart", "internal_data", "opt", "tag_extension"]

# This is the single chart-type definition shared by extension authors and core export code.
AltairChart = Union[
    alt.Chart,
    alt.LayerChart,
    alt.FacetChart,
    alt.VConcatChart,
    alt.HConcatChart,
    alt.ConcatChart,
]

_ENTRY_POINT_GROUP = "dysonsphere.extensions"


def _extension_entry_points() -> dict[str, importlib.metadata.EntryPoint]:
    """Return installed extension entry points keyed by their registered name."""
    return {ep.name: ep for ep in importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP)}


def extensions() -> list[str]:
    """Implement the canonical ``ds.extensions()`` discovery call.

    Return the sorted names of installed dysonsphere extensions.

    Each name is also accessible as an attribute of the top-level ``dysonsphere`` module
    (e.g. ``dysonsphere.biology`` when ``dysonsphere-biology`` is installed).
    """
    return sorted(_extension_entry_points())


def load_extension(name: str) -> ModuleType:
    """Implement the canonical ``ds.load_extension(name)`` discovery call.

    Import and return the extension registered under ``name``.

    Equivalent to accessing ``dysonsphere.<name>`` but explicit. Raises ``ImportError`` with
    the list of installed extensions if no extension is registered under ``name``.
    """
    ep = _extension_entry_points().get(name)
    if ep is None:
        available = extensions()
        hint = f"installed extensions: {', '.join(available)}" if available else "no extensions are installed"
        raise ImportError(f"no dysonsphere extension named {name!r} is installed ({hint})")
    return ep.load()


_EXT_MARKER_PREFIX = "__dysonsphere_ext_"
_EXT_MARKER_SEPARATOR = "::"
_ext_marker_counter = 0


def tag_extension(chart: AltairChart, name: str) -> AltairChart:
    """Return a tagged chart copy carrying the extension name for export provenance.

    The unique view-name marker survives composition and is stripped from the written spec.
    An existing name is carried inside it so statistical and user-supplied identity survives.
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
    """Return versions of extensions whose usage markers appear in ``spec``."""
    names: set[str] = set()

    def walk(value: object) -> None:
        if isinstance(value, dict):
            marker_names, _ = _unwrap_extension_markers(value.get("name"))
            names.update(marker_names)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(spec)
    eps = _extension_entry_points()
    out: dict[str, str] = {}
    for name in sorted(names):
        ep = eps.get(name)
        if ep is not None and ep.dist is not None:
            out[name] = ep.dist.version
    return out
