"""Spiral galaxy - stars on log-spiral arms, colored by line-of-sight velocity (diverging)."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

alt.data_transformers.enable("default", max_rows=None)
ds.theme(chartWidth=170, chartHeight=170, divergingPalette="redsblues")

rng = np.random.default_rng(6)
n_arm = 2600
arms = 2
b = 0.35  # spiral tightness
r = rng.uniform(0.4, 10, n_arm)
arm_id = rng.integers(0, arms, n_arm)
theta = np.log(r) / b + arm_id * (2 * np.pi / arms) + rng.normal(0, 0.22, n_arm)
x = r * np.cos(theta) + rng.normal(0, 0.3, n_arm)
y = r * np.sin(theta) + rng.normal(0, 0.3, n_arm)

# central bulge
n_bulge = 900
rb = np.abs(rng.normal(0, 1.3, n_bulge))
tb = rng.uniform(0, 2 * np.pi, n_bulge)
x = np.concatenate([x, rb * np.cos(tb)])
y = np.concatenate([y, rb * np.sin(tb)])

# rotation curve -> line-of-sight velocity (flat outer curve), projected on x
rr = np.hypot(x, y)
vrot = 1.0 - np.exp(-rr / 1.5)
vlos = vrot * (-y / (rr + 1e-6))  # km/s (normalized)

df = pl.DataFrame({"x": x, "y": y, "vlos": vlos})

chart = (
    alt.Chart(df)
    .mark_circle(size=3, opacity=0.6)
    .encode(
        x=alt.X("x:Q", axis=None),
        y=alt.Y("y:Q", axis=None),
        color=alt.Color("vlos:Q", title="v (l.o.s.)", scale=alt.Scale(domainMid=0)),
    )
    .properties(view=alt.ViewConfig(stroke=None))
)

