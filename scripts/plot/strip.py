import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(42)

CATEGORIES = ["Control", "Drug A", "Drug B", "Drug C", "Drug D"]

df = pl.DataFrame(
    {
        "group": (
            ["Control"] * 50 + ["Drug A"] * 50 + ["Drug B"] * 50 + ["Drug C"] * 50 + ["Drug D"] * 50
        ),
        "value": np.concatenate(
            [
                rng.normal(10, 2, 50),
                rng.normal(14, 2, 50),
                rng.normal(11, 2, 50),
                rng.normal(13, 2, 50),
                rng.normal(9, 2, 50),
            ]
        ),
    }
)

ds.theme()

chart = ds.mark_strip(df, "group", "value", CATEGORIES, spread=2)

ds.save(chart, "strip")
print("saved strip")
