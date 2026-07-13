import altair as alt
import polars as pl

import dysonsphere as ds
from dysonsphere.palettes import colors

# A real fluorescence micrograph (1000x1000 px, 0.0271 µm/px), its GFP intensity recolored with
# the focus LUT (true-black floor for imaging) and served as an image; the colorbar is a
# matching focus color scale.
ds.theme(chartWidth=170, chartHeight=170, closed=True, viewPadding=False)

FOV = 1000 * 0.027083  # 27.08 µm field of view

image = (
    alt.Chart(pl.DataFrame({"x": [0.0], "x2": [FOV], "y": [0.0], "y2": [FOV]}))
    .mark_image(url="/gallery/condensate.png", aspect=False)
    .encode(
        x=alt.X("x:Q", title="x (µm)", scale=alt.Scale(domain=[0, FOV], nice=False)),
        x2="x2:Q",
        y=alt.Y("y:Q", title="y (µm)", scale=alt.Scale(domain=[0, FOV], nice=False)),
        y2="y2:Q",
    )
)

# an invisible layer whose continuous color scale draws the focus colorbar (a.u.)
colorbar = (
    alt.Chart(pl.DataFrame({"x": [0.0, 0.0], "y": [0.0, 0.0], "intensity": [0.0, 1.0]}))
    .mark_point(opacity=0)
    .encode(
        x="x:Q",
        y="y:Q",
        color=alt.Color("intensity:Q", title="Intensity (a.u.)", scale=alt.Scale(range=colors["focus"])),
    )
)

chart = image + colorbar
