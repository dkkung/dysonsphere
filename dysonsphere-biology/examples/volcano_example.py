"""Volcano plot example -> examples/volcano_example.png.

Run: uv run python dysonsphere-biology/examples/volcano_example.py
"""

from pathlib import Path

import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(7)
n = 800

# Simulate differential-expression results: mostly null, with a tail of real hits whose larger
# fold changes come with smaller p-values.
log2fc = rng.normal(0, 1.0, n)
hits = rng.choice(n, 40, replace=False)
log2fc[hits] += rng.choice([-1, 1], 40) * rng.uniform(1.5, 4.0, 40)
base = rng.uniform(0.001, 1.0, n)
pvalue = np.where(np.abs(log2fc) > 1.5, base**3, base)

df = pl.DataFrame({"gene": [f"G{i}" for i in range(n)], "log2fc": log2fc, "pvalue": pvalue})

ds.theme(chartWidth=125, chartHeight=80)

out = Path(__file__).parent / "volcano_example"
ds.save(
    lambda: ds.biology.volcano(df, geneCol="gene", label=6),
    str(out),
    format=["png"],
    background="light",
)
print(f"wrote {out}.png")
