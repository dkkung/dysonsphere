import altair as alt
from vega_datasets import data

import dysonsphere as ds

ds.theme(width=160, height=120)

cars = data.cars().dropna(subset=["Horsepower", "Miles_per_Gallon"])

scatter = (
    alt.Chart(cars)
    .mark_circle()
    .encode(
        x=alt.X("Horsepower:Q"),
        y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
    )
)

# ds.labels auto-places non-overlapping labels with connector lines. Deterministic (no RNG),
# so the figure is reproducible. Pass the full df and let subset= select which points to name -
# here, 8 spread evenly across the plot (farthest-point sampling, no cherry-picking).
chart = scatter + ds.labels(cars, "Horsepower", "Miles_per_Gallon", "Name", subset=8)
