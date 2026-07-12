"""Atomic orbital cross-section - a signed 3d wavefunction, the diverging palette."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

alt.data_transformers.enable("default", max_rows=None)
ds.theme(chartWidth=160, chartHeight=160, divergingPalette="pinksblues", closed=True, viewPadding=False)

N = 95
L = 9.0
xs = np.linspace(-L, L, N)
X, Y = np.meshgrid(xs, xs)
r = np.hypot(X, Y)
# 3d_xy angular part (x*y) with a radial node -> four alternating-sign lobes
psi = (X * Y) * (r - 2.2) * np.exp(-r / 2.6)
psi = psi / np.abs(psi).max()

step = 2 * L / N
rows = []
for i in range(N):
    for j in range(N):
        rows.append(
            {
                "x0": round(-L + j * step, 3),
                "x1": round(-L + (j + 1) * step + step * 0.3, 3),
                "y0": round(-L + i * step, 3),
                "y1": round(-L + (i + 1) * step + step * 0.3, 3),
                "psi": round(float(psi[i, j]), 4),
            }
        )
df = pl.DataFrame(rows)

chart = (
    alt.Chart(df)
    .mark_rect(stroke=None, clip=True)
    .encode(
        x=alt.X("x0:Q", title="x (a₀)", scale=alt.Scale(domain=[-L, L], nice=False)),
        x2="x1",
        y=alt.Y("y0:Q", title="y (a₀)", scale=alt.Scale(domain=[-L, L], nice=False)),
        y2="y1",
        color=alt.Color("psi:Q", title="Ψ", scale=alt.Scale(domainMid=0)),
    )
)

