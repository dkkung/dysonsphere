"""Group comparison - a beeswarm strip with pairwise Mann-Whitney brackets from add_comparisons."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=150, chartHeight=150)

rng = np.random.default_rng(9)
groups = {"vehicle": (4.0, 0.8), "low dose": (4.7, 0.9), "high dose": (6.3, 1.0)}
rows = [{"group": g, "expr": float(v)} for g, (m, s) in groups.items() for v in rng.normal(m, s, 22)]
df = pl.DataFrame(rows)

strip = ds.mark_strip(df, "group", "expr", list(groups), scatter="beeswarm", yTitle="expression (a.u.)")
brackets = ds.add_comparisons(
    df,
    "group",
    "expr",
    pairs=[("vehicle", "low dose"), ("low dose", "high dose"), ("vehicle", "high dose")],
    test="mannwhitneyu",
    labelStyle="asterisks",
)

chart = strip + brackets
