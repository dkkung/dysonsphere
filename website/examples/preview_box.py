import altair as alt
import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = data.cars().dropna(subset=["Miles_per_Gallon"])

chart = (
    alt.Chart(cars)
    .mark_boxplot()
    .encode(
        x=alt.X("Origin:N", title=None),
        y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
        color=alt.Color("Origin:N", legend=None),
    )
)
