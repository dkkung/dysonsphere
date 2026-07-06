---
title: "Nonlinear axes"
description: "Minor ticks and typeset labels for log and power axes."
sidebar:
  order: 8
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

## `log_label_expr`

```python
log_label_expr(base: int = 10, notation: str = 'power') -> str
```

Return a Vega ``labelExpr`` string for base-N log-scale axis labels.

Four notations are available:

- ``"power"`` (default): e.g. ``10⁴``, ``2⁻³``, ``2²⁰``.
  Works for any integer base.
- ``"scientific"``: e.g. ``1×10⁴``, ``1×10⁻³``.
  Base-10 only. Assumes tick values are exact powers of 10 so the
  mantissa is always ``1``; raises ``ValueError`` for other bases.
- ``"e"``: e.g. ``1e+4``, ``1e-3``.
  Base-10 only. Uses Vega's ``format(datum.value, '.0e')`` internally.
  Best suited for axes whose ``values=`` are exact powers of 10.
- ``"si"``: e.g. ``10k``, ``1M``, ``100µ``.
  Base-10 only. Uses Vega's ``format(datum.value, '~s')`` internally;
  trims insignificant trailing zeros automatically.

Supports exponents up to ±99 for ``"power"`` and ``"scientific"``.
Pass the return value directly to ``alt.Axis(labelExpr=...)``.

**Parameters**

- **`base`** (`int`) - Logarithm base. Defaults to ``10``.
- **`notation`** (`str`) - ``"power"`` (default), ``"scientific"``, ``"e"``, or ``"si"``. All notations except ``"power"`` require ``base=10``.

**Examples**

```python
::

    # power notation — base-10 y-axis: 10⁴, 10⁵, 10⁶, …
    axis=alt.Axis(
        values=[10**e for e in range(4, 8)],
        labelExpr=ds.log_label_expr(),
    )

    # power notation — log2 x-axis: 2⁰, 2¹, …, 2²⁰
    axis=alt.Axis(
        values=[2**e for e in range(0, 21)],
        labelExpr=ds.log_label_expr(base=2),
    )

    # scientific notation — base-10 y-axis: 1×10⁴, 1×10⁵, 1×10⁶, …
    axis=alt.Axis(
        values=[10**e for e in range(4, 8)],
        labelExpr=ds.log_label_expr(notation="scientific"),
    )

    # e-notation — base-10 y-axis: 1e+4, 1e+5, 1e+6, …
    axis=alt.Axis(
        values=[10**e for e in range(4, 8)],
        labelExpr=ds.log_label_expr(notation="e"),
    )

    # SI prefix notation — base-10 y-axis: 10k, 100k, 1M, …
    axis=alt.Axis(
        values=[10**e for e in range(4, 8)],
        labelExpr=ds.log_label_expr(notation="si"),
    )
```

## `add_log_ticks`

```python
add_log_ticks(
    chart: alt.Chart | alt.LayerChart,
    df,
    field: str | None = None,
    *,
    axis: str = 'y',
    base: int = 10,
    nMinor: int = 1,
    expMin: int | None = None,
    expMax: int | None = None,
    xField: str | None = None,
    yField: str | None = None,
    xExpMin: int | None = None,
    xExpMax: int | None = None,
    yExpMin: int | None = None,
    yExpMax: int | None = None,
    minorTickSize: float | None = None,
) -> alt.LayerChart
```

Add unlabeled minor ticks to a log-scale axis.

Wraps ``chart`` in a layer carrying a second axis of minor ticks.
The main chart's scale domain is unaffected.

For ``base=10`` the minor ticks are placed at the 2×–9× integer
multiples within each decade — the conventional scientific log tick
pattern. For other bases (e.g. ``base=2``) ticks are placed at
``nMinor`` equally-spaced positions (in log space) per interval,
defaulting to one tick at the geometric midpoint per octave.

Works with ``alt.Chart``, ``alt.LayerChart``, and any chart type
composable with ``alt.layer()``. Also works correctly in ``hconcat``
and ``vconcat`` layouts.

.. note::
    Minor tick positions are exact at render time (the theme config
    disables Vega's integer tick rounding), so they are correct in
    any renderer. Still prefer ``ds.save()`` over ``chart.save()``
    for the other SVG corrections (grid span, superscript labels)
    and the embedded metadata.

**Parameters**

- **`chart`** (`alt.Chart | alt.LayerChart`) - The chart to add minor ticks to.
- **`df`** - DataFrame (Polars or Pandas) used for the main chart.
- **`field`** (`str | None`) - Column name of the log-scale field. When ``axis`` is ``'x'`` or ``'y'`` and this is ``None``, it is inferred from the chart's matching encoding shorthand (``chart.encoding.x`` / ``.y``); pass it explicitly for a ``LayerChart`` (no top-level encoding) or an aggregate/expression encoding, where inference is not possible. Omit when ``axis='both'`` and use ``xField`` / ``yField`` instead.
- **`axis`** (`str`) - ``'x'``, ``'y'`` (default), or ``'both'``. When ``'both'``, ``xField`` and ``yField`` must be provided.
- **`base`** (`int`) - Logarithm base matching the axis scale. Defaults to ``10``. Use ``2`` for log2 axes (e.g. volcano plots, fold-change axes). Any integer ≥ 2 is accepted.
- **`nMinor`** (`int`) - Number of minor ticks per major interval for non-base-10 scales. Ignored when ``base=10`` (which always uses the 2×–9× pattern). Defaults to ``1`` (one tick at the geometric midpoint per interval). Use ``3`` for quarter-interval ticks.
- **`expMin`** (`int | None`) - Lowest exponent (in the given ``base``) for the single-axis case. Auto-derived from ``df[field].min()`` when ``None``.
- **`expMax`** (`int | None`) - Highest exponent. Auto-derived from ``df[field].max()`` when ``None``.
- **`xField`** (`str | None`) - Column name for the x log-scale field (``axis='both'`` only).
- **`yField`** (`str | None`) - Column name for the y log-scale field (``axis='both'`` only).
- **`xExpMin`** (`int | None`) - Exponent overrides for the x axis (``axis='both'`` only).
- **`xExpMax`** (`int | None`) - Exponent overrides for the x axis (``axis='both'`` only).
- **`yExpMin`** (`int | None`) - Exponent overrides for the y axis (``axis='both'`` only).
- **`yExpMax`** (`int | None`) - Exponent overrides for the y axis (``axis='both'`` only).
- **`minorTickSize`** (`float | None`) - Length of minor ticks in pixels. Defaults to half the active theme's ``tickSize`` (``tickSize / 2``; typically ``1.5`` when the default ``tickSize=3`` is in effect).

**Examples**

```python
::

    # log10 y-axis — exp range auto-derived
    chart = ds.add_log_ticks(chart, df, "value")

    # log2 x-axis (e.g. fold-change on a volcano plot)
    chart = ds.add_log_ticks(chart, df, "fc", axis="x", base=2)

    # log2 with 3 minor ticks per octave
    chart = ds.add_log_ticks(chart, df, "fc", axis="x", base=2, nMinor=3)

    # both axes log-scaled
    chart = ds.add_log_ticks(
        chart, df, axis="both", xField="fc", yField="pvalue"
    )
```

## `add_pow_ticks`

```python
add_pow_ticks(
    chart: alt.Chart | alt.LayerChart,
    df,
    field: str | None = None,
    *,
    axis: str = 'y',
    exponent: float = 0.5,
    majorValues: list[float] | None = None,
    nMinor: int = 4,
    minorTickSize: float | None = None,
    xField: str | None = None,
    yField: str | None = None,
    xMajorValues: list[float] | None = None,
    yMajorValues: list[float] | None = None,
) -> alt.LayerChart
```

Add unlabeled minor ticks to a power- or sqrt-scale axis.

Wraps ``chart`` in a layer carrying a second axis of minor ticks.
The main chart's scale domain is unaffected.

Minor ticks are placed at positions that are equally spaced in the
power-transformed (visual) space — i.e. they appear visually uniform
on screen regardless of where the major ticks fall in data space.
The formula for minor tick ``k`` of ``nMinor`` between major ticks
``a`` and ``b`` is::

    val = (a**exp + k / (nMinor + 1) * (b**exp - a**exp)) ** (1 / exp)

``majorValues`` must match the values passed to the main chart's
``axis.values`` — the minor layer uses them to infer interval
boundaries and to set the independent scale domain.

Use ``exponent=0.5`` (the default) for a square-root axis
(equivalent to Vega-Lite's ``type="sqrt"``). For a quadratic axis
use ``exponent=2``, and so on.

Works with ``alt.Chart``, ``alt.LayerChart``, and any chart type
composable with ``alt.layer()``. Also works correctly in ``hconcat``
and ``vconcat`` layouts.

.. note::
    Minor tick positions are exact at render time (the theme config
    disables Vega's integer tick rounding), so they are correct in
    any renderer. Still prefer ``ds.save()`` over ``chart.save()``
    for the other SVG corrections (grid span, superscript labels)
    and the embedded metadata.

**Parameters**

- **`chart`** (`alt.Chart | alt.LayerChart`) - The chart to add minor ticks to.
- **`df`** - DataFrame (Polars or Pandas) used for the main chart.
- **`field`** (`str | None`) - Column name of the power-scaled field. Required when ``axis`` is ``'x'`` or ``'y'``; omit when ``axis='both'`` and use ``xField`` / ``yField`` instead.
- **`axis`** (`str`) - ``'x'``, ``'y'`` (default), or ``'both'``. When ``'both'``, ``xField``, ``yField``, ``xMajorValues``, and ``yMajorValues`` must all be provided.
- **`exponent`** (`float`) - Power exponent matching the axis scale. Defaults to ``0.5`` (square root). Use ``2`` for a quadratic axis, etc. Must be non-zero.
- **`majorValues`** (`list[float] | None`) - Ordered list of major tick data values for the single-axis case. Must match the ``values=`` passed to the main chart's ``alt.Axis``. Required — cannot be auto-derived.
- **`nMinor`** (`int`) - Number of minor ticks between each pair of major ticks. Defaults to ``4`` (divides each interval into five equal visual segments).
- **`minorTickSize`** (`float | None`) - Length of minor ticks in pixels. Defaults to half the active theme's ``tickSize`` (``tickSize / 2``; typically ``1.5`` when the default ``tickSize=3`` is in effect).
- **`xField`** (`str | None`) - Column name for the x power-scaled field (``axis='both'`` only).
- **`yField`** (`str | None`) - Column name for the y power-scaled field (``axis='both'`` only).
- **`xMajorValues`** (`list[float] | None`) - Major tick values for the x axis (``axis='both'`` only).
- **`yMajorValues`** (`list[float] | None`) - Major tick values for the y axis (``axis='both'`` only).

**Examples**

```python
::

    # sqrt y-axis (exponent=0.5 is the default)
    major_values = [0, 1, 4, 9, 16, 25]
    chart = (
        alt.Chart(df)
        .mark_point()
        .encode(
            y=alt.Y("value:Q",
                scale=alt.Scale(type="pow", exponent=0.5),
                axis=alt.Axis(values=major_values),
            )
        )
    )
    chart = ds.add_pow_ticks(chart, df, "value", majorValues=major_values)

    # quadratic x-axis
    chart = ds.add_pow_ticks(
        chart, df, "x_val", axis="x", exponent=2,
        majorValues=[0, 1, 2, 3, 4, 5],
    )

    # both axes power-scaled (same exponent)
    chart = ds.add_pow_ticks(
        chart, df, axis="both",
        xField="x_val", yField="value",
        xMajorValues=[0, 1, 4, 9], yMajorValues=[0, 1, 4, 9, 16, 25],
    )
```
