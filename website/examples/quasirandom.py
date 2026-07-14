import altair as alt
import dysonsphere as ds
from vega_datasets import data

ds.theme()

cars = ds.ensure_polars(data.cars()).drop_nulls(["Miles_per_Gallon"])

# add_quasirandom() spreads points by local density (a van der Corput sequence weighted by a KDE)
# for a symmetric, reproducible swarm - avoiding the lopsided tightly-packed rows add_beeswarm can
# show. The trade is that it does not guarantee non-overlap.
cars = ds.add_quasirandom(cars, "Miles_per_Gallon", groupBy=["Origin"])

# Pin a symmetric xOffset domain so offset 0 sits exactly on the tick (the same guarantee
# mark_strip gives you) - without it, Vega-Lite centres the tick on the offset range's midpoint.
m = cars["quasirandom_x"].abs().max()

chart = (
    alt.Chart(cars)
    .mark_circle()
    .encode(
        x=alt.X("Origin:N", title=None),
        y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon"),
        xOffset=alt.XOffset("quasirandom_x:Q", scale=alt.Scale(domain=[-m, m])),
    )
)
