"""A Lissajous figure - the parametric curve traced out and colored by phase."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=150, chartHeight=150, rampPalette="cosmos")

t = np.linspace(0, 2 * np.pi, 1400)
a, b, delta = 3, 4, np.pi / 2  # frequency ratio 3:4
df = pl.DataFrame({"x": np.sin(a * t + delta), "y": np.sin(b * t), "phase": t})

chart = (
    alt.Chart(df)
    .mark_point(size=6, filled=True)
    .encode(
        x=alt.X("x:Q", axis=None, scale=alt.Scale(domain=[-1.08, 1.08], nice=False)),
        y=alt.Y("y:Q", axis=None, scale=alt.Scale(domain=[-1.08, 1.08], nice=False)),
        color=alt.Color("phase:Q", legend=None),
        order="phase:Q",
    )
    .properties(view=alt.ViewConfig(stroke=None))
)
