"""Ramachandran plot - protein backbone dihedral density (φ vs ψ), australis."""

import altair as alt
import numpy as np
import polars as pl
from scipy.ndimage import gaussian_filter

import dysonsphere as ds

alt.data_transformers.enable("default", max_rows=None)
ds.theme(chartWidth=160, chartHeight=160)

rng = np.random.default_rng(4)
# residues from a mixture: right-handed alpha helix, beta sheet, left-handed alpha
modes = [
    ((-63, -42), (12, 12), 5000),
    ((-135, 135), (18, 16), 3500),
    ((-63, -20), (10, 25), 1500),
    ((60, 45), (12, 12), 500),
]
phi, psi = [], []
for (mp, ms), (sp, ss), k in modes:
    phi += list(rng.normal(mp, sp, k))
    psi += list(rng.normal(ms, ss, k))
phi = np.clip(np.array(phi), -180, 180)
psi = np.clip(np.array(psi), -180, 180)

N = 90
H, xe, ye = np.histogram2d(phi, psi, bins=N, range=[[-180, 180], [-180, 180]])
H = gaussian_filter(H, 1.1)
H = np.sqrt(H)

rows = []
for i in range(N):
    for j in range(N):
        rows.append(
            {
                "phi0": round(xe[i], 2),
                "phi1": round(xe[i + 1] + (xe[1] - xe[0]) * 0.3, 2),
                "psi0": round(ye[j], 2),
                "psi1": round(ye[j + 1] + (ye[1] - ye[0]) * 0.3, 2),
                "density": round(float(H[i, j]), 4),
            }
        )
df = pl.DataFrame(rows)

chart = (
    alt.Chart(df)
    .mark_rect(stroke=None, clip=True)
    .encode(
        x=alt.X("phi0:Q", title="φ (°)", scale=alt.Scale(domain=[-180, 180], nice=False),
                axis=alt.Axis(values=[-180, -90, 0, 90, 180])),
        x2="phi1",
        y=alt.Y("psi0:Q", title="ψ (°)", scale=alt.Scale(domain=[-180, 180], nice=False),
                axis=alt.Axis(values=[-180, -90, 0, 90, 180])),
        y2="psi1",
        color=alt.Color("density:Q", title=None, legend=None),
    )
)

