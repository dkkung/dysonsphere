# Nonlinear axes

Read this when adding log or power scales, formatting their major labels, or placing minor ticks.
Use a scale transform that matches the data and state its meaning; nonlinear spacing can change how
visual distances read.

## Logarithmic scales

Set the chart channel's scale to `type="log"` and use the same base when adding minor ticks. For
base 10, `ds.add_log_ticks()` adds the conventional unlabeled 2×–9× positions within each decade.
For another integer base, it divides each major interval into `nMinor + 1` equal parts in log space.
The main chart's scale remains independent of the minor-tick axis.

`field` may be inferred from a simple `alt.Chart` encoding shorthand such as `"concentration:Q"`.
Pass it explicitly for a `LayerChart`, aggregate or expression encoding, or whenever inference is
uncertain. For `axis="both"`, use `xField` and `yField`. By default the exponent extent is derived
from the minimum and maximum data values; use `expMin` and `expMax` when the tick span should differ
from the observed data span.

`ds.log_label_expr()` returns a Vega `labelExpr` for `alt.Axis(labelExpr=...)`. Its default
`notation="power"` supports any integer base. The `"scientific"`, `"e"`, and `"si"` formats are
base-10 only; scientific notation assumes major ticks are exact powers of ten.
Major tick `values` remain the actual data values, not their logarithms.

```python
# example: nonlinear
import altair as alt
import polars as pl

import dysonsphere as ds

data = pl.DataFrame({
    "concentration": [1, 2, 5, 10, 20, 50, 100],
    "response": [1.1, 1.4, 1.8, 2.3, 2.8, 3.4, 4.0],
})
ds.theme(width=180, height=130)
chart = alt.Chart(data).mark_line(point=True).encode(
    x=alt.X(
        "concentration:Q",
        title="Concentration (a.u.)",
        scale=alt.Scale(type="log", base=10),
        axis=alt.Axis(values=[1, 10, 100], labelExpr=ds.log_label_expr()),
    ),
    y=alt.Y("response:Q", title="Response (a.u.)"),
)
chart = ds.add_log_ticks(
    chart,
    data,
    "concentration",
    axis="x",
    base=10,
    expMin=0,
    expMax=2,
)
ds.save(chart, "skill_nonlinear")
```

## Power and square-root scales

`ds.add_pow_ticks()` adds unlabeled minor ticks evenly spaced in transformed visual space. Configure
the main channel with a matching power scale and exponent. Supply `majorValues` in the same data-value
order as the axis's `values`; they cannot be inferred. The default exponent `0.5` is a square-root
scale and the default `nMinor=4` places four minor ticks between each pair of major ticks. For both
axes, use `axis="both"`, `xField`, `yField`, `xMajorValues`, and `yMajorValues`.

Use `ds.save()` or `ds.show()` to render. Inspect the output to check major labels, scale, and minor
ticks; a correctly configured specification alone does not confirm their final appearance.
