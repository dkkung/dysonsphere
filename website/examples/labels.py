import altair as alt
import dysonsphere as ds
from vega_datasets import data

ds.theme(chartWidth=160, chartHeight=120)

cars = ds.ensure_polars(data.cars()).drop_nulls(["Horsepower", "Miles_per_Gallon"])

scatter = alt.Chart(cars).mark_circle().encode(
    x=alt.X("Horsepower:Q"),
    y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
)

# add_labels auto-places non-overlapping labels with connector lines. Deterministic (no RNG),
# so the figure is reproducible. Pass the full df and let labels= select which points to name -
# here, 8 spread evenly across the plot (farthest-point sampling, no cherry-picking).
chart = scatter + ds.add_labels(
    cars, "Horsepower", "Miles_per_Gallon", "Name", labels=8
)
