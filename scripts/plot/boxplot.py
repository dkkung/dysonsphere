import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(42)

df = pl.DataFrame(
    {
        "group": (
            ["Control"] * 200
            + ["Drug A"] * 200
            + ["Drug B"] * 200
            + ["Drug C"] * 200
            + ["Drug D"] * 200
            + ["Drug E"] * 200
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

CATEGORIES = ["Control", "Drug A", "Drug B", "Drug C", "Drug D", "Drug E"]

ds.theme()

df = ds.add_beeswarm(
    df,
    y_col="value",
    group_by=["group"],
)

# palette = ds.palette("greys", n=1, start=2)
# palette = ds.palette("mpl_viridis", n=len(CATEGORIES), start=4)
palette = ds.palette("blues", n=6, start=0)

base = alt.Chart(df).encode(
    x=alt.X(
        "group:N",
        sort=CATEGORIES,
        # title="Treatment",
        axis=alt.Axis(labelAngle=-45, labelAlign="right"),
    ),
    y=alt.Y("value:Q", title="Response (AU)"),
)

boxplot = base.mark_boxplot().encode(
    color=alt.Color("group:N", sort=CATEGORIES, scale=alt.Scale(range=palette), legend=None),
)

points = base.mark_circle(size=5).encode(
    xOffset=alt.XOffset("beeswarm_x:Q"),
)

ann = ds.add_pvalue(
    df,
    "group",
    "value",
    pairs=[("Control", "Drug A"), ("Control", "Drug B")],
    test="mannwhitneyu",
    categories=CATEGORIES,
    y_positions=[21, 25],
)

chart = points + boxplot + ann

test = {
    "Control": [False, False, False, False, False, False],
    "Condition A": [True, True, False, False, True, True],
    "Condition B": [True, True, True, True, True, True],
}

plot = ds.add_multilabel(chart, test, categories=CATEGORIES, style="symbol", palette=palette)

ds.save(plot, "boxplot")
print("saved boxplot")
