import altair as alt
import dysonsphere as ds
from vega_datasets import data

ds.theme(palette="blues", xLabelAngle=-45)

barley = data.barley()
sites = ["Morris", "Duluth", "University Farm", "Waseca", "Crookston", "Grand Rapids"]

bar = (
    alt.Chart(barley)
    .mark_bar()
    .encode(
        x=alt.X("site:N", sort=sites, title=None),
        y=alt.Y("mean(yield):Q", title="Mean yield (bu/acre)"),
        color=alt.Color("site:N", legend=None),
    )
)

# Band mode: alternate background shades across the x-axis categories.
chart = ds.add_shade(categories=sites, palette=[ds.colors["blues"][0], "white"], opacity=0.5) + bar
