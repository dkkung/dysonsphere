import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(42)

df = pl.DataFrame(
    {
        "group": (
            ["Control"] * 200
            + ["Group A"] * 200
            + ["Group B"] * 200
            + ["Group C"] * 200
            + ["Group D"] * 200
            + ["Group E"] * 200
        ),
        "value": np.concatenate(
            [
                rng.normal(10, 2, 200),
                rng.normal(14, 2, 200),
                rng.normal(11, 2, 200),
                rng.normal(13, 2, 200),
                rng.normal(9, 2, 200),
                rng.normal(10, 2, 200),
            ]
        ),
    }
)

CATEGORIES = ["Control", "Group A", "Group B", "Group C", "Group D", "Group E"]

ds.theme(boxplotOutliers=True)

df = ds.add_beeswarm(
    df,
    yCol="value",
    groupBy=["group"],
)

palette = ds.palette("greys", start=0, step=1)

base = alt.Chart(df).encode(
    x=alt.X("group:N", sort=CATEGORIES),
    y=alt.Y("value:Q", title="Response (AU)"),
)

boxplot = base.mark_boxplot().encode()

points = base.mark_circle().encode(
    xOffset=alt.XOffset("beeswarm_x:Q"),
)

ann = ds.add_comparisons(
    df,
    "group",
    "value",
    pairs=[("Control", "Group A"), ("Control", "Group B"), ("Group A", "Group B")],
    test="mannwhitneyu",
    categories=CATEGORIES,
    bracketStyle="line",
)

shade = ds.add_shade(
    CATEGORIES,
    "group",
)

# chart = points + boxplot
chart = boxplot

# groups = {
#     "Condition A": [False, False, False, False, False, True],
#     "Condition B": [False, False, False, False, True, True],
#     "Condition C": [False, False, False, True, True, True],
# }

groups = {
    "Treatment 1": [False, False, "A", "A", "B", "B"],
    "Treatment 2": [False, True, False, True, False, True],
}

plot = ds.add_multilabel(
    chart,
    groups,
    categories=CATEGORIES,
    # rowStyles=["symbol", "symbol", "symbol"],
    showSampleSize=True,
    df=df,
    xCol="group",
    # categoryLabel=True,
)

ds.save(plot, "boxplot", format=["png"])
print("saved boxplot")
