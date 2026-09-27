import altair as alt
from vega_datasets import data

import dysonsphere as ds

# Plain Altair marks inherit the theme too: grey boxes, single-stroke median,
# rounded whisker caps, and hidden outlier points.
ds.theme()

cars = data.cars().dropna(subset=["Miles_per_Gallon"])

chart = (
    alt.Chart(cars)
    .mark_boxplot()
    .encode(
        x=alt.X("Origin:N", title=None),
        y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
    )
)
