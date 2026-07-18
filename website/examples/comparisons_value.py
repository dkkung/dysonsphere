import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme()

rng = np.random.default_rng(5)
CATS = ["Ctrl", "Low", "High"]
means = [1.0, 1.45, 2.0]
df = pl.DataFrame({
    "dose": [c for c in CATS for _ in range(8)],
    "viability": np.concatenate([rng.normal(m, 0.4, 8) for m in means]),
})

x = alt.X("dose:N", sort=CATS, title="Dose")
base = alt.Chart(df).encode(x)
bars = base.mark_bar().encode(y=alt.Y("mean(viability):Q", title="Viability", scale=alt.Scale(domain=[0, 2.3])))
err = base.mark_errorbar(extent="stderr").encode(y=alt.Y("viability:Q", title=""))

# labelStyle="value" drops the "P =" for a bare number (keeping "< 0.001" when floored);
# yPositions=2 sets a flat row above the bars.
chart = bars + err + ds.add_comparisons(
    df, "dose", "viability",
    reference="Ctrl", categories=CATS,
    test="ttest_ind", labelStyle="value", yPositions=2.0,
)
