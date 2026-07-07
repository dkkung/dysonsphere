import altair as alt
import dysonsphere as ds
from vega_datasets import data

ds.theme(chartWidth=120)

cars = data.cars().dropna(subset=["Miles_per_Gallon", "Horsepower"])

chart = (
    alt.Chart(cars)
    .mark_rect()
    .encode(
        x=alt.X("Horsepower:Q", bin=alt.Bin(maxbins=12)),
        y=alt.Y("Miles_per_Gallon:Q", bin=alt.Bin(maxbins=12), title="Miles per gallon"),
        color=alt.Color("count():Q", title="Cars"),
    )
)
