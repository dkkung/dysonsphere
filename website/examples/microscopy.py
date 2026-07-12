import altair as alt
import numpy as np
import polars as pl
from scipy.ndimage import gaussian_filter

import dysonsphere as ds

# Continuous color defaults to australis - the viridis-analogue journey.
alt.data_transformers.enable("default", max_rows=None)
ds.theme(chartWidth=150, chartHeight=150, closed=True, viewPadding=False)

rng = np.random.default_rng(11)
N = 90
FOV = 58.0  # microns

# Draw a cytoskeletal web by tracing many PERSISTENT random walks (a slowly-drifting heading
# gives smooth curvilinear filaments, not noise). Each walker lays down a soft brush and
# occasionally branches, so the walkers cross into a connected network; a light blur fuses
# them, a gamma darkens the ground, and a few bright puncta stand in for focal adhesions.
img = np.zeros((N, N))
ys, xs = np.mgrid[0:N, 0:N]


def deposit(cy, cx, amp, s):
    y0, y1 = max(0, int(cy - 3 * s)), min(N, int(cy + 3 * s) + 1)
    x0, x1 = max(0, int(cx - 3 * s)), min(N, int(cx + 3 * s) + 1)
    if y0 < y1 and x0 < x1:
        gy, gx = ys[y0:y1, x0:x1], xs[y0:y1, x0:x1]
        img[y0:y1, x0:x1] += amp * np.exp(-((gx - cx) ** 2 + (gy - cy) ** 2) / (2 * s * s))


stack = [(rng.uniform(0, N), rng.uniform(0, N), rng.uniform(0, 2 * np.pi),
          int(rng.integers(35, 110)), float(rng.uniform(0.6, 1.0))) for _ in range(120)]
while stack:
    cy, cx, theta, steps, bright = stack.pop()
    for _ in range(steps):
        deposit(cy, cx, bright, rng.uniform(0.55, 0.8))
        theta += rng.normal(0, 0.32)
        cy, cx = cy + np.sin(theta), cx + np.cos(theta)
        if not (0 <= cy < N and 0 <= cx < N):
            break
        if rng.random() < 0.015:
            stack.append((cy, cx, theta + rng.uniform(-1.1, 1.1), int(rng.integers(20, 60)), bright * 0.9))

img = gaussian_filter(img, 0.6)
img = (img / img.max()) ** 1.6 * img.max()
for _ in range(7):
    cy, cx = rng.uniform(8, N - 8, 2)
    img += rng.uniform(1.5, 2.8) * np.exp(-((xs - cx) ** 2 + (ys - cy) ** 2) / (2 * rng.uniform(1.4, 2.6) ** 2))
img += 0.02 * np.abs(rng.standard_normal((N, N)))
img = np.clip(img, 0, np.percentile(img, 99.7))
img = img / img.max() * 18.0

step = FOV / N
df = pl.DataFrame(
    [
        {"x0": round(j * step, 3), "x1": round((j + 1) * step + step * 0.3, 3),
         "y0": round(i * step, 3), "y1": round((i + 1) * step + step * 0.3, 3),
         "intensity": round(float(img[i, j]), 3)}
        for i in range(N)
        for j in range(N)
    ]
)

chart = (
    alt.Chart(df)
    .mark_rect(stroke=None, clip=True)
    .encode(
        x=alt.X("x0:Q", title="x (µm)", scale=alt.Scale(domain=[0, FOV], nice=False)),
        x2="x1",
        y=alt.Y("y0:Q", title="y (µm)", scale=alt.Scale(domain=[0, FOV], nice=False)),
        y2="y1",
        color=alt.Color("intensity:Q", title="Intensity (a.u.)"),
    )
)
