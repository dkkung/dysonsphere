"""Ridgeline plot - stacked KDE densities across conditions, categorical palette."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=200, chartHeight=180)

rng = np.random.default_rng(9)
months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug"]
grid = np.linspace(-4, 30, 220)
overlap = 2.6

rows = []
for i, m in enumerate(months):
    mu = 6 + 9 * np.sin(i / len(months) * np.pi) + rng.normal(0, 0.5)
    sd = 2.5 + 0.4 * rng.random()
    samples = np.concatenate([rng.normal(mu, sd, 400), rng.normal(mu + 4, 1.5, 120)])
    # simple Gaussian KDE
    bw = 1.2
    dens = np.exp(-((grid[:, None] - samples[None, :]) ** 2) / (2 * bw**2)).sum(1)
    dens = dens / dens.max()
    for x, dd in zip(grid, dens):
        rows.append({"temp": float(x), "month": m, "idx": i, "base": float(i * -1.0),
                     "top": float(i * -1.0 + dd * overlap)})
df = pl.DataFrame(rows)

layers = []
for i in reversed(range(len(months))):  # back-to-front so ridges overlap correctly
    sub = df.filter(pl.col("idx") == i)
    layers.append(
        alt.Chart(sub)
        .mark_area(interpolate="monotone", opacity=0.9, stroke="white", strokeWidth=0.4)
        .encode(
            x=alt.X("temp:Q", title="Temperature (°C)"),
            y=alt.Y("top:Q", axis=None, scale=alt.Scale(domain=[-len(months), overlap + 0.5])),
            y2="base:Q",
            color=alt.Color("month:N", sort=months, legend=None),
        )
    )

chart = alt.layer(*layers)

