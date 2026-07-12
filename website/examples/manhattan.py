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

# Standard GWAS Manhattan x-axis: a tick under each chromosome with its number centered on the
# chromosome's span. The numbers are drawn as a mark_text layer, NOT axis labels - once add_labels
# pins the shared x-scale, Vega culls axis labels to a thinned subset even with labelOverlap=False
# (confirmed in both browser Vega and vl-convert), whereas mark_text marks are never culled. The
# axis keeps only ticks + the "Chromosome" title, whose titlePadding reserves the room the numbers
# sit in (so they are not clipped below the plot).
chrom_ticks = [round(t, 2) for t in tick_pos]
chrom_labels = [str(c) for c in range(1, len(chrom_sizes) + 1)]
chrom_df = pl.DataFrame({"pos": chrom_ticks, "chrom": chrom_labels})

points = (
    alt.Chart(df)
    .mark_circle(size=7, opacity=0.85)
    .encode(
        x=alt.X(
            "pos:Q",
            title="Chromosome",
            scale=alt.Scale(domain=[0, offset], nice=False),
            axis=alt.Axis(values=chrom_ticks, ticks=True, labels=False, titlePadding=13),
        ),
        y=alt.Y("logp:Q", title="−log₁₀ p", scale=alt.Scale(domain=[0, 13])),
        color=alt.Color("parity:N", scale=alt.Scale(range=["#3A68BB", "#28CDC5"]), legend=None),
    )
)

sig = ds.add_rule(7.3, label="P = 5×10⁻⁸", strokeDash=True, labelAlign="right")

hits_df = pl.DataFrame(hit_rows)
gene_labels = ds.add_labels(
    hits_df, "pos", "logp", "gene",
    xDomain=[0, offset], yDomain=[0, 13], fontSize=6, fontStyle="italic",  # gene names in italic
    fill=True,  # a background chip keeps each label legible over the point cloud
)

# chromosome numbers under the axis (mark_text so all 22 always render; see the axis note above)
chrom_nums = (
    alt.Chart(chrom_df)
    .mark_text(baseline="top", dy=4, fontSize=6)
    .encode(x=alt.X("pos:Q", axis=None), y=alt.value(115), text="chrom:N")
)

chart = points + sig + gene_labels + chrom_nums

