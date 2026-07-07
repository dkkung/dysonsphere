import altair as alt
import dysonsphere as ds
from vega_datasets import data

ds.theme()

stocks = data.stocks()

chart = (
    alt.Chart(stocks)
    .mark_line()
    .encode(
        x=alt.X("date:T", title=None),
        y=alt.Y("price:Q", title="Price (USD)"),
        color=alt.Color("symbol:N", title=None),
    )
)
