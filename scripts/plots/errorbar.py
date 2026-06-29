"""
Error bar demo — jittered points with mean ± SEM error bars.

Groups vary in spread and sample size to produce a range of error bar lengths.

Usage (from project root):
    uv run python scripts/plots/errorbar.py
"""

from pathlib import Path

import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(42)

GROUPS = ["A", "B", "C", "D", "E"]
means = [4.0, 6.5, 5.2, 7.8, 3.5]
sds = [0.4, 1.2, 0.8, 1.6, 0.3]
ns = [30, 12, 20, 8, 40]

rows = []
for group, mean, sd, n in zip(GROUPS, means, sds, ns):
    for v in rng.normal(mean, sd, n):
        rows.append({"group": group, "value": float(v)})

df = pl.DataFrame(rows)

ds.theme(palette="lavenders", chartWidth=75, chartHeight=75)

chart = ds.mark_strip(df, "group", "value", GROUPS, yTitle="Response (AU)")

ds.save(chart, str(Path(__file__).parent / "errorbar"))
print("saved errorbar")
