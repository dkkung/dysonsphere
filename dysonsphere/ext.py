"""Public primitive surface for dysonsphere extension authors (``dysonsphere.ext``).

Extensions (e.g. ``dysonsphere-biology``) build composite charts that must behave like
first-class dysonsphere objects - their generated data filtered correctly by
``ds.read(what="data")``, their styling driven by the active theme. That requires a handful of
core primitives which are otherwise ``_``-private. This module is the **stable, versioned
contract**: import from here (``from dysonsphere import ext``), never reach into
``dysonsphere.utils._internal_data`` / ``dysonsphere.theme._opt`` / etc. directly - those
signatures are free to change; the names re-exported here are not (changes go through a
deprecation cycle, like any public API).

Kept deliberately **minimal**. Primitives are promoted here only once a real consumer needs
them (growing a public surface is cheap and non-breaking; walking one back is not). The
current set is what a composite scatter annotation - the volcano plot - actually uses.

Surface:

- **``AltairChart``** - the chart-object union (``alt.Chart | LayerChart | FacetChart |
  VConcatChart | HConcatChart | ConcatChart``). Use it as the return annotation for a
  composite constructor, matching core's own ``save()`` signature.

- **``opt(key)``** - read an active-theme option (``opt("markSize")``, ``opt("chartWidth")``,
  ``opt("fontSize")``, ``opt("darkmode")``, …). Falls back to the derived built-in default
  when called before any ``ds.theme()``, so styling code never sees ``None`` sentinels.
  Unknown keys raise ``KeyError``. This is the ONLY supported way to read theme options
  outside core.

- **``internal_data(data)``** - tag a dysonsphere-GENERATED "sidecar" dataset (label
  coordinates, computed reference frames, …) so ``ds.read(what="data")`` filters it out and
  returns only the user's dataframe(s). Accepts a ``list[dict]`` (→ ``alt.Data``) or a
  polars/pandas DataFrame (→ tagged polars df); pass the result straight to
  ``alt.Chart(...)``.

  **DISCIPLINE:** route EVERY generated data source through ``internal_data`` -
  ``alt.Chart(internal_data(rows_or_df))``. Miss one and that sidecar leaks as a phantom
  "user" dataframe (a false multi-frame error from ``read``, or the wrong frame returned).
  Conversely, do NOT tag the USER's own frame (the points you were handed) - tagging it would
  hide the user's data from ``read``. Rule of thumb: data you computed → tag it; data the
  caller passed in → leave it.

  **Facet caveat:** an ``internal_data`` sidecar gives its layer its own dataset, which makes
  the composite un-faceteable (Altair requires all layers of a faceted chart to share one
  data variable). Core's facet-safe annotations take a ``data=`` param and build on a shared
  base instead; that helper (``_datum_base``) is not yet part of this public surface - ask if
  your extension needs faceting.

- **``tag_extension(chart, name)``** - tag a chart your extension built so ``ds.save()`` records
  your extension's version in the figure's provenance (``environment["dysonsphere-extensions"]``,
  grouped right under ``dysonsphere``). Call it once on the chart you return:
  ``return ext.tag_extension(chart, "biology")``. The tag is a durable
  view-name marker that survives ``+``/layer/concat and is stripped from the written spec, so it
  only affects provenance - never the rendered output. ``name`` is your extension's registered
  entry-point name (the ``ds.<name>`` alias); its version is looked up from the installed
  distribution. Only extensions that actually produced a figure are recorded (not merely installed).
"""

from __future__ import annotations

from .discovery import _tag_extension as tag_extension
from .export import _AltairChart as AltairChart
from .theme import _opt as opt
from .utils import _internal_data as internal_data

__all__ = ["AltairChart", "internal_data", "opt", "tag_extension"]
