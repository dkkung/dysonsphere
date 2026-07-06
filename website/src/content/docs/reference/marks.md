---
title: "Marks"
description: "Composite marks: strip and violin plots."
sidebar:
  order: 3
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

## `mark_violin`

```python
mark_violin(
    df: pl.DataFrame | Any,
    xCol: str,
    yCol: str,
    categories: list[str],
    *,
    boxplotSize: int | None = None,
    boxplotColor: str = 'black',
    medianColor: str = 'white',
    palette: str | list[str] | None = None,
    fillOpacity: float | None = None,
    stroke: str | None = None,
    strokeWidth: float | None = None,
    legend: bool = False,
    xLabelAngle: float | None = None,
    labelMap: Mapping[Any, str | list[str]] | None = None,
    steps: int = 200,
    yTitle: str | None | _UnsetType = _UNSET,
    xTitle: str | None | _UnsetType = _UNSET,
) -> alt.LayerChart
```

Build an Altair layer combining a violin plot behind a boxplot.

Returns a ``LayerChart`` that can be saved directly or composed with other
layers (e.g. ``ds.add_comparisons``).

The returned ``LayerChart`` is safe to place in ``alt.hconcat()`` alongside
``mark_strip()`` or any other chart - the violin uses absolute ``x:Q``
coordinates internally rather than ``xOffset``, so Vega-Lite's xOffset
scale resolution never squishes the violin shape.

**Parameters**

- **`df`** (`pl.DataFrame | Any`) - Polars DataFrame containing the data.
- **`xCol`** (`str`) - Column name for the grouping variable (x-axis).
- **`yCol`** (`str`) - Column name for the value variable (y-axis).
- **`categories`** (`list[str]`) - Ordered list of all x-axis categories, used for positioning and axis labels.
- **`boxplotSize`** (`int | None`) - Width of the boxplot box in pixels.
- **`boxplotColor`** (`str`) - Fill color of the boxplot.
- **`medianColor`** (`str`) - Fill color of the boxplot median line. Defaults to ``"white"`` so it reads against the default black box; overrides the theme's ``markMedianFill``.
- **`palette`** (`str | list[str] | None`) - Fill color of all violins. When ``None``, each group inherits its color from the theme's active category palette.
- **`fillOpacity`** (`float | None`) - Fill opacity of the violin. Inherits ``markFillOpacity`` from theme when ``None``.
- **`stroke`** (`str | None`) - Outline color of the violin. Defaults to ``None`` (no outline).
- **`strokeWidth`** (`float | None`) - Width of the violin outline. Inherits ``markStrokeWidth`` from theme when ``None``.
- **`xLabelAngle`** (`float | None`) - X-axis label rotation in degrees. Negative tilts left (e.g. ``-45``), positive tilts right; ``labelAlign`` is derived automatically from the sign. ``None`` inherits from ``theme(xLabelAngle)``.
- **`labelMap`** (`Mapping[Any, str | list[str]] | None`) - ``{raw_value: label}`` mapping applied to the x-axis tick labels at render time via :func:`label_expr` - the data keeps the raw values. A label may be a list of strings for a multi-line label. Unmapped values show as-is.
- **`steps`** (`int`) - Number of y grid points used for KDE estimation (per group).
- **`yTitle`** (`str | None | _UnsetType`) - Y-axis title. Defaults to ``yCol``. Pass ``None`` to suppress.
- **`xTitle`** (`str | None | _UnsetType`) - X-axis title. Defaults to ``xCol``. Pass ``None`` to suppress.

**Examples**

```python
::

    ds.theme(chartWidth=250)
    chart = ds.mark_violin(df, "group", "value", CATEGORIES)
    ds.save(chart, "violin")

    # safe in hconcat with mark_strip
    left = ds.mark_strip(df, "group", "value", CATEGORIES)
    right = ds.mark_violin(df, "group", "value", CATEGORIES)
    ds.save(alt.hconcat(left, right), "comparison")

    # with optional outline and custom colors
    chart = ds.mark_violin(
        df, "group", "value", CATEGORIES,
        boxplotSize=10,
        palette="#AAAAAA",
        stroke="black",
        strokeWidth=0.5,
    )
```

## `mark_strip`

```python
mark_strip(
    df: pl.DataFrame | Any,
    xCol: str,
    yCol: str,
    categories: list[str],
    *,
    scatter: str = 'jitter',
    palette: list[str] | None = None,
    markSize: int | None = None,
    markOpacity: float | None = None,
    spread: float | None = None,
    legend: bool = False,
    xLabelAngle: float | None = None,
    labelMap: Mapping[Any, str | list[str]] | None = None,
    errorbars: bool = True,
    errorbarExtent: str = 'sem',
    yTitle: str | None | _UnsetType = _UNSET,
    xTitle: str | None | _UnsetType = _UNSET,
) -> alt.LayerChart
```

Build an Altair layer combining jittered or beeswarm points with a median indicator.

Returns a ``LayerChart`` that can be saved directly or composed with other
layers (e.g. ``ds.add_comparisons``).

**Parameters**

- **`df`** (`pl.DataFrame | Any`) - Polars DataFrame containing the data.
- **`xCol`** (`str`) - Column name for the grouping variable (x-axis).
- **`yCol`** (`str`) - Column name for the value variable (y-axis).
- **`categories`** (`list[str]`) - Ordered list of all x-axis categories.
- **`scatter`** (`str`) - Point distribution method: ``'jitter'`` (faster, random Gaussian offset) or ``'beeswarm'`` (collision-avoidance, better for smaller n).
- **`markSize`** (`int | None`) - Size of individual points. Inherits ``markSize`` from theme when ``None``.
- **`markOpacity`** (`float | None`) - Opacity of individual points. Inherits ``markFillOpacity`` from theme when ``None``.
- **`spread`** (`float | None`) - Controls point spread in pixels. For ``'jitter'``: standard deviation of the Gaussian offsets (~68% of points within ±spread). For ``'beeswarm'``: collision radius (points placed so no two centres are closer than 2·spread); total width grows with n.
- **`xLabelAngle`** (`float | None`) - X-axis label rotation in degrees. Negative tilts left (e.g. ``-45``), positive tilts right; ``labelAlign`` is derived automatically from the sign. ``None`` inherits from ``theme(xLabelAngle)``.
- **`labelMap`** (`Mapping[Any, str | list[str]] | None`) - ``{raw_value: label}`` mapping applied to the x-axis tick labels at render time via :func:`label_expr` - the data keeps the raw values. A label may be a list of strings for a multi-line label. Unmapped values show as-is.
- **`errorbars`** (`bool`) - Whether to show error bars around the group mean. When ``True``, the mean is shown as a tick with error bars. When ``False``, the median is shown instead.
- **`errorbarExtent`** (`str`) - Statistic to use for error bars: ``'sem'`` (standard error of the mean, default) or ``'sd'`` (standard deviation).
- **`yTitle`** (`str | None | _UnsetType`) - Y-axis title. Defaults to ``yCol``. Pass ``None`` to suppress.
- **`xTitle`** (`str | None | _UnsetType`) - X-axis title. Defaults to ``xCol``. Pass ``None`` to suppress.

**Examples**

```python
::

    ds.theme()
    chart = ds.mark_strip(df, "group", "value", CATEGORIES)
    ds.save(chart, "strip")

    # beeswarm variant
    chart = ds.mark_strip(df, "group", "value", CATEGORIES, scatter="beeswarm")
```
