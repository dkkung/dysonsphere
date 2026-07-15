"""SHAP beeswarm - per-feature attribution swarm coloured by feature value, ranked by importance."""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=215, chartHeight=155)

rng = np.random.default_rng(6)
n = 300
# Each feature's SHAP value depends on its (normalised) value: a positive coefficient means high
# feature values push the prediction up, a negative one pushes it down. Magnitude sets importance.
features = {
    "glucose": (3.4, 0.35), "BMI": (2.2, 0.35), "age": (1.7, 0.3), "insulin": (-1.3, 0.4),
    "blood pressure": (1.0, 0.3), "pedigree": (0.8, 0.35), "pregnancies": (0.5, 0.3),
}
rows = []
for name, (eff, sd) in features.items():
    val = rng.uniform(0, 1, n)
    shap = eff * (val - 0.5) + rng.normal(0, sd, n)
    rows += [{"feature": name, "value": float(v), "shap": float(s)} for v, s in zip(val, shap)]
df = pl.DataFrame(rows)

# Rank features by mean |SHAP| (importance) so the strongest sits on top.
order = df.group_by("feature").agg(pl.col("shap").abs().mean().alias("imp")).sort("imp")["feature"].to_list()

# Density-scaled quasirandom swarm within each feature row (offset applied vertically via yOffset).
df = ds.add_quasirandom(df, "shap", ["feature"], heightPx=215, outCol="off")

points = (
    alt.Chart(df)
    .mark_circle(size=5, opacity=0.75)
    .encode(
        x=alt.X("shap:Q", title="SHAP value (impact on prediction)", scale=alt.Scale(domain=[-3, 3])),
        y=alt.Y("feature:N", sort=list(reversed(order)), title=None),
        yOffset=alt.YOffset("off:Q"),
        color=alt.Color(
            "value:Q",
            scale=alt.Scale(range=ds.palette("redsblues", 9, reverse=True)),  # low -> blue, high -> red
            legend=alt.Legend(title="feature value", gradientLength=90, values=[0, 1],
                              labelExpr="datum.value == 0 ? 'low' : 'high'"),
        ),
    )
)

chart = points + ds.add_rule(0.0, axis="x")  # SHAP = 0 reference
