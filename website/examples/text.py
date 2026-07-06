import altair as alt
import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = data.cars().dropna(subset=["Miles_per_Gallon", "Horsepower"])

scatter = alt.Chart(cars).mark_point().encode(
    x=alt.X("Horsepower:Q"),
    y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
)

# Position presets pin text to the chart frame; data coordinates pin it to values.
chart = (
    scatter
    + ds.add_text("n = 392", position="topRight")
    + ds.add_text("outlier cluster", x=200.0, y=32.0, fontSize=5)
)
