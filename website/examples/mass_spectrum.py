"""Mass spectrum - stick spectrum with an isotope envelope and labeled fragment peaks."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=250, chartHeight=130)

rng = np.random.default_rng(2)
# fragment peaks (m/z, rel. intensity, label); each gets a small isotope tail
frags = [
    (43, 55, ""),
    (57, 40, ""),
    (71, 100, "C₅H₁₁⁺"),
    (91, 62, "tropylium"),
    (105, 30, ""),
    (134, 18, ""),
    (149, 12, ""),
    (178, 45, "M⁺"),
]
mz, inten = [], []
for m, h, _ in frags:
    for k in range(3):  # isotope peaks
        mz.append(float(m + k))
        inten.append(h * (0.65**k) * (1 + rng.normal(0, 0.02)))
# a bit of baseline grass
for _ in range(60):
    mz.append(rng.uniform(30, 185))
    inten.append(rng.uniform(0.5, 4))
df = pl.DataFrame({"mz": mz, "intensity": inten})

sticks = (
    alt.Chart(df)
    .mark_rule(strokeWidth=0.9, strokeDash=[0, 0])
    .encode(
        x=alt.X("mz:Q", title="m/z", scale=alt.Scale(domain=[25, 190])),
        y=alt.Y("intensity:Q", title="relative intensity", scale=alt.Scale(domain=[0, 108])),
    )
)

labels = ds.add_text([f[2] for f in frags if f[2]][0], x=71.0, y=104.0, fontSize=6)
for m, h, lab in frags:
    if lab and m != 71:
        labels = labels + ds.add_text(lab, x=float(m), y=float(h + 6), fontSize=6)

chart = sticks + labels

