import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(42)

CATEGORIES = ["Control", "Group A", "Group B", "Group C", "Group D", "Group E"]

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

ds.theme(xLabelAngle=-45)
palette = ds.palette("lavenders", n=len(CATEGORIES))

chart = ds.mark_violin(df, "group", "value", CATEGORIES, palette=palette)

ds.save(chart, "violin")
print("saved violin")
