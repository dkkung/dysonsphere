import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(42)

CATEGORIES = ["Control", "Group A", "Group B", "Group C", "Group D"]

df = pl.DataFrame(
    {
        "group": (["Control"] * 100 + ["Group A"] * 100 + ["Group B"] * 100 + ["Group C"] * 100 + ["Group D"] * 100),
        "value": np.concatenate(
            [
                rng.normal(10, 2, 100),
                rng.normal(14, 2, 100),
                rng.normal(11, 2, 100),
                rng.normal(13, 2, 100),
                rng.normal(9, 2, 100),
            ]
        ),
    }
)

ds.theme(xLabelAngle=-45)

df = ds.add_beeswarm(df, yCol="value", groupBy=["group"])

summary = df.group_by("group").agg(
    [
        pl.col("value").mean().alias("__mean"),
        (pl.col("value").std() / pl.col("value").count().sqrt()).alias("__sem"),
    ]
)

x = alt.X("group:N", sort=CATEGORIES, title=None)

points = (
    alt.Chart(df)
    .mark_circle()
    .encode(
        x=x,
        y=alt.Y("value:Q", title="Response (AU)"),
        xOffset=alt.XOffset("beeswarm_x:Q"),
        color=alt.Color("group:N"),
    )
)

errorbars = (
    alt.Chart(summary)
    .mark_errorbar()
    .encode(
        x=x,
        y=alt.Y("__mean:Q", title="Response (AU)"),
        yError=alt.YError("__sem:Q"),
    )
)

chart = points + errorbars

ds.save(chart, "beeswarm")
print("saved beeswarm")
