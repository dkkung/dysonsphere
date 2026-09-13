"""API for dysonsphere extensions (``dysonsphere.ext``).

Extensions use these core helpers to match core chart behavior for metadata filtering and theme
styling. Import them from ``dysonsphere.ext`` rather than private core modules. The re-exported
names are stable and changes follow the usual public-API deprecation process.

The current API supports the composite annotation used by the volcano plot:

- **``AltairChart``** - the chart-object union (``alt.Chart | LayerChart | FacetChart |
  VConcatChart | HConcatChart | ConcatChart``). Use it as the return annotation for a
  composite constructor, matching core's ``save()`` signature.

- **``opt(key)``** - read an active-theme option (``opt("markSize")``, ``opt("width")``,
  ``opt("fontSize")``, ``opt("darkmode")``, …). Falls back to the derived built-in default
  when called before any ``ds.theme()``, so styling code receives derived defaults rather than
  ``None`` values.
  Unknown keys raise ``KeyError``. This is the ONLY supported way to read theme options
  outside core.

- **``internal_data(data)``** - tag a dysonsphere-generated annotation dataset (label
  coordinates, computed reference frames, …) so ``ds.metadata.read(what="data")`` filters it out and
  returns only the user's dataframe(s). Accepts a ``list[dict]`` (→ ``alt.Data``) or a
  polars/pandas DataFrame (→ tagged polars df); pass the result straight to
  ``alt.Chart(...)``.

  Route every generated data source through ``internal_data`` -
  ``alt.Chart(internal_data(rows_or_df))``. An untagged dataset can appear as a user dataframe
  or cause a false multi-frame error in ``read``. Do not tag the user's frame; tagging it hides
  that data from ``read``. Tag data computed by the extension and leave caller-provided data alone.

  **Facet caveat:** an ``internal_data`` dataset gives its layer its own data source, which makes
  the composite un-faceteable (Altair requires all layers of a faceted chart to share one
  data variable). Core's facet-safe annotations take a ``data=`` param and build on a shared
  base instead; that helper (``_datum_base``) is not yet part of this API - ask if
  your extension needs faceting.

- **``tag_extension(chart, name)``** - tag a chart your extension built so ``ds.save()`` records
  your extension's version in the figure's provenance (``environment["dysonsphere-extensions"]``,
  grouped right under ``dysonsphere``). Call it once on the chart you return:
  ``return ext.tag_extension(chart, "biology")``. The tag is a durable, unique
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
