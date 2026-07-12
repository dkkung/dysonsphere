"""The Mandelbrot set - smooth (continuous) escape-time coloring, in borealis."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

alt.data_transformers.enable("default", max_rows=None)
ds.theme(chartWidth=160, chartHeight=150, closed=True, viewPadding=False, heatmapPalette="borealis")

N = 120
MAXIT = 260
# a seahorse-valley window of the complex plane
re = np.linspace(-0.766, -0.724, N)
im = np.linspace(0.092, 0.134, N)
C = re[None, :] + 1j * im[:, None]
Z = np.zeros_like(C)
esc = np.zeros(C.shape)  # interior stays 0 (dark); the boundary filaments glow
alive = np.ones(C.shape, bool)
for it in range(MAXIT):
    Z[alive] = Z[alive] ** 2 + C[alive]
    mag = np.abs(Z)
    just = alive & (mag > 2)
    # smooth iteration count: it + 1 - log2(log|z|) - large near the boundary
    esc[just] = it + 1 - np.log2(np.log(mag[just]))
    alive &= ~just
esc = np.sqrt(esc)  # gentle stretch so the outer bands read
esc = (esc - esc.min()) / (np.ptp(esc) + 1e-9)

df = pl.DataFrame(
    [
        {"x0": j, "x1": j + 1.3, "y0": i, "y1": i + 1.3, "c": round(float(esc[i, j]), 4)}
        for i in range(N)
        for j in range(N)
    ]
)

chart = (
    alt.Chart(df)
    .mark_rect(stroke=None, clip=True)
    .encode(
        x=alt.X("x0:Q", title=None, axis=None, scale=alt.Scale(domain=[0, N], nice=False)),
        x2="x1",
        y=alt.Y("y0:Q", title=None, axis=None, scale=alt.Scale(domain=[0, N], nice=False)),
        y2="y1",
        color=alt.Color("c:Q", title="escape time", legend=None),
    )
    .properties(view=alt.ViewConfig(stroke=None))
)
