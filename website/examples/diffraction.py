"""Electron diffraction pattern - a reciprocal lattice of Bragg spots, eclipse (mono)."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

alt.data_transformers.enable("default", max_rows=None)
ds.theme(chartWidth=160, chartHeight=160, heatmapPalette="eclipse", closed=True, viewPadding=False)

N = 92
L = 10.0
xs = np.linspace(-L, L, N)
X, Y = np.meshgrid(xs, xs)
img = np.zeros((N, N))

# hexagonal reciprocal lattice; spot brightness falls with |g| (form factor), a few orders
b1 = np.array([2.4, 0.0])
b2 = np.array([1.2, 2.08])
for h in range(-4, 5):
    for k in range(-4, 5):
        g = h * b1 + k * b2
        r2 = g[0] ** 2 + g[1] ** 2
        amp = np.exp(-r2 / 40.0)
        if h == 0 and k == 0:
            amp = 1.0
        img += amp * np.exp(-((X - g[0]) ** 2 + (Y - g[1]) ** 2) / (2 * 0.16))
img = img / img.max()
img = img ** 0.5  # lift faint high-order spots

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
                "I": round(float(img[i, j]), 4),
            }
        )
df = pl.DataFrame(rows)

chart = (
    alt.Chart(df)
    .mark_rect(stroke=None, clip=True)
    .encode(
        x=alt.X("x0:Q", title="q_x (1/nm)", scale=alt.Scale(domain=[-L, L], nice=False)),
        x2="x1",
        y=alt.Y("y0:Q", title="q_y (1/nm)", scale=alt.Scale(domain=[-L, L], nice=False)),
        y2="y1",
        color=alt.Color("I:Q", title=None, legend=None),
    )
)

