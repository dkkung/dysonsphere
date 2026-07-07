import altair as alt
import dysonsphere as ds
from vega_datasets import data

# cornerRadius=True rounds bar tips (and rects/arcs) by a size derived from the
# chart dimensions; pass a float for explicit pixels.
ds.theme(palette="blues", xLabelAngle=-45, cornerRadius=True)

barley = data.barley()

chart = (
    alt.Chart(barley)
    .mark_bar()
    .encode(
        x=alt.X("variety:N", sort="-y", title="Variety"),
        y=alt.Y("mean(yield):Q", title="Mean yield (bu/acre)"),
        color=alt.Color("variety:N", legend=None),
    )
)
