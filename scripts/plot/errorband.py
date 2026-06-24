from pathlib import Path

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds
from dysonsphere.palettes import colors

rng = np.random.default_rng(42)

GROUPS = ["Control", "Drug A", "Drug B", "Drug C"]
TIMEPOINTS = np.linspace(0, 24, 13)
N_REPS = 20

slopes = {"Control": 0.0, "Drug A": 0.3, "Drug B": 0.18, "Drug C": -0.12}

rows = []
for group in GROUPS:
    for t in TIMEPOINTS:
        mean = 10 + slopes[group] * t
        for v in rng.normal(mean, 1.2, N_REPS):
            rows.append({"group": group, "time": float(t), "value": float(v)})

df = pl.DataFrame(rows)

palette = ds.palette("blues2", n=len(GROUPS), start=0)

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
        detail=alt.Detail("group:N"),
        color=alt.ColorValue(colors["blues"][0]),
    )
    .mark_errorband(extent="ci")
)
line = base.mark_line(strokeWidth=0.75).encode(y=alt.Y("mean(value):Q", title="Response (AU)"))

chart = band + line

out = str(Path(__file__).parent / "errorband")
ds.save(chart, out)
print(f"saved {out}")
