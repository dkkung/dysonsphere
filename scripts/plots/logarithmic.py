import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(42)

TIMEPOINTS = [1, 3, 5, 7, 10]
GROUPS = ["Group A", "Group B", "Group C"]
STARTS = {"Group A": 1.5e5, "Group B": 1.4e5, "Group C": 1.6e5}
SLOPES = {"Group A": 2.8, "Group B": -0.8, "Group C": 0.1}

rows = []
for group in GROUPS:
    for t in TIMEPOINTS:
        value = STARTS[group] * np.exp(SLOPES[group] * (t - 1) / 9) * rng.lognormal(0, 0.15)
        rows.append({"group": group, "time": float(t), "value": float(value)})

df = pl.DataFrame(rows)

import math

y_min = float(df["value"].min())  # ty: ignore[invalid-argument-type]
y_max = float(df["value"].max())  # ty: ignore[invalid-argument-type]
exp_min = int(math.floor(math.log10(y_min)))
exp_max = int(math.ceil(math.log10(y_max)))
major_values = [10**e for e in range(exp_min, exp_max + 1)]

ds.theme()

chart = (
    alt.Chart(df)
    .mark_line(point=True)
    .encode(
        x=alt.X("time:Q", title="Time (days)"),
        y=alt.Y(
            "value:Q",
            title="Cumulative cell number",
            scale=alt.Scale(type="log", base=10),
            axis=alt.Axis(values=major_values, labelExpr=ds.log_label_expr()),
        ),
        color=alt.Color("group:N", sort=GROUPS, title=None),
    )
)

chart = ds.add_log_ticks(chart, df, axis="y", field="value")

ds.save(chart, "logarithmic")
print("saved logarithmic")
