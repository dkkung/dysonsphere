"""Hubble 1929 - the expanding universe, from the original 24 galaxies.

Edwin Hubble's velocity-distance diagram: more distant galaxies recede faster, in direct proportion.
The slope is the Hubble constant - here ~400-500 km/s/Mpc, the famous early overestimate (the modern
value is ~70; his distance scale was off). Fit + confidence band from add_correlation. Distances and
radial velocities are the 24 individual nebulae from Hubble's 1929 paper.
"""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=205, chartHeight=175, inwardTicks=True)
dark = bool(alt.theme.options.get("darkmode"))
ink = "white" if dark else "black"

# distance (Mpc), radial velocity (km/s) - Hubble (1929), Table 1
DATA = [
    (0.032, 170), (0.034, 290), (0.214, -130), (0.263, -70), (0.275, -185), (0.275, -220),
    (0.45, 200), (0.5, 290), (0.5, 270), (0.63, 200), (0.8, 300), (0.9, -30),
    (0.9, 650), (0.9, 150), (0.9, 500), (1.0, 920), (1.1, 450), (1.1, 500),
    (1.4, 500), (1.7, 960), (2.0, 500), (2.0, 850), (2.0, 800), (2.0, 1090),
]
df = pl.DataFrame(DATA, schema=["distance", "velocity"], orient="row")

# Hubble's constant is the slope of the fit
h0 = float(np.polyfit(df["distance"].to_numpy(), df["velocity"].to_numpy(), 1)[0])

scatter = alt.Chart(df).mark_point(filled=True, size=13, color=ink).encode(
    x=alt.X("distance:Q", title="Distance (Mpc)", scale=alt.Scale(domain=[-0.05, 2.1], nice=False)),
    y=alt.Y("velocity:Q", title="Radial velocity (km/s)"),
)
label = ds.add_text(f"H₀ ≈ {h0:.0f} km/s/Mpc", position="topLeft")

chart = scatter + ds.add_correlation(df, "distance", "velocity", ci=True, position=None) + label
