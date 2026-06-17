import altair as alt
import numpy as np
import polars as pl

import theme

rng = np.random.default_rng(42)

GROUPS = ["Control", "Drug A", "Drug B"]
params = {"Control": (10, 2), "Drug A": (13, 1.5), "Drug B": (7, 3)}
N = 150

rows = []
for group in GROUPS:
    mean, sd = params[group]
    for v in rng.normal(mean, sd, N):
        rows.append({"group": group, "value": float(v)})

df = pl.DataFrame(rows)

palette = theme.palette_range("bluergrotto", n=len(GROUPS))

theme.options()

chart = (
    alt.Chart(df)
    .mark_bar(binSpacing=0)
    .encode(
        x=alt.X(
            "value:Q",
            title="Expression (log₂)",
            bin=alt.Bin(maxbins=25),
            axis=alt.Axis(tickMinStep=3),
        ),
        y=alt.Y("count()", title="Count"),
        color=alt.Color("group:N", sort=GROUPS, scale=alt.Scale(range=palette), title=None),
    )
)

theme.save(chart, "histogram")
print("saved histogram")
