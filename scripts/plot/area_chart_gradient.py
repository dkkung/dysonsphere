import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(42)

TIMEPOINTS = np.linspace(0, 24, 200)
GROUP = "Drug A"
LINE_COLOR = "black"


def pk_curve(t: np.ndarray, cmax: float, tmax: float, half_life: float) -> np.ndarray:
    ke = np.log(2) / half_life
    ka = np.log(2) / (tmax * 0.5)
    scale = cmax / (np.exp(-ke * tmax) - np.exp(-ka * tmax))
    return scale * (np.exp(-ke * t) - np.exp(-ka * t))


rows = []
for t in TIMEPOINTS:
    c = pk_curve(np.array([t]), 0.9, 1.5, 4.0)[0] + rng.normal(0, 0.008)
    rows.append({"time": float(t), "concentration": max(0.0, float(c)), "group": GROUP})

df = pl.DataFrame(rows)

palette = ds.palette("mpl_YlGnBu", n=10)

ds.theme(closed=False)

area = (
    alt.Chart(df)
    .mark_area(
        fill={
            "gradient": "linear",
            "stops": [{"offset": i / 9, "color": c} for i, c in enumerate(palette[::-1])],
            "x1": 0,
            "y1": 0,
            "x2": 0,
            "y2": 1,
        },
        line={"stroke": LINE_COLOR, "strokeWidth": 0.5},
    )
    .encode(
        x=alt.X("time:Q", title="Time (h)"),
        y=alt.Y("concentration:Q", title="Concentration (ng/mL)"),
    )
)

chart = alt.layer(area)

ds.save(chart, "area_chart_gradient")
print("saved area_chart_gradient")
