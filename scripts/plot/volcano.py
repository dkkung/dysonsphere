import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(42)

n = 500
log2fc = rng.normal(0, 1.5, n)
neg_log10_p = np.abs(log2fc) * rng.exponential(1.2, n) + rng.exponential(0.3, n)

FC_THRESH = 1.0
P_THRESH = 1.3  # -log10(0.05)

category = np.where(
    (log2fc > FC_THRESH) & (neg_log10_p > P_THRESH),
    "Up",
    np.where((log2fc < -FC_THRESH) & (neg_log10_p > P_THRESH), "Down", "NS"),
)

df = pl.DataFrame(
    {
        "log2fc": log2fc,
        "neg_log10_p": neg_log10_p,
        "category": category,
    }
)

CATEGORIES = ["Up", "NS", "Down"]

ds.theme(chartWidth=200, markFillOpacity=0.9)

points = (
    alt.Chart(df)
    .mark_point()
    .encode(
        x=alt.X(
            "log2fc:Q",
            title="log₂(Fold Change)",
        ),
        y=alt.Y(
            "neg_log10_p:Q",
            title="-log₁₀(p-value)",
        ),
        color=alt.Color(
            "category:N",
            sort=CATEGORIES,
            title=None,
        ),
    )
)

h_rule = alt.Chart(alt.Data(values=[{"y": P_THRESH}])).mark_rule().encode(y=alt.Y("y:Q"))

v_rule_pos = alt.Chart(alt.Data(values=[{"x": FC_THRESH}])).mark_rule().encode(x=alt.X("x:Q"))

v_rule_neg = alt.Chart(alt.Data(values=[{"x": -FC_THRESH}])).mark_rule().encode(x=alt.X("x:Q"))

chart = points + h_rule + v_rule_pos + v_rule_neg

ds.save(chart, "volcano")
print("saved volcano")
