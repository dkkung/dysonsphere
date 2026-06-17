import altair as alt
import numpy as np
import polars as pl

import theme

rng = np.random.default_rng(42)

TIMEPOINTS = np.linspace(0, 24, 100)
GROUPS = ["Type A", "Type B", "Type C", "Type D"]

rows = []
for t in TIMEPOINTS:
    for group, base in zip(GROUPS, [0.4, 0.3, 0.2, 0.1]):
        rows.append(
            {
                "time": float(t),
                "group": group,
                "value": max(0.0, base + rng.normal(0, 0.02)),
            }
        )

df = pl.DataFrame(rows)

palette = theme.palette_range("bluelagoon", n=len(GROUPS))

theme.options()

chart = (
    alt.Chart(df)
    .mark_area()
    .encode(
        x=alt.X("time:Q", title="Time (h)"),
        y=alt.Y(
            "value:Q",
            title="Proportion",
            stack="normalize",
            scale=alt.Scale(domain=[0, 1]),
        ),
        color=alt.Color("group:N", sort=GROUPS, scale=alt.Scale(range=palette), title=None),
        order=alt.Order("group:N", sort="descending"),
    )
)

theme.save(chart, "area_chart")
print("saved area_chart")
