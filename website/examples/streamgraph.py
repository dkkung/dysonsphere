"""Streamgraph - ML framework share of published models over time, a centre-stacked mark_area."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=250, chartHeight=150)

years = np.arange(2015, 2026)
t = years - 2015
# Smooth share trajectories: scikit-learn fades, TensorFlow/Keras peak then wane, PyTorch surges,
# JAX arrives late. A streamgraph (stack="center") reads these as flowing bands.
trends = {
    "scikit-learn": 38 - 2.2 * t,
    "Keras": 22 * np.exp(-((t - 3) ** 2) / 8),
    "TensorFlow": 12 + 30 * np.exp(-((t - 4) ** 2) / 14),
    "PyTorch": 4 + 46 / (1 + np.exp(-(t - 5))),
    "JAX": 20 / (1 + np.exp(-(t - 8.5))),
}
rows = [
    {"year": int(y), "framework": name, "models": max(0.5, float(series[i]))}
    for name, series in trends.items()
    for i, y in enumerate(years)
]
df = pl.DataFrame(rows)

order = ["scikit-learn", "Keras", "TensorFlow", "PyTorch", "JAX"]
chart = (
    alt.Chart(df)
    .mark_area(interpolate="monotone")
    .encode(
        x=alt.X("year:O", title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("models:Q", stack="center", axis=None),  # streamgraph baseline is meaningless
        color=alt.Color("framework:N", sort=order, title="Framework"),
        order=alt.Order("framework:N", sort="ascending"),
    )
)
