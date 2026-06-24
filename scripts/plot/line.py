import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(42)

TIMEPOINTS = np.linspace(0, 24, 50)
GROUPS = ["Control", "Drug A", "Drug B", "Drug C"]

rows = []
for group in GROUPS:
    slope = {"Control": 0.0, "Drug A": 0.25, "Drug B": 0.15, "Drug C": -0.1}[group]
    for t in TIMEPOINTS:
        mean = 10 + slope * t + rng.normal(0, 0.3)
        rows.append({"group": group, "time": float(t), "value": float(mean)})

df = pl.DataFrame(rows)

ds.theme()

chart = (
    alt.Chart(df)
    .mark_line(strokeWidth=0.75)
    .encode(
        x=alt.X("time:Q", title="Time (h)"),
        y=alt.Y("value:Q", title="Response (AU)"),
        color=alt.Color("group:N", sort=GROUPS, title=None),
    )
)

ds.save(chart, "line")
print("saved line")
