import altair as alt
import numpy as np
import polars as pl
from scipy.stats import gaussian_kde

import dysonsphere as ds

rng = np.random.default_rng(42)

GROUPS = ["Week 1", "Week 2", "Week 3", "Week 4", "Week 5", "Week 6"]
N = 200
OFFSET = 0.05  # vertical gap between baselines; smaller = more overlap
SCALE = 0.12  # peak height of each ridge; larger = taller ridges
LEGEND = False  # False = inline text labels on the left; True = color legend

rows = []
for i, group in enumerate(GROUPS):
    mean = 10 + i * 1.5
    sd = max(2.5 - i * 0.2, 1.0)
    for v in rng.normal(mean, sd, N):
        rows.append({"group": group, "value": float(v)})

df = pl.DataFrame(rows)

# Compute KDE per group and stack with baseline offsets
all_values = df["value"].to_numpy()
x_grid = np.linspace(float(all_values.min()) - 1, float(all_values.max()) + 1, 300)

density_rows = []
label_rows = []
for i, group in enumerate(GROUPS):
    baseline = (len(GROUPS) - 1 - i) * OFFSET  # Week 1 highest, Week 6 lowest
    kde = gaussian_kde(df.filter(pl.col("group") == group)["value"].to_numpy())
    density = kde(x_grid)
    density = density / density.max() * SCALE  # normalize to fixed peak height
    for x, d in zip(x_grid, density):
        density_rows.append(
            {
                "group": group,
                "value": float(x),
                "density": float(d) + baseline,
                "baseline": float(baseline),
                "draw_order": i,  # Week 1 drawn first (back), Week 6 last (front)
            }
        )
    label_rows.append({"group": group, "value": float(x_grid[0]), "baseline": float(baseline)})

density_df = pl.DataFrame(density_rows)
label_df = pl.DataFrame(label_rows)

palette = ds.palette("mpl_YlGnBu", n=len(GROUPS), start=1)

ds.theme(chartWidth=200, legend=LEGEND)

ridges = (
    alt.Chart(density_df)
    .mark_area()
    .encode(
        x=alt.X("value:Q", title="Value", axis=alt.Axis(domain=False)),
        y=alt.Y("density:Q", title=None, axis=None),
        y2=alt.Y2("baseline:Q"),
        color=alt.Color(
            "group:N",
            sort=GROUPS,
            scale=alt.Scale(range=palette),
            title=None,
            legend=alt.Legend() if LEGEND else None,
        ),
        order=alt.Order("draw_order:Q"),
    )
)

if LEGEND:
    chart = ridges
else:
    labels = (
        alt.Chart(label_df)
        .mark_text(align="right", dx=-4, baseline="middle")
        .encode(
            x=alt.X("value:Q"),
            y=alt.Y("baseline:Q"),
            text="group:N",
        )
    )
    chart = alt.layer(ridges, labels)

ds.save(chart, "ridgeplot")
print("saved ridgeplot")
