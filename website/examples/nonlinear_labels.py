import altair as alt
import dysonsphere as ds
from vega_datasets import data

ds.theme()

stocks = data.stocks()

# log_label_expr() returns a Vega labelExpr for typeset log labels (10¹, 10², …).
line = alt.Chart(stocks).mark_line().encode(
    x=alt.X("date:T", title=None),
    y=alt.Y(
        "price:Q",
        scale=alt.Scale(type="log"),
        axis=alt.Axis(values=[1, 10, 100, 1000], labelExpr=ds.log_label_expr(notation="power")),
        title="Price (USD)",
    ),
    color=alt.Color("symbol:N", title="Symbol"),
)

chart = ds.add_log_ticks(line, stocks, "price", axis="y")
