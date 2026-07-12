"""Van der Pol phase portrait - trajectories to the limit cycle, mark_trail width = speed."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

alt.data_transformers.enable("default", max_rows=None)
ds.theme(chartWidth=170, chartHeight=170)

mu = 2.0
dt = 0.02
steps = 900


def integrate(x0, y0):
    xs, ys, sp = [], [], []
    x, y = x0, y0
    for _ in range(steps):
        dx = y
        dy = mu * (1 - x * x) * y - x
        x += dx * dt
        y += dy * dt
        xs.append(x)
        ys.append(y)
        sp.append(np.hypot(dx, dy))
    return xs, ys, sp


rng = np.random.default_rng(1)
rows = []
tid = 0
starts = [(0.1, 0.1)] + [(rng.uniform(-3.5, 3.5), rng.uniform(-6, 6)) for _ in range(13)]
for x0, y0 in starts:
    xs, ys, sp = integrate(x0, y0)
    for k in range(0, len(xs), 2):  # thin for size
        rows.append({"x": xs[k], "y": ys[k], "speed": sp[k], "tid": f"t{tid}", "order": k})
    tid += 1
df = pl.DataFrame(rows)

chart = (
    alt.Chart(df)
    .mark_trail()
    .encode(
        x=alt.X("x:Q", title="x"),
        y=alt.Y("y:Q", title="ẋ"),
        order=alt.Order("order:Q"),
        detail="tid:N",
        size=alt.Size("speed:Q", scale=alt.Scale(range=[0.1, 2.2]), legend=None),
    )
)

