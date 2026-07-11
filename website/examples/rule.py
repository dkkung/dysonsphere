import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme()

rng = np.random.default_rng(1)
batches = ["batch 1", "batch 2", "batch 3"]
df = pl.DataFrame(
    {
        "batch": [b for b in batches for _ in range(24)],
        "impurity": np.concatenate([rng.normal(m, s, 24) for m, s in ((12, 1.5), (14, 1.5), (30, 2.0))]),
    }
)

strip = ds.mark_strip(df, "batch", "impurity", batches, yTitle="Impurity (ppm)")

# A labeled horizontal reference line; inherits the theme's dashed-rule style.
chart = strip + ds.add_rule(22, label="release limit")
