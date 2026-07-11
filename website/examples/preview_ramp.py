import altair as alt
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=124, chartHeight=124)

# Diagonal linear ramp: the palette itself, laid out as a surface. Cells carry explicit
# edges (x/x2) on linear axes so the domain ends exactly on the 0 and 6 ticks; each cell
# overhangs by 0.02 units to cover the sub-pixel antialiasing seam.
N = 30
step = 6 / N
cells = []
for i in range(N):
    for j in range(N):
        cells.append(
            {
                "x0": round(i * step, 3),
                "x1": round((i + 1) * step + 0.02, 3),
                "y0": round(j * step, 3),
                "y1": round((j + 1) * step + 0.02, 3),
                "z": round((i + 0.5) * step + (j + 0.5) * step, 3),
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
            scale=alt.Scale(domain=[0, 6], nice=False),
            axis=alt.Axis(values=[0, 1, 2, 3, 4, 5, 6]),
        ),
        x2="x1",
        y=alt.Y(
            "y0:Q",
            title="y",
            scale=alt.Scale(domain=[0, 6], nice=False),
            axis=alt.Axis(values=[0, 1, 2, 3, 4, 5, 6]),
        ),
        y2="y1",
        color=alt.Color("z:Q", title="x + y"),
    )
)
