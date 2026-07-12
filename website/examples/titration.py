"""A weak-acid / strong-base titration curve - equivalence and pKa marked with add_rule."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=180, chartHeight=140)

Ka, Kw = 10**-4.76, 1e-14  # acetic acid
Ca, Va, Cb = 0.1, 25.0, 0.1  # M, mL, M
Vb = np.linspace(0.02, 50, 400)
Vtot = (Va + Vb) / 1000.0
Cap = (Ca * Va / 1000.0) / Vtot  # formal acid conc.
Cbp = (Cb * Vb / 1000.0) / Vtot  # formal base conc.

# solve the proton-condition charge balance for [H+] by geometric bisection (vectorized)
lo, hi = np.full_like(Vb, 1e-14), np.ones_like(Vb)
for _ in range(80):
    mid = np.sqrt(lo * hi)
    f = (Cbp + mid) - (Kw / mid + Cap * Ka / (Ka + mid))  # monotone increasing in mid
    lo, hi = np.where(f > 0, lo, mid), np.where(f > 0, mid, hi)
pH = -np.log10(np.sqrt(lo * hi))

df = pl.DataFrame({"Vb": Vb, "pH": pH})
curve = alt.Chart(df).mark_line().encode(
    x=alt.X("Vb:Q", title="Base added (mL)", scale=alt.Scale(domain=[0, 50], nice=False)),
    y=alt.Y("pH:Q", title="pH", scale=alt.Scale(domain=[2, 13], nice=False)),
)

chart = (
    curve
    + ds.add_rule(25.0, axis="x", label="equivalence", labelAlign="top", labelPosition="right")
    + ds.add_rule(4.76, axis="y", strokeDash=True, label="pKa", labelAlign="left")
)
