---
title: "Extensions"
description: "Discover extensions and use the extension-author API (dysonsphere.ext)."
sidebar:
  order: 3
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

Extension discovery implementation and author API (``dysonsphere.ext``).

Optional distributions register an entry point under ``dysonsphere.extensions``, for example
``biology = "dysonsphere_biology"``. Core uses these entry points to enumerate extensions and lazily
resolve aliases such as ``ds.biology``. Users discover and explicitly load extensions through the
canonical ``ds.extensions()`` and ``ds.load_extension()`` call paths, not through ``ds.ext``.

Extension authors use the supported names below to match core chart behavior for metadata filtering
and theme styling. Import them from ``dysonsphere.ext`` rather than private core modules. These names
are stable and changes follow the usual public-API deprecation process.

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
  distribution. It returns a tagged chart copy and does not mutate ``chart``. Only extensions that
  actually produced a figure are recorded (not merely installed).

## `extensions`

Call as `ds.extensions(...)`.

```python
def extensions() -> list[str]: ...
```

Implement the canonical ``ds.extensions()`` discovery call.

Return the sorted names of installed dysonsphere extensions.

Each name is also accessible as an attribute of the top-level ``dysonsphere`` module
(e.g. ``dysonsphere.biology`` when ``dysonsphere-biology`` is installed).

## `load_extension`

Call as `ds.load_extension(...)`.

```python
def load_extension(name: str) -> ModuleType: ...
```

Implement the canonical ``ds.load_extension(name)`` discovery call.

Import and return the extension registered under ``name``.

Equivalent to accessing ``dysonsphere.<name>`` but explicit. Raises ``ImportError`` with
the list of installed extensions if no extension is registered under ``name``.

## `tag_extension`

Call as `ds.ext.tag_extension(...)`.

```python
def tag_extension(chart: AltairChart, name: str) -> AltairChart: ...
```

Return a tagged chart copy carrying the extension name for export provenance.

The unique view-name marker survives composition and is stripped from the written spec.
An existing name is carried inside it so statistical and user-supplied identity survives.

## `internal_data`

Call as `ds.ext.internal_data(...)`.

```python
def internal_data(
    data: list[dict[str, Any]] | pl.DataFrame | Any,
) -> Any: ...
```

Tag dysonsphere-generated (non-user) chart data with the internal marker column.

Accepts a list of record dicts (returned as an ``alt.Data``) or a polars/pandas
DataFrame (returned as a polars DataFrame with the marker column added). Pass the
result straight to ``alt.Chart(...)``.

## `opt`

Call as `ds.ext.opt(...)`.

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
