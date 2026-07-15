"""qPCR grouped bars - relative expression of cytokine genes, vehicle vs LPS, with significance brackets."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=215, chartHeight=160)

rng = np.random.default_rng(7)
genes = ["GAPDH", "IL6", "TNF", "IL1B", "CXCL10"]
fold = {"GAPDH": 1.0, "IL6": 17.0, "TNF": 8.0, "IL1B": 12.0, "CXCL10": 21.0}  # LPS induction
sig = {"GAPDH": "ns", "IL6": "***", "TNF": "**", "IL1B": "***", "CXCL10": "***"}

rows = []
for g in genes:
    for cond, level in [("Vehicle", 1.0), ("LPS", fold[g])]:
        for _ in range(4):  # biological quadruplicate, lognormal technical noise
            rows.append({"gene": g, "condition": cond, "expr": float(level * np.exp(rng.normal(0, 0.16)))})
df = pl.DataFrame(rows)

# Bracket height per gene: a fixed gap above that gene's tallest error bar (mean + SEM), so brackets
# clear the error bars uniformly whatever the induction magnitude (a fixed gap above the mean let the
# tall CXCL10 error bar poke through).
bar_top = {}
for g in genes:
    tops = []
    for c in ["Vehicle", "LPS"]:
        v = df.filter((pl.col("gene") == g) & (pl.col("condition") == c))["expr"].to_numpy()
        tops.append(v.mean() + v.std(ddof=1) / np.sqrt(len(v)))
    bar_top[g] = max(tops) + 1.8
ymax = round(max(bar_top.values()) + 2.5)

x = alt.X("gene:N", title="Gene", sort=genes, axis=alt.Axis(labelFontStyle="italic"))  # italic gene symbols
xoff = alt.XOffset("condition:N", sort=["Vehicle", "LPS"])
yscale = alt.Scale(domain=[0, ymax])

base = alt.Chart(df).encode(x=x, xOffset=xoff)
bars = base.mark_bar().encode(
    y=alt.Y("mean(expr):Q", title="Relative expression", scale=yscale),
    color=alt.Color("condition:N", sort=["Vehicle", "LPS"], title=None),
)
err = base.mark_errorbar(extent="stderr").encode(y=alt.Y("expr:Q", title=""))

# Significance bracket over each gene's vehicle-vs-LPS pair: a top line (mark_line spanning the two
# offset positions via detail) plus down-ticks at each end (mark_rule), with the label centred on the
# band. GAPDH (housekeeping) is ns; the induced cytokines carry asterisks.
tick = 0.7
top_rows, tick_rows, star_rows = [], [], []
for g in genes:
    for cond in ["Vehicle", "LPS"]:
        top_rows.append({"gene": g, "condition": cond, "y": bar_top[g]})
        tick_rows.append({"gene": g, "condition": cond, "y": bar_top[g], "y2": bar_top[g] - tick})
    star_rows.append({"gene": g, "y": bar_top[g], "label": sig[g]})

top = alt.Chart(pl.DataFrame(top_rows)).mark_line().encode(
    x=x, xOffset=xoff, y=alt.Y("y:Q", scale=yscale, title=""), detail="gene:N"
)
ends = alt.Chart(pl.DataFrame(tick_rows)).mark_rule(strokeDash=[0, 0]).encode(
    x=x, xOffset=xoff, y=alt.Y("y:Q", scale=yscale, title=""), y2="y2:Q"
)
stars = alt.Chart(pl.DataFrame(star_rows)).mark_text(baseline="bottom", dy=-2, fontSize=8).encode(
    x=alt.X("gene:N", sort=genes), y=alt.Y("y:Q", scale=yscale, title=""), text="label:N"
)

chart = bars + err + ends + top + stars
