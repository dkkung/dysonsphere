---
title: "Saving & loading"
description: "Export charts to files and rebuild them from the Vega-Lite JSON."
sidebar:
  order: 10
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

## `save`

```python
def save(
    chart: _AltairChart | Callable[[], _AltairChart],
    filename: str,
    ppi: int = 1200,
    description: str | None = None,
    saveMetadata: bool = True,
    embedReport: bool = True,
    format: str | list[str] | None = None,
    background: str | list[str] | None = None,
    transparent: bool = True,
    maxRows: int = 5000,
    overrideMaxRows: bool = False,
) -> None: ...
```

Save a chart in one or more formats and background variants.

Which files are written is controlled by ``format`` (``"svg"``/``"png"``/``"json"``)
and ``background`` (``"light"``/``"dark"``), each defaulting to the theme options
``saveFormat`` / ``saveBackground``. A background suffix (``_light`` / ``_dark``) is
added **only when more than one background** is rendered — a single-background export
keeps clean names::

    ds.save(chart, "fig")                      # fig.svg + fig.json   (defaults)
    ds.save(chart, "fig", format="png")        # fig.png
    ds.save(chart, "fig", background=["light", "dark"])
    #   → fig_light.svg / fig_dark.svg + fig_light.json / fig_dark.json

Each background toggles ``darkmode`` for its render, restoring the original after.

**Parameters**

- **`chart`** (`_AltairChart | Callable[[], _AltairChart]`) - The Altair chart to save, or a zero-argument callable that returns one. Accepts any Altair compound chart type: ``Chart``, ``LayerChart``, ``FacetChart``, ``VConcatChart``, ``HConcatChart``, or ``ConcatChart``. When a callable is provided it is called fresh for each variant — after ``darkmode`` has been toggled — so any marks whose colours depend on ``ds.theme()`` (e.g. ``add_multilabel``) are rebuilt with the correct palette each time.
- **`filename`** (`str`) - Extensionless path for the output files (e.g. ``"myplot"`` or ``"plots/myplot"``). A bare name saves to the current working directory, matching Altair's default behaviour.
- **`ppi`** (`int`) - Pixel density for PNG output.
- **`description`** (`str | None`) - Optional, purely your own text. Stored verbatim (nothing appended) in the Vega-Lite JSON spec's ``description`` field, the SVG ``<desc>`` element, and the PNG ``iTXt Description`` chunk. Independent of ``saveMetadata``.
- **`format`** (`str | list[str] | None`) - Which file format(s) to write: any of ``"svg"``, ``"png"``, ``"json"`` (the raw Vega-Lite spec), or ``"html"`` (a self-contained interactive page, Vega JS bundled in), as a single string or a list. ``None`` (default) uses the theme option ``saveFormat`` (``["svg", "json"]``). An empty list or unknown value raises. ``"html"`` is the **interactive** tier: it renders live in the browser via Vega, so it is fully themed, carries the metadata block, and gets exact tick positions (that fix lives in the theme config), but it does NOT get dysonsphere's static SVG post-processors (superscript typesetting, Illustrator-friendly flattening). In particular ``inwardTicks`` is deliberately **not** applied to HTML: the only way to make Vega draw ticks inward is a negative ``tickSize``, and while that works in vl-convert's Vega (the static SVG/PNG path), the browser bundles a different Vega build that lays out axis labels wrong with a negative ``tickSize`` (mangled label spacing), so it renders inconsistently and is left off. Use ``"svg"``/``"png"`` for the publication-accurate static figure.
- **`background`** (`str | list[str] | None`) - Which background variant(s) to render: ``"light"`` and/or ``"dark"`` (each toggles ``darkmode``), as a single string or a list. ``None`` (default) uses the theme option ``saveBackground`` (``"light"``). An empty list or unknown value raises.
- **`transparent`** (`bool`) - Whether the rendered SVG/PNG have a transparent background. ``True`` (default): exported figures composite onto any page or slide. ``False``: the background is filled with the theme's ``chartFill`` (white in light mode, black in dark mode, unless set explicitly) - for outputs viewed on their own, e.g. images embedded in a README. Applies to the SVG/PNG render only; the JSON and HTML keep the chart's logical background (the theme option ``transparent``).
- **`maxRows`** (`int`) - Row cap for the data inlined into the output (default ``5000``, matching Altair). Every format renders via ``chart.to_dict()``, which inlines the data, and the JSON embeds it for :func:`read` — so data over this many rows would make the files huge and is **blocked with a clear error**. Raise it to allow larger data.
- **`overrideMaxRows`** (`bool`) - If ``True``, removes the row cap entirely for this save (inlines all rows, however many). The deliberate opt-in for large data.
- **`saveMetadata`** (`bool`) - If ``True`` (default), embeds a **structured JSON** metadata block — ``{"provenance": {...}, "statistics": [...]}`` — in every output format so each is self-contained and machine-readable: - ``provenance`` — generation facts as fields: ``user``, ``script``, ``chart`` (best-effort source text of the ``chart`` argument at this call site — the variable name or inline composition, e.g. ``"boxplot + points"``; omitted when the source is unavailable, e.g. in a plain REPL), ``timestamp`` (ISO-8601), ``environment`` (OS + toolchain versions), then the identity fields ``vegaliteChecksum``/``exportIdentifier``/``dataChecksum``. In Jupyter, ``script`` is ``"<jupyter-notebook>"``; ``user`` falls back to ``"unknown_user"``. - ``statistics`` — the structured records queued by ``add_comparisons`` (groups, omnibus result, comparisons with exact p-values and effect sizes); omitted when there are none. It lands in the **Vega-Lite JSON** under ``usermeta.dysonsphere`` (merged into any ``usermeta`` already on the chart), the **SVG** ``<metadata id="dysonsphere">`` element (CDATA), and the **PNG** ``iTXt dysonsphere`` chunk. ``saveMetadata=False`` suppresses the structured block entirely; your ``description`` (if any) is still written.
- **`embedReport`** (`bool`) - If ``True`` (default) and ``saveMetadata`` is on, also embeds the human-readable **report table** (the descriptive + effect-size text from ``add_comparisons`` / ``add_correlation``) so you can read it straight out of the file — as a ``report`` member of ``usermeta.dysonsphere`` in the **JSON**, and as a dedicated readable channel (real newlines, not escaped JSON) in the **SVG** (``<metadata id="dysonsphere-report">``) and **PNG** (``iTXt dysonsphere-report``). It never touches ``description`` (your text only). Set ``False`` to keep just the structured block. (Also available standalone via ``add_comparisons(report=True)``.)

**Examples**

```python
Static chart::

    ds.theme()
    chart = alt.Chart(df).mark_point().encode(...)
    ds.save(chart, "plots/myplot")

Callable — rebuilt per variant so dark-mode colours are correct::

    ds.save(
        lambda: ds.add_multilabel(chart, CONDITIONS, style="symbol"),
        "plots/myplot",
        background=["light", "dark"],
    )
```

## `show`

```python
def show(chart: _AltairChart | Callable[[], _AltairChart]): ...
```

Render *chart* through the full ``ds.save()`` pipeline and return it for accurate
inline display in a notebook.

Altair's own inline renderer (used when you just display a chart) does NOT run
dysonsphere's SVG post-processors, so its preview is approximate - superscript labels
aren't typeset, the axisOffset grid gap remains, and with ``inwardTicks=True`` the
ticks still point outward. ``ds.show(chart)`` renders the *same* corrected SVG that
:func:`save` writes and returns it as an ``IPython.display.SVG`` for inline display, so
the preview matches the saved figure. It renders at the theme's current ``darkmode`` and
writes no file.

Accepts the same chart types as :func:`save`, including a zero-argument callable (called
once). Requires IPython (present in any notebook); otherwise raises ``ImportError`` - use
:func:`save` to write a file instead.

## `load`

```python
def load(
    path: str,
    *,
    raw: bool = False,
    applyTheme: bool = True,
) -> '_AltairChart | dict[str, Any]': ...
```

Rebuild the chart from a dysonsphere-exported Vega-Lite JSON (the ``.json`` spec).

JSON only — the PNG/SVG carry the metadata block but not the full spec.

**Parameters**

- **`raw`** (`bool`) - ``False`` (default) returns a composable Altair object (of the right type). Its theme ``config`` is stripped (Altair's schema rejects a few of dysonsphere's config values), so it comes back unstyled — see ``applyTheme``. ``True`` returns the raw Vega-Lite spec ``dict`` instead, ``config`` intact, which re-renders pixel-identically (e.g. via ``vl_convert``) but is not a composable Altair object.
- **`applyTheme`** (`bool`) - For ``raw=False``: ``True`` (default) re-applies the theme baked into the file via ``ds.theme(**saved_args)`` so the object renders exactly as saved. Like any ``ds.theme()`` call this **replaces the active theme globally**. ``False`` leaves the current theme untouched (the object is styled by whatever theme is active).
