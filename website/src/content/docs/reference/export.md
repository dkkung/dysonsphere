---
title: "Saving & loading"
description: "Export charts to files and rebuild them from the Vega-Lite JSON."
sidebar:
  order: 11
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

## `save`

```python
def save(
    chart: _AltairChart | Callable[[], _AltairChart],
    filename: str | Path,
    *,
    ppi: int = 1200,
    description: str | None = None,
    saveMetadata: bool = True,
    embedReport: bool = True,
    format: str | list[str] | None = None,
    background: str | list[str] | None = None,
    transparent: bool = True,
    maxRows: int | None = None,
) -> None: ...
```

Save a chart in one or more formats and background variants.

Which files are written is controlled by ``format`` (``"svg"``/``"png"``/``"tiff"``/``"json"``/``"html"``)
and ``background`` (``"light"``/``"dark"``), each defaulting to the theme options
``saveFormat`` / ``saveBackground``. A background suffix (``_light`` / ``_dark``) is
added only when multiple backgrounds are rendered – a single-background export
keeps names without a background suffix::

    ds.save(chart, "fig")                      # fig.svg + fig.json   (defaults)
    ds.save(chart, "fig", format="png")        # fig.png
    ds.save(chart, "fig", background=["light", "dark"])
    #   → fig_light.svg / fig_dark.svg + fig_light.json / fig_dark.json

Each background toggles ``darkmode`` for its render, restoring the original after.

Point labels are placed once per background against the complete composed panel before writing
any format, so JSON, HTML, SVG, PNG, and TIFF start with the same obstacle-aware layout.

Labels are typeset on export (SVG/PNG/TIFF): a ``^`` marks a superscript (``"x^2"``, ``"10^3"``)
and a double underscore marks a subscript (``"C__t"`` -> C with a subscript t; single ``_`` is
left alone so snake_case column names used as default titles are not mangled). Unicode
super/subscripts you type (``"H₂O"``, ``"t₀"``) and log/p-value exponents are normalized to
smaller, shifted text characters. Script digits and letters become ASCII; the superscript minus
becomes Unicode U+2212, so rendering does not depend on Unicode superscript/subscript glyphs.
Saved SVGs rewrite font names for Illustrator; PNG and TIFF retain the original CSS font-family
stack so the raster renderer can select the intended installed family.

**Parameters**

- **`chart`** (`_AltairChart | Callable[[], _AltairChart]`) - The Altair chart to save, or a zero-argument callable that returns one. Accepts any Altair compound chart type: ``Chart``, ``LayerChart``, ``FacetChart``, ``VConcatChart``, ``HConcatChart``, or ``ConcatChart``. When a callable is provided it is called fresh for each variant – after ``darkmode`` has been toggled – so any marks whose colors depend on ``ds.theme()`` (e.g. ``add_multilabel``) are rebuilt with the correct palette each time.
- **`filename`** (`str | Path`) - Extensionless path for the output files (e.g. ``"myplot"`` or ``"plots/myplot"``). A bare name saves to the current working directory, matching Altair's default behavior.
- **`ppi`** (`int`) - Pixel density for PNG and TIFF output. TIFF records this value directly in its horizontal and vertical resolution tags, in pixels per inch.
- **`description`** (`str | None`) - Optional text stored verbatim in the Vega-Lite JSON spec's ``description`` field, the SVG ``<desc>`` element, and the PNG ``iTXt Description`` chunk. TIFF stores it in the ``description`` field of its JSON ``ImageDescription`` envelope. It is independent of ``saveMetadata``.
- **`format`** (`str | list[str] | None`) - Which file format(s) to write: any of ``"svg"``, ``"png"``, ``"tiff"``, ``"json"`` (the raw Vega-Lite spec), or ``"html"`` (a self-contained interactive page, Vega JS bundled in), as a single string or a list. ``None`` (default) uses the theme option ``saveFormat`` (``["svg", "json"]``). An empty list or unknown value raises. ``dysonsphere.SAVE_FORMATS`` is the immutable tuple of accepted format names, shared with theme validation. It lists supported names, not runtime dependency availability or the active default formats. ``"tiff"`` writes an 8-bit RGB or RGBA publication figure with lossless LZW compression, using the corrected PNG pixels without resampling. Pillow with libtiff support is required and checked before any files are written. ``"html"`` renders an interactive chart in the browser using Vega. It uses the theme, includes metadata when ``saveMetadata`` is enabled, and retains exact tick positions from the theme configuration. It does not receive Dysonsphere's static SVG processing, including superscript typesetting and Illustrator-specific flattening. ``tickDirection="in"`` is not applied to HTML. Static SVG/PNG/TIFF rendering reverses the rendered SVG tick-line geometry; HTML does not use this SVG correction. Negative ``tickSize`` values also produce inconsistent axis-label layout across browser Vega builds, so HTML leaves ticks outward. Use ``"svg"``, ``"png"``, or ``"tiff"`` for static output with SVG post-processing.
- **`background`** (`str | list[str] | None`) - Which background variant(s) to render: ``"light"`` and/or ``"dark"`` (each toggles ``darkmode``), as a single string or a list. ``None`` (default) uses the theme option ``saveBackground`` (``"light"``). An empty list or unknown value raises.
- **`transparent`** (`bool`) - Whether SVG/PNG/TIFF rendering requests a transparent background. ``True`` (default) requests transparency unless the chart specifies its own background. ``False`` fills an unset background with the theme's ``chartFill`` (white in light mode, black in dark mode, unless set explicitly). This applies to SVG/PNG/TIFF rendering only; the JSON and HTML keep the chart's logical background (the theme option ``transparent``). TIFF uses RGB when this is ``False`` and RGBA when ``True``. An explicitly transparent or translucent chart background is incompatible with RGB TIFF; use an opaque background or ``transparent=True`` rather than silently dropping alpha.
- **`maxRows`** (`int | None`) - Optional row cap for each dataframe processed during export. ``None`` (default) removes Altair's standard 5000-row cap. Set an integer to reject larger data sources with a clear error. Every format resolves through ``chart.to_dict()``; JSON and HTML retain the inlined data, while static rendering still materializes it during export.
- **`saveMetadata`** (`bool`) - If ``True`` (default), embeds a structured JSON metadata block – ``{"provenance": {...}, "statistics": [...]}`` – in every output format so each is self-contained and machine-readable: - ``provenance`` – generation facts as fields: ``user``, ``script``, ``chart`` (best-effort source text of the ``chart`` argument at this call site – the variable name or inline composition, e.g. ``"boxplot + points"``; omitted when the source is unavailable, e.g. in a plain REPL), ``timestamp`` (ISO-8601), ``environment`` (OS + toolchain versions), then the identity fields ``vegaliteChecksum``/``exportIdentifier``/``dataChecksum``. In Jupyter, ``script`` is ``"<jupyter-notebook>"``; ``user`` falls back to ``"unknown_user"``. - ``statistics`` – the structured records queued by ``stats.comparisons`` (groups, omnibus result, comparisons with exact p-values and effect sizes); omitted when there are none. It lands in the Vega-Lite JSON under ``usermeta.dysonsphere`` (merged into any ``usermeta`` already on the chart), the SVG ``<metadata id="dysonsphere">`` element (CDATA), the PNG ``iTXt dysonsphere`` chunk, and the ``dysonsphere`` member of TIFF's JSON ``ImageDescription`` envelope (tag 270). TIFF uses ASCII-escaped JSON so Unicode descriptions and reports are retained exactly. ``saveMetadata=False`` suppresses the structured block entirely. The ``description``, if supplied, is still written. Reproducible exports. ``timestamp`` and ``exportIdentifier`` normally change on every call, so re-saving an unchanged figure rewrites its bytes. Setting the ``SOURCE_DATE_EPOCH`` environment variable (the reproducible-builds convention: an integer count of UTC seconds) pins the timestamp to that instant and derives the identifier from the figure's own content, making repeated saves byte-identical – useful when figures are committed alongside a manuscript. Distinct figures still get distinct identifiers, and the light/dark variants of one export still share one.
- **`embedReport`** (`bool`) - If ``True`` (default) and ``saveMetadata`` is on, also embeds the human-readable report table (the descriptive and effect-size text from ``stats.comparisons`` / ``stats.correlation``) as a ``report`` member of ``usermeta.dysonsphere`` in the JSON and of the ``dysonsphere`` block in TIFF's JSON envelope, and as a dedicated readable channel (real newlines, not escaped JSON) in the SVG (``<metadata id="dysonsphere-report">``) and PNG (``iTXt dysonsphere-report``). It never touches ``description`` (your text only). Set ``False`` to keep just the structured block. (Also available standalone via ``stats.comparisons(report=True)``.)

**Examples**

```python
Static chart::

    ds.theme()
    chart = alt.Chart(df).mark_point().encode(...)
    ds.save(chart, "plots/myplot")

Callable – rebuilt per variant so dark-mode colors are correct::

    ds.save(
        lambda: ds.add_multilabel(chart, CONDITIONS, style="symbol"),
        "plots/myplot",
        background=["light", "dark"],
    )
```

## `show`

```python
def show(
    chart: _AltairChart | Callable[[], _AltairChart],
    *,
    maxRows: int | None = None,
) -> 'HTML': ...
```

Render *chart* with the SVG processing used by ``ds.save()`` and return it for inline
display in a notebook.

Altair's inline renderer does not run dysonsphere's SVG processing, so it leaves superscript
labels untypeset, retains the axisOffset grid gap, and draws ticks outward when
``tickDirection="in"`` is set. ``ds.show(chart)`` applies the same SVG corrections used by
:func:`save` and returns the result as ``IPython.display.HTML`` for inline display, so
the preview matches the saved figure. It renders at the theme's current ``darkmode`` and
``transparent`` and writes no file.

This also places labels from the saved point coordinates and label settings; no extra placement
call is needed.

The SVG is returned as HTML rather than ``IPython.display.SVG`` so the preview uses the
notebook's own background, like a bare Altair chart. An ``image/svg+xml`` output goes to the
frontend's image renderer instead. In VS Code, that renderer composites the SVG onto a white
canvas, so transparent dark-mode content can be hard to see.

Like :func:`save`, the render is wrapped in the ``"default"`` data transformer so
``ds.show()`` works regardless of whichever transformer is active in the session – in
particular ``vegafusion``, which otherwise makes Altair's ``to_dict()`` raise because
dysonsphere's SVG processing needs the Vega-Lite specification. ``maxRows=None`` (default)
allows any number of rows; set an integer to reject larger data sources with a clear
:class:`ValueError`. Dense charts can produce large SVG output and require substantial memory.

Accepts the same chart types as :func:`save`, including a zero-argument callable (called
once). Requires IPython (present in any notebook); otherwise raises ``ImportError`` - use
:func:`save` to write a file instead.

**Returns**

- `IPython.display.HTML` - The corrected SVG wrapped for inline notebook display.

## `load`

```python
def load(
    path: str | Path,
    *,
    output: Literal['chart', 'spec'] = 'chart',
    applyTheme: bool = True,
) -> '_AltairChart | dict[str, Any]': ...
```

Load a dysonsphere-exported Vega-Lite JSON as a chart or specification.

Use the default ``output="chart"`` to rebuild an editable, composable Altair object. Current-version
statistical records are restored with their owning chart components, so composition, panel extraction,
and a later :func:`save` preserve only the records still represented. Their numerical results and
source-data checksums are preserved, not recomputed. Loaded records retain a guard over their saved
analytical panel; changing data, mappings, transforms, parameters, or annotation values makes a later
save fail closed and requires rebuilding the annotation from source data. Presentation edits and intact
panel composition remain valid.

Use ``output="spec"`` only when the untouched Vega-Lite dictionary is needed for inspection or external
tooling. This mode is equivalent to parsing the JSON directly: it does not reconstruct an Altair object,
restore chart-owned statistical records, or apply the saved theme. Rendering the dictionary directly also
omits Dysonsphere's static SVG processing.

``load`` accepts Vega-Lite JSON only; PNG/SVG exports may carry a metadata block but not the
full specification. Files from earlier versions receive no adapter. Lookup transforms,
runtime parameters/selections, external data, and
expressions beyond deterministic operations on ``datum`` cannot be preserved when rebuilding a chart.

**Parameters**

- **`output`** (`Literal['chart', 'spec']`) - ``"chart"`` (default) returns a composable Altair object of the appropriate type. Its saved theme ``config`` is stripped because Altair's schema rejects some Dysonsphere config values; see ``applyTheme``. ``"spec"`` returns the untouched Vega-Lite dictionary, including its ``config``, datasets, metadata, and other export properties.
- **`applyTheme`** (`bool`) - For ``output="chart"``, ``True`` (default) re-applies the theme baked into the file via ``ds.theme(**saved_args)`` so the object renders as saved. Like any ``ds.theme()`` call, this replaces the active theme globally. ``False`` leaves the current theme untouched, so the object uses whatever theme is active. This parameter has no effect for ``output="spec"``.

**Returns**

- `_AltairChart | dict[str, Any]` - A composable Altair chart for ``output="chart"`` or the untouched specification dictionary for ``output="spec"``.
