"""Gray-Scott reaction-diffusion - a Turing pattern grown from noise, in nebula."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

alt.data_transformers.enable("default", max_rows=None)
ds.theme(chartWidth=150, chartHeight=150, closed=True, viewPadding=False, heatmapPalette="nebula")

rng = np.random.default_rng(3)
N = 100
Du, Dv, f, k = 0.16, 0.08, 0.060, 0.062  # coral/spot regime
U = np.ones((N, N))
V = np.zeros((N, N))
for _ in range(22):  # seed random patches of V
    y, x = rng.integers(4, N - 12, 2)
    U[y : y + 8, x : x + 8], V[y : y + 8, x : x + 8] = 0.5, 0.25
V += 0.02 * rng.standard_normal((N, N))


def lap(Z):
    return np.roll(Z, 1, 0) + np.roll(Z, -1, 0) + np.roll(Z, 1, 1) + np.roll(Z, -1, 1) - 4 * Z


for _ in range(3600):  # integrate the PDE
    uvv = U * V * V
    U += Du * lap(U) - uvv + f * (1 - U)
    V += Dv * lap(V) + uvv - (f + k) * V

img = (V - V.min()) / (np.ptp(V) + 1e-9)
df = pl.DataFrame(
    [
        {"x0": j, "x1": j + 1.3, "y0": i, "y1": i + 1.3, "c": round(float(img[i, j]), 4)}
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
        color=alt.Color("c:Q", title="concentration", legend=None),
    )
    .properties(view=alt.ViewConfig(stroke=None))
)
