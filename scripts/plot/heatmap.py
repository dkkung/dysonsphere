import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(42)

xs, ys = [], []
for cx, cy, s, n in [(2.5, 7.5, 0.6, 130), (7.5, 2.5, 0.7, 150), (5.0, 5.5, 1.0, 110)]:
    xs.append(rng.normal(cx, s, n))
    ys.append(rng.normal(cy, s, n))

df = pl.DataFrame(
    {
        "x": np.concatenate(xs).tolist(),
        "y": np.concatenate(ys).tolist(),
    }
)

ds.theme()

chart = (
    alt.Chart(df)
    .mark_rect()
    .encode(
        x=alt.X("x:Q", bin=alt.Bin(maxbins=10), title=None, axis=alt.Axis(format=".0f")),
        y=alt.Y("y:Q", bin=alt.Bin(maxbins=10), title=None, axis=alt.Axis(format=".0f")),
        color=alt.Color("count()", title=None),
    )
)

ds.save(chart, "heatmap")
print("saved heatmap")
