import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(42)

CATEGORIES = ["Control", "Drug A", "Drug B", "Drug C", "Drug D", "Drug E"]

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

ds.theme(angledX=True)
palette = ds.palette("lavenders", n=len(CATEGORIES))

chart = ds.mark_violin(df, "group", "value", CATEGORIES, palette=palette)

ds.save(chart, "violin")
print("saved violin")
