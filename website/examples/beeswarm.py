import altair as alt
from vega_datasets import data

import dysonsphere as ds

ds.theme()

cars = data.cars().dropna(subset=["Miles_per_Gallon"])

# ds.transforms.beeswarm() computes collision-avoiding x-offsets per group.
cars = ds.transforms.beeswarm(cars, "Miles_per_Gallon", groupBy=["Origin"])

# Pin a symmetric xOffset domain so offset 0 sits on the tick - otherwise Vega-Lite centres the
# tick on the offset range's midpoint, nudging a leaning swarm off-tick (mark_strip does this for
# you). m is the widest offset in either direction.
m = cars["beeswarm_x"].abs().max()

chart = (
    alt.Chart(cars)
    .mark_circle()
    .encode(
        x=alt.X("Origin:N", title=None),
        y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
        xOffset=alt.XOffset("beeswarm_x:Q", scale=alt.Scale(domain=[-m, m])),
    )
)
