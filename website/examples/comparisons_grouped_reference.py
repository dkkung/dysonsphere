import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ds.theme(chartWidth=250, chartHeight=150, xAxis=False)

G = ds.colors["greys"]
CTRL_FILL = G[4]  # three shades darker than the default bar fill (greys[1])
BAR_FILL = G[1]

rng = np.random.default_rng(7)
GROUPS = ["Sham", "Stim", "Stim+IFN"]
CONDS = ["Veh", "1", "3", "10", "30", "100"]
baseline = {"Sham": 2.0, "Stim": 5.0, "Stim+IFN": 8.0}
dose = {"Veh": 1.0, "1": 1.1, "3": 1.3, "10": 1.6, "30": 2.0, "100": 2.5}
df = pl.DataFrame([
    {"grp": g, "cond": c, "y": baseline[g] * dose[c] * np.exp(rng.normal(0, 0.07))}
    for g in GROUPS for c in CONDS for _ in range(10)
])

# Jitter the points within each sub-bar: a per-level integer slot plus the quasirandom offset.
idx = {c: i for i, c in enumerate(CONDS)}
df = ds.add_quasirandom(df, "y", ["grp", "cond"])
jmax = df["quasirandom_x"].abs().max()
df = df.with_columns((pl.col("cond").replace_strict(idx) + pl.col("quasirandom_x") / jmax * 0.34).alias("xoff"))

# Category-keyed yPositions: one flat asterisk row per group, above that group's bars.
YPOS = {"Sham": 6.5, "Stim": 15.5, "Stim+IFN": 22.0}

x = alt.X("grp:N", sort=GROUPS, title=None)
xo = alt.XOffset("cond:N", sort=CONDS)
base = alt.Chart(df).encode(x, xo)
bars = base.mark_bar().encode(
    y=alt.Y("mean(y):Q", title="Cytokine (pg/mL)"),
    fill=alt.condition("datum.cond === 'Veh'", alt.value(CTRL_FILL), alt.value(BAR_FILL)),
)
err = base.mark_errorbar(extent="stderr").encode(y=alt.Y("y:Q", title=""))

# Grouped reference mode: compare every dose against "Veh" within each group, asterisks over each bar.
ann = ds.add_comparisons(
    df, "grp", "y",
    xOffsetCol="cond", reference="Veh",
    categories=GROUPS, xOffsetSort=CONDS,
    test="mannwhitneyu", correction="holm",
    labelStyle="asterisks", yPositions=YPOS,
)

points = alt.Chart(df).mark_circle(size=2).encode(
    x, xOffset=alt.XOffset("xoff:Q", scale=alt.Scale(domain=[-0.5, 5.5])), y="y:Q",
)

# Nest the bars/errorbars/annotation together, then layer the jittered points with an
# independent xOffset scale (categorical bars vs. quantitative point jitter can't share one).
grouped = alt.layer(alt.layer(bars, err, ann), points).resolve_scale(xOffset="independent")
chart = ds.add_multilabel(
    grouped, categories=GROUPS,
    span={"Sham": ["Sham"], "Stim": ["Stim"], "Stim + IFNγ": ["Stim+IFN"]},
)
