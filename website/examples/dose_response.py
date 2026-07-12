"""Dose-response curves - % viability vs log dose for three compounds, sigmoid fits (IC50)."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=175, chartHeight=140)

rng = np.random.default_rng(3)


def hill(dose, ic50, slope=1.2, top=100.0, bottom=0.0):
    """Four-parameter logistic (Hill) dose-response: viability falls from top to bottom about IC50."""
    return bottom + (top - bottom) / (1 + (dose / ic50) ** slope)


doses = np.logspace(0, 4, 8)  # 1 .. 10,000 nM, 8 points
fine = np.logspace(0, 4, 200)  # smooth curve for the fit
compounds = [("Compound A", 30.0), ("Compound B", 300.0), ("Compound C", 2500.0)]

pts, curves = [], []
for name, ic50 in compounds:
    for d in doses:
        for _ in range(3):  # technical triplicate
            pts.append({"dose": float(d), "viab": float(hill(d, ic50) + rng.normal(0, 5)), "compound": name})
    curves += [{"dose": float(d), "viab": float(hill(d, ic50)), "compound": name} for d in fine]

pts_df = pl.DataFrame(pts)
xenc = alt.X(
    "dose:Q", title="Dose (nM)", scale=alt.Scale(type="log", domain=[1, 10000], nice=False),
    axis=alt.Axis(values=[1, 10, 100, 1000, 10000], labelExpr=ds.log_label_expr(notation="power")),
)
yenc = alt.Y("viab:Q", title="Viability (%)", scale=alt.Scale(domain=[-10, 115], nice=False))

fits = (
    alt.Chart(pl.DataFrame(curves))
    .mark_line()
    .encode(x=xenc, y=yenc, color=alt.Color("compound:N", title=None))
)
# mean +/- SD of the triplicate at each dose, instead of every raw point
bars = alt.Chart(pts_df).mark_errorbar(extent="stdev").encode(
    x=xenc, y=yenc, color=alt.Color("compound:N", legend=None)
)
means = alt.Chart(pts_df).mark_point(size=14, filled=True).encode(
    x=xenc, y="mean(viab):Q", color=alt.Color("compound:N", legend=None)
)

chart = fits + bars + means
