---
title: "Multilabels"
description: "Attach a multilabel annotation table below a chart."
sidebar:
  order: 7
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

## `add_multilabel`

```python
def add_multilabel(
    chart: alt.Chart | alt.LayerChart | alt.ConcatChart | alt.VConcatChart | alt.HConcatChart,
    groups: dict[str, list[Any]] | None = None,
    categories: list[str] | None = None,
    *,
    spacing: float = 0,
    showSampleSize: bool = False,
    data: pl.DataFrame | pd.DataFrame | None = None,
    x: str | None = None,
    sampleSizeIndex: int = 0,
    sampleSizeLabel: str = 'n =',
    order: list[str] | None = None,
    style: str = 'plusminus',
    rowStyles: dict[str, str] | list[str] | None = None,
    labelPosition: str = 'left',
    labelPadding: float = 0,
    symbol: str = 'circle',
    symbolSize: float | None = None,
    palette: list[str] | None = None,
    strokeWidth: float | None = None,
    connectingLine: bool = True,
    lineOrientation: str = 'vertical',
    chartWidth: float | None = None,
    fontSize: float | None = None,
    rowHeight: int | float | dict[str, int | float] | list[int | float] | None = None,
    rowValueAngle: int | float | dict[str, Any] | list[Any] | None = None,
    categoryLabel: bool = False,
    categoryLabelPosition: str = 'bottom',
    labelMap: dict[str, Any] | None = None,
    categoryLabelAngle: float = -45,
    categoryLabelHeight: float | None = None,
    span: dict[str | None, list[str]] | list[dict[str | None, list[str]]] | None = None,
    spanBracketStyle: str = 'line',
    spanLabelPosition: str = 'bottom',
    spanBracketReverse: bool = True,
    spanTickHeight: float | None = None,
    spanGap: float | None = None,
) -> alt.VConcatChart: ...
```

Compose a chart with a grid annotation table, replacing its x-axis labels.

Accepts ``alt.Chart`` or ``alt.LayerChart`` (e.g. a strip+boxplot layer), and also a
concatenated chart - ``_strip_x_labels`` recurses into ``vconcat``/``hconcat`` panels, so a
stack of panels sharing one x-layout (e.g. ``ds.biology.western_blot``'s image strips) gets
the table below the whole stack. A ``vconcat`` is the sensible case; a table under an
``hconcat`` of differently-x'd panels composes but rarely aligns meaningfully.
Strips x-axis labels and ticks from ``chart``, builds a condition table via
:func:`_multilabel_layer`, and returns
``alt.vconcat(chart, annotation, spacing=spacing).resolve_scale(x="shared")``.

Both ``groups`` and ``categories`` are optional. Omit ``groups`` (or pass
``{}``) when you only need sample sizes or category labels.

**Parameters**

- **`chart`** (`alt.Chart | alt.LayerChart | alt.ConcatChart | alt.VConcatChart | alt.HConcatChart`) - The main Altair chart (any type: ``Chart``, ``LayerChart``, etc.).
- **`groups`** (`dict[str, list[Any]] | None`) - ``{row_label: [value, ...]}`` mapping, one value per category. Defaults to ``{}`` — omit entirely when only ``showSampleSize`` or ``categoryLabel`` is needed.
- **`categories`** (`list[str] | None`) - Ordered list of x-axis categories matching the main chart. Defaults to ``None`` (empty list); must be provided when ``showSampleSize=True`` or when ``categoryLabel=True``.
- **`spacing`** (`float`) - Vertical gap in pixels between the chart and the annotation table. Defaults to ``0`` so the annotation sits flush below the axis line.
- **`showSampleSize`** (`bool`) - When ``True``, injects a per-category sample size row computed from ``data``. Requires ``data`` and ``x``. The row always renders as ``"text"`` regardless of the global ``style`` setting.
- **`data`** (`pl.DataFrame | pd.DataFrame | None`) - Source DataFrame (Polars or Pandas) for counting samples per category. Only used when ``showSampleSize=True``.
- **`x`** (`str | None`) - Column name in ``data`` used for x-axis grouping. Only used when ``showSampleSize=True``.
- **`sampleSizeIndex`** (`int`) - Insertion index among the ``groups`` rows, using ``list.insert()`` semantics. ``0`` (default) places the n-row first; ``len(groups)`` places it last. Negative indices follow Python convention (``-1`` is second-to-last, not last). Applies to ``order`` too when one is given, unless that ``order`` names ``sampleSizeLabel`` itself.
- **`sampleSizeLabel`** (`str`) - Row label for the sample size row. Defaults to ``"n ="``. Name it in ``order`` to place the row yourself.
- **`order`** (`list[str] | None`) - Row display order (top to bottom). Defaults to ``dict`` insertion order. Every listed label must be a key of ``groups`` and must occur only once; listing only some rows displays only those rows. Per-row mapping options are checked against all keys in ``groups``, including rows omitted from ``order``.
- **`style`** (`str`) - Global default style for all rows. ``"plusminus"`` renders ``True`` as ``+`` and ``False`` as ``−``. ``"symbol"`` renders ``True`` as a filled mark and ``False`` as an unfilled mark, with a connecting rule between consecutive ``True`` values (direction set by ``lineOrientation``). The mark shape is controlled by ``symbol``. ``"text"`` renders raw group values as center-aligned strings and is forced automatically per row when any value in that row is non-bool. Override per row with ``rowStyles``.
- **`rowStyles`** (`dict[str, str] | list[str] | None`) - Per-row style overrides. Accepts either a ``dict`` mapping row labels to style strings (``{"Row A": "symbol", "Row B": "text"}``) or a ``list`` of style strings in row-display order (``["symbol", "text"]``). Accepts the same values as ``style``. Non-bool rows always render as ``"text"`` regardless of this setting. Connecting rules only span between ``"symbol"`` rows; rows of other styles between symbol rows are skipped in run detection.
- **`labelPosition`** (`str`) - ``"left"`` (default) places row labels to the left of the grid with right-aligned text. ``"right"`` places them to the right with left-aligned text.
- **`labelPadding`** (`float`) - Gap in pixels between the plot boundary and the label text. Vega-Lite's default is 2. Negative values pull the labels into the plot area.
- **`symbol`** (`str`) - Vega-Lite shape name for ``"symbol"`` style marks (e.g. ``"circle"``, ``"square"``, ``"diamond"``, ``"triangle-up"``). Defaults to ``"circle"``.
- **`symbolSize`** (`float | None`) - Area (in square pixels) of each symbol. Defaults to ``markSize * 4`` from ``ds.theme()``.
- **`palette`** (`list[str] | None`) - List of colors used to fill annotation marks in ``"symbol"`` style. ``palette[0]`` overrides the ``False`` mark color and ``palette[-1]`` the ``True`` mark color. Overrides darkmode defaults when provided. Pass the result of ``ds.palette()`` directly.
- **`strokeWidth`** (`float | None`) - Stroke width applied to dot marks and the connecting rule. Defaults to ``markStrokeWidth`` from ``ds.theme()``.
- **`connectingLine`** (`bool`) - When ``True`` (default), draws a rule spanning each consecutive run of ``True`` values (``"symbol"`` style only). Set to ``False`` to show symbols only. Direction is controlled by ``lineOrientation``.
- **`lineOrientation`** (`str`) - Direction of the connecting rule. ``"vertical"`` (default) draws a rule down each column spanning consecutive ``True`` rows. ``"horizontal"`` draws a rule across each row spanning consecutive ``True`` columns.
- **`chartWidth`** (`float | None`) - Width of the annotation chart in pixels. Inherits ``width`` from ``ds.theme()`` when not set.
- **`fontSize`** (`float | None`) - Font size for ``"text"`` style symbols and row labels. Inherits ``fontSize`` from ``ds.theme()`` when not set.
- **`rowHeight`** (`int | float | dict[str, int | float] | list[int | float] | None`) - Height in pixels per annotation row. Accepts a single number applied to every row, a ``dict`` mapping row labels to heights, or a ``list`` of heights in row-display order. A ``dict`` may be partial; unlisted rows are auto-sized. Auto-sizing gives an unrotated row ``10`` px and a rotated row the height of its rotated text bounding box (never less than ``10``).
- **`rowValueAngle`** (`int | float | dict[str, Any] | list[Any] | None`) - Rotation of the row's values in degrees, in every style — the text of a ``"text"`` or ``"plusminus"`` row, and the marks of a ``"symbol"`` row. Accepts a single number applied to every row, a ``dict`` mapping row labels to angles, or a ``list`` of angles in row-display order. Defaults to ``0`` (horizontal). Use ``-90`` to read bottom-to-top and ``90`` to read top-to-bottom. Values rotate about their own center, so they stay centered on the category, and rotated rows grow to fit their tallest rotated cell unless ``rowHeight`` pins them. Row labels are never rotated. Rotating the default ``"circle"`` symbol has no visible effect; use a shape with lineOrientation, such as ``symbol="triangle-up"``. A single row's angle may itself be a ``list`` — one angle per x-axis category — to rotate only some cells, e.g. standing dose values on end while leaving the ``-`` placeholders of the untreated controls upright:: rowValueAngle={"dose": [0, 0, -90, -90, -90]}
- **`categoryLabel`** (`bool`) - When ``True``, renders the x-axis category names as angled text in a dedicated row, replacing the main chart's stripped axis labels within the annotation. Defaults to ``False``.
- **`categoryLabelPosition`** (`str`) - Where to place the category label row relative to the data rows. ``"bottom"`` (default) places labels below all rows; ``"top"`` places them above.
- **`categoryLabelAngle`** (`float`) - Rotation angle of the category name text in degrees. Defaults to ``-45``.
- **`categoryLabelHeight`** (`float | None`) - Height in pixels reserved for the x-label row. Auto-computed from ``fontSize``, ``categoryLabelAngle``, and the longest category name when ``None`` (default): ``ceil(fontSize × 0.6 × max_len × |sin(angle)| + fontSize × |cos(angle)|)``.
- **`labelMap`** (`dict[str, Any] | None`) - ``{raw_value: label}`` mapping applied to the category-label row (plain lookup; the data and band positions keep the raw values). List labels are space-joined here - use the mark constructors' ``labelMap`` for true multi-line axis labels.
- **`span`** (`dict[str | None, list[str]] | list[dict[str | None, list[str]]] | None`) - Dict mapping span label → list of categories, or a list of such single-entry dicts (one per span). The span extends from the lowest to the highest index in ``categories`` found in the list. Use ``""`` as a key (or ``None``) to draw a rule/bracket with no label; the list form allows multiple unlabeled spans without key collisions:: span={"Group 1": ["Cat A", "Cat B"], "Group 2": ["Cat C", "Cat D"]} span=[{None: ["Cat A", "Cat B"]}, {None: ["Cat C", "Cat D"]}]
- **`spanBracketStyle`** (`str`) - ``"line"`` (default) draws a plain horizontal rule. ``"bracket"`` adds vertical end ticks at the left and right edges of the span.
- **`spanLabelPosition`** (`str`) - Where to place the span label relative to the rule. ``"bottom"`` (default) places it below; ``"top"`` places it above.
- **`spanBracketReverse`** (`bool`) - When ``True`` (default), bracket end ticks point toward the annotation rows. When ``False``, they point away. No effect when ``spanBracketStyle="line"``.
- **`spanTickHeight`** (`float | None`) - Height in pixels of the bracket end ticks. Defaults to the active theme ``tickSize``. Only used when ``spanBracketStyle="bracket"``.
- **`spanGap`** (`float | None`) - Vertical gap in pixels between the last annotation row and the span rule. Defaults to ``rowHeight × 0.3``.

**Examples**

```python
::

    chart = ds.mark_strip(data, "group", "value", CATEGORIES)

    # Full multilabel with sample sizes and category labels
    composed = ds.add_multilabel(
        chart,
        {"Condition A": [False, True, True, True]},
        categories=CATEGORIES,
        style="symbol",
        showSampleSize=True,
        data=data,
        x="group",
        categoryLabel=True,
    )
    ds.save(composed, "my_plot")

    # Sample sizes only — no groups needed
    ds.add_multilabel(chart, categories=CATEGORIES, showSampleSize=True, data=data, x="group")
```
