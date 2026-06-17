import numpy as np
import polars as pl

import theme

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

theme.options()

palette = theme.palette_range("lagoon_4_oklab", n=len(CATEGORIES))
chart = theme.mark_strip(df, "group", "value", CATEGORIES, palette=palette)

theme.save(chart, "strip")
print("saved strip")
