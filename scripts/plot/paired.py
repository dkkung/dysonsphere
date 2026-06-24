import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(42)

CONDITIONS = ["Baseline", "Week 12"]
GROUPS = ["Placebo", "Low Dose", "High Dose"]
N_PER_GROUP = 10

rows = []
for group in GROUPS:
    effect = {"Placebo": 0.0, "Low Dose": -15.0, "High Dose": -30.0}[group]
    for i in range(N_PER_GROUP):
        baseline = float(rng.normal(100, 15))
        followup = float(baseline + effect + rng.normal(0, 8))
        subject = f"{group[0]}{i + 1:02d}"
        rows.append(
            {"subject": subject, "group": group, "condition": "Baseline", "value": baseline}
        )
        rows.append({"subject": subject, "group": group, "condition": "Week 12", "value": followup})

df = pl.DataFrame(rows)

palette = ds.palette("mpl_YlGnBu", n=len(GROUPS), start=2)

ds.theme()

x = alt.X("condition:N", sort=CONDITIONS, title=None)
color = alt.Color("group:N", sort=GROUPS, scale=alt.Scale(range=palette), title=None)

lines = (
    alt.Chart(df)
    .mark_line()
    .encode(
        x=x,
        y=alt.Y("value:Q", title="Biomarker (AU)"),
        detail=alt.Detail("subject:N"),
        color=color,
    )
)

points = (
    alt.Chart(df)
    .mark_circle()
    .encode(
        x=x,
        y=alt.Y("value:Q", title="Biomarker (AU)"),
        color=color,
    )
)

chart = alt.layer(lines, points)

ds.save(chart, "paired")
print("saved paired")
