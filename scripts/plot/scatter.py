import altair as alt
import numpy as np
import polars as pl

import theme

rng = np.random.default_rng(42)

x = np.linspace(0, 5, 200)
y = np.exp(x) + rng.normal(0, 2, 200)

mask = y >= 0
x, y = x[mask], y[mask]

df = pl.DataFrame({"x": x, "y": y})

# palette = theme.palette_range("mpl_YlGnBu")
# palette = theme.palette_range("RdPu_sat", reverse=False)
palette = theme.palette_range("bluegrotto_oklab")

theme.options()

chart = (
    alt.Chart(df)
    .mark_point()
    .encode(
        x=alt.X("x:Q", title="X"),
        y=alt.Y("y:Q", title="Y"),
        color=alt.Color(
            "y:Q",
            title=None,
            scale=alt.Scale(range=palette),
        ),
    )
)

theme.save(chart, "scatter", ppi=1200)
print("saved scatter")
