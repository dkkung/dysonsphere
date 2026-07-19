import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=200, chartHeight=160)

rng = np.random.default_rng(21)
conds = ["vehicle", "low dose", "high dose"]
data = {
    "vehicle": rng.normal(52, 8, 90),
    "low dose": np.concatenate([rng.normal(46, 7, 70), rng.normal(60, 5, 20)]),
    "high dose": rng.normal(34, 9, 90),
}
rows = []
for c in conds:
    for v in data[c]:
        rows.append({"condition": c, "response": float(v)})
df = pl.DataFrame(rows)

# the cloud: KDE violin + embedded boxplot
violin = ds.mark_violin(df, "condition", "response", conds, yTitle="response (a.u.)")

# the rain: jittered raw points on a hidden x-axis, so only the violin draws the axis
jit = rng.normal(0, 0.12, len(df))
rain_df = df.with_columns(pl.Series("jx", jit))
rain = (
    alt.Chart(rain_df)
    .mark_circle(size=7, opacity=0.5, stroke="black", strokeWidth=0.2)
    .encode(
        x=alt.X("condition:N", sort=conds, axis=None),
        xOffset=alt.XOffset("jx:Q", scale=alt.Scale(domain=[-0.5, 0.5])),
        y=alt.Y("response:Q"),
        color=alt.Color("condition:N", sort=conds, scale=alt.Scale(domain=conds), legend=None),
    )
)

chart = violin + rain
