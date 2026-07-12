"""A CO2 pressure-temperature phase diagram - boundaries, triple + critical points, phase labels."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=180, chartHeight=150)

Tt, Pt = 216.6, 5.18  # triple point (K, bar)
Tc, Pc = 304.1, 73.8  # critical point

# vaporization (triple -> critical): Clausius-Clapeyron ln P = a - b/T through both points
b = (np.log(Pt) - np.log(Pc)) / (1 / Tc - 1 / Tt)
a = np.log(Pt) + b / Tt
Tvap = np.linspace(Tt, Tc, 60)
# sublimation (below triple): steeper CC anchored at the triple point
bs, as_ = b * 1.35, np.log(Pt) + b * 1.35 / Tt
Tsub = np.linspace(185, Tt, 50)
# fusion (near-vertical, slight positive dP/dT) rising from the triple point
Pfus = np.linspace(Pt, 300, 40)

rows = [{"T": float(t), "P": float(np.exp(a - b / t)), "boundary": "vaporization"} for t in Tvap]
rows += [{"T": float(t), "P": float(np.exp(as_ - bs / t)), "boundary": "sublimation"} for t in Tsub]
rows += [{"T": Tt + (p - Pt) * 0.006, "P": float(p), "boundary": "fusion"} for p in Pfus]
bounds = pl.DataFrame(rows)
lines = alt.Chart(bounds).mark_line().encode(
    x=alt.X("T:Q", title="Temperature (K)", scale=alt.Scale(domain=[185, 320], nice=False)),
    y=alt.Y(
        "P:Q", title="Pressure (bar)", scale=alt.Scale(type="log", domain=[1, 300], nice=False),
        axis=alt.Axis(values=[1, 10, 100]),  # decades only; add_log_ticks() fills the half-size minors
    ),
    detail="boundary:N",
)
pts = alt.Chart(pl.DataFrame({"T": [Tt, Tc], "P": [Pt, Pc]})).mark_point(
    size=28, filled=True, opacity=1
).encode(x="T:Q", y="P:Q")

visual = (
    lines
    + pts
    + ds.add_text("Solid", x=200.0, y=40.0)
    + ds.add_text("Liquid", x=268.0, y=120.0)
    + ds.add_text("Gas", x=250.0, y=2.0)
    + ds.add_text("Supercritical", x=312.0, y=140.0, align="right")
    + ds.add_text("Triple", x=Tt, y=Pt, offsetX=-4, align="right")
    + ds.add_text("Critical", x=Tc, y=Pc, offsetX=6, align="left")
)
chart = ds.add_log_ticks(visual, bounds, axis="y", field="P")
