import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds
from dysonsphere.utils import band_geometry

ds.theme()

rng = np.random.default_rng(11)
CATS = ["Ctrl", "Low", "Mid", "High"]
means = [1.0, 1.3, 2.1, 3.0]
df = pl.DataFrame({
    "dose": [c for c in CATS for _ in range(10)],
    "response": np.concatenate([rng.normal(m, 0.28, 10) for m in means]),
})
df = ds.add_quasirandom(df, "response", ["dose"])
# Pin the offset domain wider than the data so the swarm stays inside the bars.
m = df["quasirandom_x"].abs().max() * 1.9
bar_w = band_geometry(len(CATS), scale="band").step * 0.82  # narrower than the band, so the swarm sits inside

x = alt.X("dose:N", sort=CATS, title="Dose")
bars = alt.Chart(df).mark_bar(size=bar_w).encode(x, y=alt.Y("mean(response):Q", title="Response"))
points = alt.Chart(df).mark_circle(size=2).encode(
    x, xOffset=alt.XOffset("quasirandom_x:Q", scale=alt.Scale(domain=[-m, m])), y="response:Q",
)

# reference="Ctrl": compare every dose against the control, drawing the p-value above each bar
# with no brackets - the clean many-vs-control layout.
chart = bars + points + ds.add_comparisons(
    df, "dose", "response",
    reference="Ctrl", categories=CATS,
    test="ttest_ind", correction="holm", labelStyle="asterisks",
)
