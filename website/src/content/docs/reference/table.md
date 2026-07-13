---
title: "Tables"
description: "Render a DataFrame as a publication-styled table."
sidebar:
  order: 13
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

Render a DataFrame as a publication-styled table via a composite Altair mark.

## `mark_table`

```python
def mark_table(
    df: pl.DataFrame | Any,
    columns: list[str] | None = None,
    *,
    header: bool = True,
    headerLabels: dict[str, str] | None = None,
    columnFormat: dict[str, str] | None = None,
    sigFigs: int | None = None,
    align: dict[str, str] | str | None = None,
    strokes: Sequence[str] | str = ('outer', 'header'),
    palette: str | list[str] = 'greys',
    striping: bool = True,
    nStripes: int = 2,
    cellColor: dict[str, str] | None = None,
    textColor: str | dict[str, str] | None = None,
    fontStyle: str | dict[str, str] | None = None,
    fontSize: float | None = None,
    headerFontStyle: str = 'bold',
    headerColor: str | None = None,
    headerFill: str | bool = False,
    cellPadding: float | None = None,
    rowHeight: float | None = None,
    columnWidths: list[float] | dict[str, float] | None = None,
    strokeColor: str | None = None,
    strokeWidth: float | None = None,
) -> alt.LayerChart: ...
```

Render ``df`` as a styled table: an ``alt.LayerChart`` that composes like any other mark.

The table lays cells out in pixel space (so it drops into ``+`` / ``hconcat`` / ``vconcat``
without scale-merge surprises) but drives every per-row mark off the **user's dataframe** via
``transform_window`` (row index) and ``transform_calculate`` (formatted labels, contrast
colours). Those transforms never touch the inlined data, so ``read(what="data")`` and the
provenance ``dataChecksum`` recover the frame you passed **byte-for-byte** - only the fixed
chrome (strokes, header text) rides on internal sidecar datasets.

Because a table cannot render at the 100×100 default canvas, ``mark_table`` sizes itself from
the row/column counts and a per-column content estimate, overriding ``chartWidth`` /
``chartHeight``. Column widths are proportional-font estimates (Vega cannot measure text at
build time); pass ``columnWidths`` for exact control.

**Darkmode** is resolved at BUILD time (like ``add_shade`` / ``add_multilabel``): the stripe
fills sample the dark end of the palette and the strokes / auto-contrast colours flip when the
table is built under ``theme(darkmode=True)`` (cell text with no explicit colour follows the
theme's darkmode-aware ``config.text`` at render). So set the theme before building, or - to
export light AND dark from one call - pass a **callable** to ``ds.save()`` so the table is
rebuilt per background::

    ds.save(lambda: ds.mark_table(df, ...), "table", background=["light", "dark"])

**Parameters**

- **`df`** (`pl.DataFrame | Any`) - The data to tabulate (Polars or Pandas). Never mutated.
- **`columns`** (`list[str] | None`) - Columns to show, in order. ``None`` (default) uses every column in ``df`` order.
- **`header`** (`bool`) - Draw the header row of column labels. Default ``True``.
- **`headerLabels`** (`dict[str, str] | None`) - ``{column: display label}`` to rename headers (unlisted columns keep their name).
- **`columnFormat`** (`dict[str, str] | None`) - ``{column: format}`` for numeric columns. Each value is either a **notation keyword** - ``"scientific"`` (``1.23×10⁻⁵``), ``"power"`` (``10⁻⁵``, nearest power of ten), ``"e"`` (``1.2e-5``), ``"si"`` (``12k``) - honouring ``sigFigs``, or any **d3/printf format spec** (``".2g"``, ``".1f"``, ``","`` …). The two superscript notations reuse the SVG typesetting the rest of dysonsphere applies, so exponents render aligned and any leading statistical symbol is italicised. Unlisted numeric columns default to ``sigFigs`` significant figures; string columns render verbatim.
- **`sigFigs`** (`int | None`) - Significant figures for the notation keywords and the numeric default. ``None`` (default) reads ``theme(sigFigs=…)``.
- **`align`** (`dict[str, str] | str | None`) - Text alignment. ``None`` (default) is **type-aware**: numeric columns are right-aligned (so decimals and units line up) and everything else is left-aligned. A single ``"left"``/``"center"``/``"right"`` forces all columns; a ``{column: side}`` dict overrides per column (unlisted columns keep the type-aware default).
- **`strokes`** (`Sequence[str] | str`) - Which rules to draw, as any combination of ``"outer"`` (the border), ``"header"`` (the header/body separator), ``"rows"`` (between data rows), ``"cols"`` (between columns), ``"grid"`` (= ``rows`` + ``cols``, the interior grid), and ``"all"`` (every rule - ``outer`` + ``header`` + ``rows`` + ``cols``). A single string is accepted. Default ``("outer", "header")``.
- **`palette`** (`str | list[str]`) - Palette (name or hex list) for row striping. Default ``"greys"``. The lightest ``nStripes`` stops are used in light mode, the darkest in dark mode.
- **`striping`** (`bool`) - Shade alternating rows. Default ``True``.
- **`nStripes`** (`int`) - Number of stripe colours to alternate through. Default ``2``.
- **`cellColor`** (`dict[str, str] | None`) - ``{column: palette}`` to shade cells by value (a heatmap column). The column's values map across the palette (a 13-stop diverging palette is centred on 0; otherwise the domain is the column's ``[min, max]``), and each cell's text switches to black or white for contrast. Overrides striping within that column.
- **`textColor`** (`str | dict[str, str] | None`) - Body cell text colour. ``None`` (default) inherits the theme's darkmode-aware text colour. A single string colours every body cell; a ``{column: colour}`` dict colours per column (unlisted columns inherit). A ``cellColor`` (value-shaded) column keeps its automatic black/white contrast unless you give it an explicit **dict** entry here (a per-column colour is taken as deliberate; a global string does not override the heatmap's contrast).
- **`fontStyle`** (`str | dict[str, str] | None`) - Body cell font style (e.g. ``"italic"``, ``"bold"``, ``"normal"``). ``None`` (default) inherits. A single string styles every body cell; a ``{column: style}`` dict styles per column (unlisted columns inherit) - e.g. ``{"gene": "italic"}`` for italic gene names.
- **`fontSize`** (`float | None`) - Cell font size. ``None`` (default) reads ``theme(fontSize=…)``.
- **`headerFontStyle`** (`str`) - Font style for header labels (e.g. ``"bold"``, ``"normal"``, ``"italic"``). Default ``"bold"``.
- **`headerColor`** (`str | None`) - Header text colour. ``None`` (default) inherits the theme's text colour, or - when ``headerFill`` is set - auto-contrasts (black/white) against the fill. A string sets a fixed colour.
- **`headerFill`** (`str | bool`) - Background band behind the header row, following the ``bool | str`` pattern: ``False`` (default) → none; ``True`` → a darkmode-aware default grey band; a string → that colour.
- **`cellPadding`** (`float | None`) - Horizontal padding inside a cell, in px. ``None`` (default) → ``fontSize * 0.6``.
- **`rowHeight`** (`float | None`) - Row height in px. ``None`` (default) → ``round(fontSize * 2)``. The header row uses the same height.
- **`columnWidths`** (`list[float] | dict[str, float] | None`) - Override the estimated widths: a list in ``columns`` order, or a ``{column: width}`` dict (unlisted columns keep their estimate).
- **`strokeColor`** (`str | None`) - Rule colour. ``None`` (default) → darkmode-aware black/white.
- **`strokeWidth`** (`float | None`) - Rule width in px. ``None`` (default) → the theme's ``axisWidth``.

**Returns**

- `alt.LayerChart` - A self-sized table. Compose with ``+`` or concatenate; export with ``ds.save()``.

**Examples**

```python
::

    tbl = ds.mark_table(
        df,
        columns=["gene", "log2FC", "pvalue"],
        columnFormat={"log2FC": ".2f", "pvalue": "scientific"},
        cellColor={"log2FC": "pinksblues"},
        strokes=("outer", "header", "rows"),
    )
    ds.save(tbl, "table")
```
