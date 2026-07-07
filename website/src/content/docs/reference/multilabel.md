---
title: "Multilabels"
description: "Attach a multilabel annotation table below a chart."
sidebar:
  order: 5
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

## `add_multilabel`

```python
def add_multilabel(
    chart: alt.Chart | alt.LayerChart,
    groups: dict[str, list] | None = None,
    categories: list[str] | None = None,
    *,
    spacing: int = 0,
    showSampleSize: bool = False,
    df = None,
    xCol: str | None = None,
    sampleSizeIndex: int = 0,
    sampleSizeLabel: str = 'n =',
    **kwargs,
) -> alt.VConcatChart: ...
```

Compose a chart with a grid annotation table, replacing its x-axis labels.

Accepts ``alt.Chart`` or ``alt.LayerChart`` (e.g. a strip+boxplot layer).
Strips x-axis labels and ticks from ``chart``, builds a condition table via
:func:`_multilabel_layer`, and returns
``alt.vconcat(chart, annotation, spacing=spacing).resolve_scale(x="shared")``.

Both ``groups`` and ``categories`` are optional. Omit ``groups`` (or pass
``{}``) when you only need sample sizes or category labels.

All keyword arguments beyond the named parameters are forwarded to
:func:`_multilabel_layer` — see its docstring for the full parameter list,
including ``style``, ``rowStyles``, ``categoryLabel``,
``categoryLabelPosition``, ``categoryLabelAngle``, ``categoryLabelHeight``,
``span``, ``spanBracketStyle``, ``spanLabelPosition``, ``spanBracketReverse``,
``spanTickHeight``, and ``spanGap``.

**Parameters**

- **`chart`** (`alt.Chart | alt.LayerChart`) - The main Altair chart (any type: ``Chart``, ``LayerChart``, etc.).
- **`groups`** (`dict[str, list] | None`) - ``{row_label: [value, ...]}`` mapping, one value per category. Defaults to ``{}`` — omit entirely when only ``showSampleSize`` or ``categoryLabel`` is needed.
- **`categories`** (`list[str] | None`) - Ordered list of x-axis categories matching the main chart. Defaults to ``None`` (empty list); must be provided when ``showSampleSize=True`` or when ``categoryLabel=True``.
- **`spacing`** (`int`) - Vertical gap in pixels between the chart and the annotation table. Defaults to ``0`` so the annotation sits flush below the axis line.
- **`showSampleSize`** (`bool`) - When ``True``, injects a per-category sample size row computed from ``df``. Requires ``df`` and ``xCol``. The row always renders as ``"text"`` regardless of the global ``style`` setting.
- **`df`** - Source DataFrame (Polars or Pandas) for counting samples per category. Only used when ``showSampleSize=True``.
- **`xCol`** (`str | None`) - Column name in ``df`` used for x-axis grouping. Only used when ``showSampleSize=True``.
- **`sampleSizeIndex`** (`int`) - Insertion index among the ``groups`` rows, using ``list.insert()`` semantics. ``0`` (default) places the n-row first; ``len(groups)`` places it last. Negative indices follow Python convention (``-1`` is second-to-last, not last).
- **`sampleSizeLabel`** (`str`) - Row label for the sample size row. Defaults to ``"n ="``.

**Examples**

```python
::

    chart = ds.mark_strip(df, "group", "value", CATEGORIES)

    # Full multilabel with sample sizes and category labels
    composed = ds.add_multilabel(
        chart,
        {"Condition A": [False, True, True, True]},
        categories=CATEGORIES,
        style="symbol",
        showSampleSize=True,
        df=df,
        xCol="group",
        categoryLabel=True,
    )
    ds.save(composed, "my_plot")

    # Sample sizes only — no groups needed
    ds.add_multilabel(chart, categories=CATEGORIES, showSampleSize=True, df=df, xCol="group")
```
