import altair as alt
import dysonsphere as ds
from vega_datasets import data

# Angle crowded categorical labels; alignment follows the sign automatically.
ds.theme(palette="blues", xLabelAngle=-45)

barley = data.barley()

chart = (
    alt.Chart(barley)
    .mark_bar()
    .encode(
        x=alt.X("variety:N", sort="-y", title=None),
        y=alt.Y("mean(yield):Q", title="Mean yield (bu/acre)"),
        color=alt.Color("variety:N", legend=None),
    )
)
