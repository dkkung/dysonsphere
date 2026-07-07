import altair as alt
import dysonsphere as ds
from vega_datasets import data

# The verbose omnibus label is long - widen the canvas so it fits.
ds.theme(chartWidth=200)

cars = data.cars().dropna(subset=["Miles_per_Gallon"])
origins = ["Europe", "Japan", "USA"]

box = alt.Chart(cars).mark_boxplot().encode(
    x=alt.X("Origin:N", sort=origins, title=None),
    # Pad the y domain so the corner label clears the stacked brackets below it.
    y=alt.Y("Miles_per_Gallon:Q", scale=alt.Scale(domain=[0, 75]), title="Miles per gallon"),
    color=alt.Color("Origin:N"),
)

chart = box + ds.add_comparisons(
    cars, "Origin", "Miles_per_Gallon",
    [("Europe", "USA"), ("Japan", "USA")],
    test="kruskal", omnibusVerbose=True, categories=origins,
    yStart=50,
)
