---
title: "Extension authoring"
description: "The stable primitive surface for extension authors (dysonsphere.ext)."
sidebar:
  order: 4
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

Public primitive surface for dysonsphere extension authors (``dysonsphere.ext``).

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

## `tag_extension`

```python
def tag_extension(chart: _AltairChart, name: str) -> _AltairChart: ...
```

Tag ``chart`` as produced by the extension ``name`` (e.g. ``"biology"``) so ``save()``
records that extension's version in provenance. The tag is a view-``name`` marker that
survives composition (``+``/layer/concat) and is stripped from the written spec.

## `internal_data`

```python
def internal_data(
    data: list[dict[str, Any]] | pl.DataFrame | Any,
) -> Any: ...
```

Tag dysonsphere-generated (non-user) chart data with the internal sentinel column.

Accepts a list of record dicts (returned as an ``alt.Data``) or a polars/pandas
DataFrame (returned as a polars DataFrame with the sentinel column added).  Pass the
result straight to ``alt.Chart(...)``.

## `opt`

```python
def opt(key: str) -> Any: ...
```

Read a theme option, falling back to the (derived) built-in default.

The single accessor for theme options outside theme.py — replaces scattered
``alt.theme.options.get(key, hardcoded)`` calls, whose per-site hardcoded fallbacks
could silently drift from ``_BUILTIN_DEFAULTS``. After ``ds.theme()`` every option is
present in ``alt.theme.options``, so the fallback only matters when a chart helper is
called before any ``theme()``; it then sees the fully derived built-in defaults
(``markSize`` 10.0, ``axisOffset`` 4.5, …), computed once and cached. Unknown keys
raise ``KeyError``.
