import altair as alt
import dysonsphere as ds
from vega_datasets import data

# Built-in style presets: "notebook" and "presentation". A dysonsphere.toml
# config file can customise them or add your own.
ds.theme(style="presentation", palette="blues")

barley = data.barley()

chart = (
    alt.Chart(barley)
    .mark_bar()
    .encode(
        x=alt.X("site:N", sort="-y", title="Site"),
        y=alt.Y("mean(yield):Q", title="Mean yield (bu/acre)"),
        color=alt.Color("site:N", legend=None),
    )
)
