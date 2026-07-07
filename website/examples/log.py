import altair as alt
import dysonsphere as ds
from vega_datasets import data

ds.theme()

stocks = data.stocks()

line = alt.Chart(stocks).mark_line().encode(
    x=alt.X("date:T", title=None),
    y=alt.Y(
        "price:Q",
        scale=alt.Scale(type="log"),
        # Major ticks on the decades; add_log_ticks() fills in the minors.
        axis=alt.Axis(values=[1, 10, 100, 1000]),
        title="Price (USD)",
    ),
    color=alt.Color("symbol:N", title="Symbol"),
)

chart = ds.add_log_ticks(line, stocks, "price", axis="y")
