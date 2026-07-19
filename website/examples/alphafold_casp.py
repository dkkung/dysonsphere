"""AlphaFold2 at CASP14 - the protein-folding problem, cracked.

At the 2020 CASP14 blind structure-prediction assessment, DeepMind's AlphaFold2 predicted protein
backbones at a median accuracy (GDT_TS ~92 out of 100) approaching experiment - and far above every
other group, a leap the field had not seen in 25 years of CASP. Each point is a predictor group's
median GDT_TS; AlphaFold2 sits alone at the top. The gap and AlphaFold2's ~92 are the real CASP14
result; the trailing field is a representative ranking.
"""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds
from dysonsphere.palettes import colors

ds.theme(chartWidth=230, chartHeight=170)
dark = bool(alt.theme.options.get("darkmode"))  # the site injects darkmode per light/dark spec
NAVY = colors["australis"][4] if dark else colors["borealis"][2]  # indigo-navy, lighter on dark
GREY = colors["greys"][5 if dark else 6]

rng = np.random.default_rng(11)
n = 96
rank = np.arange(1, n + 1)
# the field trails off from ~75; AlphaFold2 (group 427) is the lone point near experimental accuracy
gdt = np.clip(62 * np.exp(-(rank - 2) / 24) + 12 + rng.normal(0, 2.3, n), 6, 78)
gdt[0] = 92.4  # AlphaFold2 median GDT_TS
df = pl.DataFrame({"rank": rank, "gdt": gdt, "group": ["AlphaFold2"] + ["field"] * (n - 1)})

xenc = alt.X("rank:Q", title="Predictor group (ranked by accuracy)")
yenc = alt.Y("gdt:Q", title="Median GDT_TS")

field = alt.Chart(df.filter(pl.col("group") == "field")).mark_circle(size=15, color=GREY, opacity=0.7).encode(x=xenc, y=yenc)
af = alt.Chart(df.filter(pl.col("group") == "AlphaFold2")).mark_circle(size=15, color=NAVY).encode(x=xenc, y=yenc)
# label just the AlphaFold2 point (auto-placed with a connector); add_labels drives the shared scale
labels = ds.add_labels(df, "rank", "gdt", "group", labels=(df["group"] == "AlphaFold2"))

chart = field + af + labels
