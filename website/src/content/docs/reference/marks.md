---
title: "Marks"
description: "Composite marks: strip and violin plots."
sidebar:
  order: 5
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

## `mark_violin`

```python
def mark_violin(
    df: pl.DataFrame | Any,
    xCol: str,
    yCol: str,
    categories: list[str],
    *,
    inner: str | None = 'quartiles',
    innerColor: str | None = None,
    boxplotSize: int | None = None,
    boxplotColor: str = 'black',
    medianColor: str = 'white',
    palette: str | list[str] | None = None,
    fillOpacity: float | None = None,
    stroke: str | bool | None = True,
    strokeWidth: float | None = None,
    legend: bool = False,
    xLabelAngle: float | None = None,
    labelMap: Mapping[Any, str | list[str]] | None = None,
    steps: int = 200,
    trim: bool = False,
    bandwidth: float | None = None,
    yTitle: str | None | _UnsetType = _UNSET,
    xTitle: str | None | _UnsetType = _UNSET,
) -> alt.LayerChart: ...
```

Build an Altair layer combining a violin plot with an inner statistic display.

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
- **`inner`** (`str | None`) - Inner statistic display: ``"quartiles"`` (default) draws Prism-style horizontal lines - a solid median (at twice the outline ``strokeWidth``, clipped to the violin border) and dashed quartiles (at the outline ``strokeWidth``) - each spanning the violin's width at that value; ``"median"`` draws only the median line; ``"box"`` embeds a boxplot; ``None`` draws the violin outline only.
- **`innerColor`** (`str | None`) - Color of the median/quartile lines (``"quartiles"``/``"median"``). ``None`` (default) means ``"black"`` in both light and dark mode - the lines sit inside the mark fill, not on the background, so they are deliberately not darkmode-sensitive.
- **`boxplotSize`** (`int | None`) - Width of the boxplot box in pixels (``inner="box"`` only).
- **`boxplotColor`** (`str`) - Fill color of the boxplot (``inner="box"`` only).
- **`medianColor`** (`str`) - Fill color of the boxplot median line (``inner="box"`` only). Defaults to ``"white"`` so it reads against the default black box; overrides the theme's ``markMedianFill``.
- **`palette`** (`str | list[str] | None`) - Fill color of all violins. When ``None``, each group inherits its color from the theme's active category palette.
- **`fillOpacity`** (`float | None`) - Fill opacity of the violin. Inherits ``markFillOpacity`` from theme when ``None``.
- **`stroke`** (`str | bool | None`) - Outline color of the violin. ``True`` (default) uses the theme's ``markStroke`` (black - kept black in dark mode too, outlining the light palette fills like ``mark_strip``'s points); ``False`` or ``None`` disables the outline; a string sets the color directly.
- **`strokeWidth`** (`float | None`) - Width of the violin outline. Inherits ``markStrokeWidth`` from theme when ``None``.
- **`xLabelAngle`** (`float | None`) - X-axis label rotation in degrees. Negative tilts left (e.g. ``-45``), positive tilts right; ``labelAlign`` is derived automatically from the sign. ``None`` inherits from ``theme(xLabelAngle)``.
- **`labelMap`** (`Mapping[Any, str | list[str]] | None`) - ``{raw_value: label}`` mapping applied to the x-axis tick labels at render time via :func:`label_expr` - the data keeps the raw values. A label may be a list of strings for a multi-line label. Unmapped values show as-is.
- **`steps`** (`int`) - Number of y grid points used for KDE estimation (per group).
- **`trim`** (`bool`) - When ``True``, evaluate the KDE only on the group's data range so the violin ends sharply at the observed min/max. When ``False`` (default), the tails extend 2 KDE bandwidths beyond the data extremes.
- **`bandwidth`** (`float | None`) - KDE bandwidth (``scipy.stats.gaussian_kde`` ``bw_method``). ``None`` (default) uses Scott's rule; smaller values give a tighter, less smoothed outline.
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

    # Prism-style look with sharp tips at the data extremes
    chart = ds.mark_violin(df, "group", "value", CATEGORIES, trim=True)

    # bare silhouette: remove the default outline
    chart = ds.mark_violin(df, "group", "value", CATEGORIES, stroke=None)

    # classic embedded boxplot with custom colors
    chart = ds.mark_violin(
        df, "group", "value", CATEGORIES,
        inner="box",
        boxplotSize=10,
        palette="#AAAAAA",
    )
```

## `mark_strip`

```python
def mark_strip(
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
) -> alt.LayerChart: ...
```

Build an Altair layer combining jittered or beeswarm points with a centre statistic.

With ``errorbars=True`` (default) the centre tick marks the group MEAN - the same
statistic the error bars are computed from, so the tick is always centred between
the caps. With ``errorbars=False`` the tick marks the median instead.

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
