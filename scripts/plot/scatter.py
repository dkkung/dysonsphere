import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(42)

x = np.linspace(0, 5, 200)
y = np.exp(x) + rng.normal(0, 2, 200)

mask = y >= 0
x, y = x[mask], y[mask]

df = pl.DataFrame({"x": x, "y": y})

ds.theme()

chart = (
    alt.Chart(df)
    .mark_point()
    .encode(
        x=alt.X("x:Q", title="X"),
        y=alt.Y("y:Q", title="Y"),
        color=alt.Color("y:Q", title=None),
    )
)

ds.save(chart, "scatter", ppi=1200)
print("saved scatter")
