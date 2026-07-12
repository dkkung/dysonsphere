"""GWAS Manhattan plot - alternating chromosome colors, a significance rule, labeled hits."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

alt.data_transformers.enable("default", max_rows=None)
ds.theme(chartWidth=260, chartHeight=115)

rng = np.random.default_rng(8)
chrom_sizes = [249, 243, 198, 191, 181, 171, 159, 145, 138, 134, 135, 133,
               114, 107, 102, 90, 83, 80, 59, 64, 48, 51]
hits = {2: (160, "SORT1"), 6: (32, "HLA-B"), 9: (22, "CDKN2A"), 16: (53, "FTO")}

x, y, parity, tick_pos = [], [], [], []
hit_rows = []
offset = 0.0
for c, size in enumerate(chrom_sizes, start=1):
    n = max(50, size // 3)
    pos = np.sort(rng.uniform(0, size, n))
    logp = rng.exponential(0.5, n)
    if c in hits:
        hp, name = hits[c]
        d = np.abs(pos - hp)
        logp += (8.0 + rng.uniform(0, 2.5)) * np.exp(-(d**2) / (2 * 3.5**2))
        hit_rows.append({"pos": offset + hp, "logp": float(logp.max()), "gene": name})
    gx = offset + pos
    x += list(gx)
    y += list(logp)
    parity += [str(c % 2)] * n
    tick_pos.append(offset + size / 2)
    offset += size

df = pl.DataFrame({"pos": x, "logp": y, "parity": parity})

points = (
    alt.Chart(df)
    .mark_circle(size=7, opacity=0.85)
    .encode(
        x=alt.X("pos:Q", title="chromosome", axis=alt.Axis(labels=False, ticks=False)),
        y=alt.Y("logp:Q", title="−log₁₀ p", scale=alt.Scale(domain=[0, 13])),
        color=alt.Color("parity:N", scale=alt.Scale(range=["#3A68BB", "#28CDC5"]), legend=None),
    )
)

sig = ds.add_rule(7.3, label="P = 5×10⁻⁸", strokeDash=True, labelAlign="right")

hits_df = pl.DataFrame(hit_rows)
gene_labels = ds.add_labels(
    hits_df, "pos", "logp", "gene",
    xDomain=[0, offset], yDomain=[0, 13], fontSize=6, fontStyle="italic",  # gene names in italic
)

chart = points + sig + gene_labels

