import math

import altair as alt
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=124, chartHeight=124)


def bump(x, y, mx, my, s):
    return math.exp(-((x - mx) ** 2 + (y - my) ** 2) / (2 * s * s))


# Gaussian-mixture density surface. Cells carry explicit edges (x/x2) on linear axes so the
# domain ends exactly on the -3 and 3 ticks; each cell overhangs by 0.02 units to cover the
# sub-pixel antialiasing seam.
N = 30
step = 6 / N
cells = []
for i in range(N):
    for j in range(N):
        x = -3 + (i + 0.5) * step
        y = -3 + (j + 0.5) * step
        z = bump(x, y, -1.2, -0.8, 0.9) + 0.7 * bump(x, y, 1.4, 1.0, 0.7) + 0.45 * bump(x, y, 0.3, -1.8, 0.5)
        cells.append(
            {
                "x0": round(-3 + i * step, 3),
                "x1": round(-3 + (i + 1) * step + 0.02, 3),
                "y0": round(-3 + j * step, 3),
                "y1": round(-3 + (j + 1) * step + 0.02, 3),
                "density": round(z, 4),
            }
        )
grid = pl.DataFrame(cells)

chart = (
    alt.Chart(grid)
    .mark_rect(stroke=None, clip=True)
    .encode(
        x=alt.X(
            "x0:Q",
            title="x",
            scale=alt.Scale(domain=[-3, 3], nice=False),
            axis=alt.Axis(values=[-3, -2, -1, 0, 1, 2, 3]),
        ),
        x2="x1",
        y=alt.Y(
            "y0:Q",
            title="y",
            scale=alt.Scale(domain=[-3, 3], nice=False),
            axis=alt.Axis(values=[-3, -2, -1, 0, 1, 2, 3]),
        ),
        y2="y1",
        color=alt.Color("density:Q", legend=alt.Legend(title="Density", titleOrient="top")),
    )
)
