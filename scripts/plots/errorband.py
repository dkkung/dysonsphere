from pathlib import Path

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(42)

GROUPS = ["Control", "Group A", "Group B", "Group C"]
TIMEPOINTS = np.linspace(0, 24, 13)
N_REPS = 20

slopes = {"Control": 0.0, "Group A": 0.3, "Group B": 0.18, "Group C": -0.12}

rows = []
for group in GROUPS:
    for t in TIMEPOINTS:
        mean = 10 + slopes[group] * t
        for v in rng.normal(mean, 1.2, N_REPS):
            rows.append({"group": group, "time": float(t), "value": float(v)})

df = pl.DataFrame(rows)

palette = ds.palette("lavenders", n=len(GROUPS), start=0)

ds.theme(chartWidth=200, chartHeight=120, legend=True)

base = alt.Chart(df).encode(
    x=alt.X("time:Q", title="Time (h)"),
    color=alt.Color("group:N", sort=GROUPS, title=None, scale=alt.Scale(range=palette)),
)

band = (
    alt.Chart(df)
    .encode(
        x=alt.X("time:Q", title="Time (h)"),
        y=alt.Y("value:Q", title="Response (AU)"),
        color=alt.Color("group:N", sort=GROUPS, title=None, scale=alt.Scale(range=palette)),
    )
    .mark_errorband(extent="ci")
)
line = base.mark_line(strokeWidth=0.75).encode(y=alt.Y("mean(value):Q", title="Response (AU)"))

chart = band + line

out = str(Path(__file__).parent / "errorband")
ds.save(chart, out)
print(f"saved {out}")
