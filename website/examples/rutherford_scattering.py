"""Rutherford scattering - the experiment that found the atomic nucleus.

Geiger and Marsden fired alpha particles at a thin gold foil and counted the scintillations at each
deflection angle. The counts follow Rutherford's 1/sin⁴(θ/2) law across nearly four orders of
magnitude - only a tiny, dense, positively charged nucleus could deflect alpha particles so sharply.
Counts from Geiger & Marsden (1913); the curve is Rutherford's law, calibrated to the data.
"""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=225, chartHeight=170)
dark = bool(alt.theme.options.get("darkmode"))
ink = "white" if dark else "black"

# scattering angle (degrees), relative scintillation count - Geiger & Marsden (1913)
ANGLE = [15, 22.5, 30, 37.5, 45, 60, 75, 105, 120, 135, 150]
COUNT = [132000, 27300, 7800, 3300, 1435, 477, 211, 70, 52, 43, 33]

ang = np.array(ANGLE, dtype=float)
cnt = np.array(COUNT, dtype=float)
c = float(np.mean(cnt * np.sin(np.radians(ang) / 2) ** 4))  # Rutherford: N = C / sin⁴(θ/2)
fine = np.linspace(12, 156, 240)
curve = pl.DataFrame({"angle": fine, "N": c / np.sin(np.radians(fine) / 2) ** 4})
df = pl.DataFrame({"angle": ang, "N": cnt})

yscale = alt.Scale(type="log", domain=[20, 3e5])
yaxis = alt.Axis(values=[100, 1000, 10000, 100000], labelExpr=ds.log_label_expr(notation="power"), title="Scintillations (relative)")
xenc = alt.X("angle:Q", title="Scattering angle (degrees)", scale=alt.Scale(domain=[0, 160], nice=False))

law = alt.Chart(curve).mark_line(color=ds.palette("australis", 5)[2]).encode(x=xenc, y=alt.Y("N:Q", scale=yscale, axis=yaxis))
pts = alt.Chart(df).mark_point(filled=True, size=32, color=ink).encode(x=xenc, y=alt.Y("N:Q", scale=yscale, axis=yaxis))
chart = ds.add_log_ticks(law + pts, df, "N", axis="y")
