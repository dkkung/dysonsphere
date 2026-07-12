"""Two-source wave interference - fringe field from coherent point sources (australis)."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

alt.data_transformers.enable("default", max_rows=None)
ds.theme(chartWidth=175, chartHeight=140, closed=True, viewPadding=False)

N = 92
W, H = 24.0, 18.0
xs = np.linspace(0, W, N)
ysv = np.linspace(0, H, int(N * H / W))
X, Y = np.meshgrid(xs, ysv)
k = 2 * np.pi / 1.6  # wavenumber
sources = [(2.0, H / 2 - 3.0), (2.0, H / 2 + 3.0)]
amp = np.zeros_like(X)
for sx, sy in sources:
    r = np.hypot(X - sx, Y - sy)
    amp += np.cos(k * r) / np.sqrt(r + 0.5)
intensity = amp**2

M = X.shape[0]
sx_ = W / N
sy_ = H / X.shape[0]
rows = []
for i in range(M):
    for j in range(N):
        rows.append(
            {
                "x0": round(j * sx_, 3),
                "x1": round((j + 1) * sx_ + sx_ * 0.3, 3),
                "y0": round(i * sy_, 3),
                "y1": round((i + 1) * sy_ + sy_ * 0.3, 3),
                "I": round(float(intensity[i, j]), 4),
            }
        )
df = pl.DataFrame(rows)

chart = (
    alt.Chart(df)
    .mark_rect(stroke=None, clip=True)
    .encode(
        x=alt.X("x0:Q", title="x (mm)", scale=alt.Scale(domain=[0, W], nice=False)),
        x2="x1",
        y=alt.Y("y0:Q", title="y (mm)", scale=alt.Scale(domain=[0, H], nice=False)),
        y2="y1",
        color=alt.Color("I:Q", title=None, legend=None),
    )
)

