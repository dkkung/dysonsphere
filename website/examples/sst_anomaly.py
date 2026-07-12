"""Sea-surface temperature anomaly - warm/cool eddies on a diverging scale about 0."""

import altair as alt
import numpy as np
import polars as pl
from scipy.ndimage import gaussian_filter

import dysonsphere as ds
from dysonsphere.palettes import colors

alt.data_transformers.enable("default", max_rows=None)
ds.theme(chartWidth=190, chartHeight=140, closed=True, viewPadding=False)

rng = np.random.default_rng(7)
NX, NY = 110, 80
field = np.zeros((NY, NX))
ys, xs = np.mgrid[0:NY, 0:NX]
for _ in range(26):  # superpose warm (+) and cool (-) mesoscale eddies
    cy, cx = rng.uniform(0, NY), rng.uniform(0, NX)
    sx, sy = rng.uniform(6, 16), rng.uniform(5, 12)
    amp = rng.uniform(-3.2, 3.2)
    field += amp * np.exp(-((xs - cx) ** 2 / (2 * sx**2) + (ys - cy) ** 2 / (2 * sy**2)))
field = gaussian_filter(field, 1.2)
field += 0.15 * rng.standard_normal((NY, NX))

LONW, LATW = 40.0, 30.0  # degrees spanned
sx, sy = LONW / NX, LATW / NY
df = pl.DataFrame(
    [
        {"lon": round(j * sx, 3), "lon2": round((j + 1.3) * sx, 3),
         "lat": round(i * sy, 3), "lat2": round((i + 1.3) * sy, 3),
         "anom": round(float(field[i, j]), 3)}
        for i in range(NY)
        for j in range(NX)
    ]
)

chart = (
    alt.Chart(df)
    .mark_rect(stroke=None, clip=True)
    .encode(
        x=alt.X("lon:Q", title="Longitude (°E)", scale=alt.Scale(domain=[0, LONW], nice=False)),
        x2="lon2",
        y=alt.Y("lat:Q", title="Latitude (°N)", scale=alt.Scale(domain=[0, LATW], nice=False)),
        y2="lat2",
        # reversed redsblues so warm anomalies read red, cool read blue
        color=alt.Color("anom:Q", title="ΔT (°C)", scale=alt.Scale(range=colors["redsblues"][::-1], domain=[-4, 4])),
    )
)
