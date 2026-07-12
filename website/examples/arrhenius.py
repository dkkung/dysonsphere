"""An Arrhenius plot - ln k vs 1/T with the OLS fit and readout from add_correlation."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=175, chartHeight=140)

rng = np.random.default_rng(4)
T = np.array([290, 300, 310, 320, 330, 340, 350, 360, 370, 380.0])  # K
Ea, A, R = 55e3, 1e11, 8.314  # J/mol, prefactor, gas constant
lnk = np.log(A * np.exp(-Ea / (R * T))) + rng.normal(0, 0.18, T.size)
df = pl.DataFrame({"invT": 1000.0 / T, "lnk": lnk})

pts = alt.Chart(df).mark_circle().encode(
    x=alt.X("invT:Q", title="1000 / T  (K⁻¹)"),
    y=alt.Y("lnk:Q", title="ln k"),
)

chart = pts + ds.add_correlation(df, "invT", "lnk", includeEquation=True, position="topRight")
