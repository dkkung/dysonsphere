import altair as alt
import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = data.cars().dropna(subset=["Miles_per_Gallon", "Weight_in_lbs"])

scatter = alt.Chart(cars).mark_point().encode(
    x=alt.X("Weight_in_lbs:Q", title="Weight (lbs)"),
    y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
)

# Rank correlations report the coefficient only - no fit line, since a straight
# line is not their model.
chart = scatter + ds.add_correlation(
    cars, "Weight_in_lbs", "Miles_per_Gallon",
    method="spearman", includePvalue=True, position="topRight",
)
