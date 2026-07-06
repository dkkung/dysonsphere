import numpy as np
import polars as pl

import dysonsphere as ds

# ds.biology comes from the separately-installed `dysonsphere-biology` extension,
# resolved lazily through the entry-point discovery system (pip install dysonsphere-biology).

rng = np.random.default_rng(7)
n = 800

# Simulate a differential-expression result: mostly null, with a tail of real hits whose
# larger fold changes come with smaller p-values.
log2fc = rng.normal(0, 1.0, n)
hits = rng.choice(n, 40, replace=False)
log2fc[hits] += rng.choice([-1, 1], 40) * rng.uniform(1.5, 4.0, 40)
base = rng.uniform(0.001, 1.0, n)
pvalue = np.where(np.abs(log2fc) > 1.5, base**3, base)

df = pl.DataFrame({"gene": [f"G{i}" for i in range(n)], "log2fc": log2fc, "pvalue": pvalue})

ds.theme(chartWidth=150, chartHeight=110)

# label=8 auto-selects the 8 most significant genes (ranked by |log2fc| x -log10 p).
chart = ds.biology.volcano(df, geneCol="gene", label=8, legend=False)
