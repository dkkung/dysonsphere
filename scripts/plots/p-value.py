import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(42)

df = pl.DataFrame(
    {
        "group": ["Control"] * 30 + ["Group A"] * 30 + ["Group B"] * 30,
        "value": np.concatenate(
            [
                rng.normal(10, 2, 30),
                rng.normal(14, 2, 30),
                rng.normal(11, 2, 30),
            ]
        ),
    }
)

CATEGORIES = ["Control", "Group A", "Group B"]

ds.theme(markSize=15)

chart = (
    alt.Chart(df)
    .mark_point()
    .encode(
        x=alt.X("group:N", sort=CATEGORIES, title="Treatment"),
        y=alt.Y("value:Q", title="Response (AU)"),
        color=alt.Color("group:N", sort=CATEGORIES, legend=None),
    )
)

ann = ds.add_statistics(
    df,
    "group",
    "value",
    pairs=[("Control", "Group A"), ("Control", "Group B"), ("Group A", "Group B")],
    test="mannwhitneyu",
    categories=CATEGORIES,
    yPositions=[21, 5, 24],
    reverse=[("Control", "Group B")],
)

ds.save(chart + ann, "p-value")
print("saved p-value")
