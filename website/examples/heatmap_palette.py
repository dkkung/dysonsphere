import altair as alt
from vega_datasets import data

import dysonsphere as ds

# Per-type palettes: heatmapPalette styles only continuous heatmaps, leaving the
# categorical palette untouched. Any name from ds.palettes.colors works.
ds.theme(heatmapPalette="cosmos")

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
