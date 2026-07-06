import altair as alt
import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = data.cars().dropna(subset=["Miles_per_Gallon", "Horsepower"])

scatter = alt.Chart(cars).mark_point().encode(
    x=alt.X("Horsepower:Q"),
    y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
)

# One call places multiple reference lines (a list of values) with per-line labels.
# labelPosition picks which side of the line the label sits on; labelAlign, where along it.
chart = scatter + ds.add_rule(
    [20, 30, 40],
    label=["economy", "efficient", "hybrid"],
    labelAlign="right",
    labelPosition="top",
)
