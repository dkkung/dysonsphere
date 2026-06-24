import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(42)

GROUPS = ["Control", "Drug A", "Drug B", "Drug C", "Drug D"]
TYPES = ["Type 1", "Type 2"]

df = pl.DataFrame(
    {
        "group": GROUPS * 2,
        "type": ["Type 1"] * 5 + ["Type 2"] * 5,
        "value": rng.integers(20, 80, 10).tolist(),
    }
)

palette = ds.palette("greys", n=2)

ds.theme()

chart = (
    alt.Chart(df)
    .mark_bar()
    .encode(
        x=alt.X(
            "group:N",
            sort=GROUPS,
            title="Treatment",
            axis=alt.Axis(labelAngle=-45, labelAlign="right"),
        ),
        y=alt.Y("value:Q", title="Percentage", stack="normalize"),
        color=alt.Color(
            "type:N",
            sort=TYPES,
            scale=alt.Scale(range=palette),
            title=None,
        ),
    )
)

ds.save(chart, "stacked_bar_chart")
print("saved stacked_bar_chart")
