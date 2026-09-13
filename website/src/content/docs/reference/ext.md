---
title: "Extension authoring"
description: "The stable primitive surface for extension authors (dysonsphere.ext)."
sidebar:
  order: 4
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

Public API for dysonsphere extension authors (``dysonsphere.ext``).

Extensions use these core helpers to match core chart behavior for metadata filtering and theme
styling. Import them from ``dysonsphere.ext`` rather than private core modules. The re-exported
names are stable and changes follow the usual public-API deprecation process.

The current API supports the composite annotation used by the volcano plot:

- **``AltairChart``** - the chart-object union (``alt.Chart | LayerChart | FacetChart |
  VConcatChart | HConcatChart | ConcatChart``). Use it as the return annotation for a
  composite constructor, matching core's ``save()`` signature.

- **``opt(key)``** - read an active-theme option (``opt("markSize")``, ``opt("width")``,
  ``opt("fontSize")``, ``opt("darkmode")``, …). Falls back to the derived built-in default
  when called before any ``ds.theme()``, so styling code never sees ``None`` sentinels.
  Unknown keys raise ``KeyError``. This is the ONLY supported way to read theme options
  outside core.

- **``internal_data(data)``** - tag a dysonsphere-GENERATED "sidecar" dataset (label
  coordinates, computed reference frames, …) so ``ds.metadata.read(what="data")`` filters it out and
  returns only the user's dataframe(s). Accepts a ``list[dict]`` (→ ``alt.Data``) or a
  polars/pandas DataFrame (→ tagged polars df); pass the result straight to
  ``alt.Chart(...)``.

  Route every generated data source through ``internal_data`` -
  ``alt.Chart(internal_data(rows_or_df))``. An untagged sidecar can appear as a user dataframe
  or cause a false multi-frame error in ``read``. Do not tag the user's frame; tagging it hides
  that data from ``read``. Tag data computed by the extension and leave caller-provided data alone.

  **Facet caveat:** an ``internal_data`` sidecar gives its layer its own dataset, which makes
  the composite un-faceteable (Altair requires all layers of a faceted chart to share one
  data variable). Core's facet-safe annotations take a ``data=`` param and build on a shared
  base instead; that helper (``_datum_base``) is not yet part of this public surface - ask if
  your extension needs faceting.

- **``tag_extension(chart, name)``** - tag a chart your extension built so ``ds.save()`` records
  your extension's version in the figure's provenance (``environment["dysonsphere-extensions"]``,
  grouped right under ``dysonsphere``). Call it once on the chart you return:
  ``return ext.tag_extension(chart, "biology")``. The tag is a durable, unique
  view-name marker that survives ``+``/layer/concat and is stripped from the written spec, so it
  only affects provenance - never the rendered output. ``name`` is your extension's registered
  entry-point name (the ``ds.<name>`` alias); its version is looked up from the installed
  distribution. Only extensions that actually produced a figure are recorded (not merely installed).

## `tag_extension`

```python
def tag_extension(chart: _AltairChart, name: str) -> _AltairChart: ...
```

Tag ``chart`` as produced by the extension ``name`` (e.g. ``"biology"``) so ``save()``
records that extension's version in provenance.

The unique view-name marker survives composition and is stripped from the written spec.
An existing name is carried inside it so statistical identity is not overwritten and a
user-supplied name can be restored when internal markers are removed.

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
(``markSize`` 10.0, ``axisOffset`` 0, …), computed once and cached. Unknown keys
raise ``KeyError``.
