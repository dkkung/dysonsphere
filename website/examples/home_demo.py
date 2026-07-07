import altair as alt
import numpy as np
import polars as pl
import dysonsphere as ds

ds.theme(palette="blues2", chartWidth=140)

rng = np.random.default_rng(7)
rep1 = rng.normal(10, 2, 2500)
df = pl.DataFrame({"rep1": rep1, "rep2": rep1 * 0.9 + rng.normal(1, 0.9, 2500)})

heatmap = (
    alt.Chart(df)
    .mark_rect()
    .encode(
        x=alt.X("rep1:Q", bin=alt.Bin(maxbins=24), title="Replicate 1"),
        y=alt.Y("rep2:Q", bin=alt.Bin(maxbins=24), title="Replicate 2"),
        color=alt.Color("count():Q", title=None),
    )
)

chart = heatmap + ds.add_correlation(df, "rep1", "rep2")
