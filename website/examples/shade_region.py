import altair as alt
from vega_datasets import data

import dysonsphere as ds

ds.theme()

cars = data.cars().dropna(subset=["Miles_per_Gallon", "Horsepower"])

scatter = (
    alt.Chart(cars)
    .mark_point()
    .encode(
        x=alt.X("Horsepower:Q"),
        y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
    )
)

# axis="both" with a nested ((x_start, x_end), (y_start, y_end)) tuple shades a 2D region -
# an intersection rectangle spanning both axes. Drawn under the points with +.
chart = (
    ds.shade(
        palette=[ds.palettes.colors["blues"][0]],
        positions=[((40, 100), (28, 48))],
        axis="both",
        opacity=0.5,
    )
    + scatter
)
