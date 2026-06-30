"""
Manual equivalent of ds.mark_strip() using bare Altair.

Demonstrates how to replicate the jitter + median tick + error bar pattern
without mark_strip(), preserving full access to Altair's encoding API.
This lets you add tooltips, selections, alt.condition() colour mappings,
or any other Altair feature that LayerChart composition makes awkward.

Usage (from project root):
    uv run python scripts/plots/manual_strip.py
"""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(42)

GROUPS = ["Control", "Group A", "Group B", "Group C"]
n = 20

df = pl.DataFrame(
    {
        "group": sum([[g] * n for g in GROUPS], []),
        "value": np.concatenate([rng.normal(loc, 0.9, n) for loc in [5.0, 6.2, 7.8, 5.4]]),
    }
)

ds.theme(palette="lavenders", xLabelAngle=-45)

# ── Jitter ────────────────────────────────────────────────────────────────────
df = ds.add_jitter(df)  # adds "jitter_x" column

# Offset scale: maps jitter values to pixel offsets within the band center.
# This mirrors what mark_strip() computes internally.
band_padding = alt.theme.options.get("bandPadding", 0.1)
chart_width = alt.theme.options.get("chartWidth", 100)
step = chart_width / (len(GROUPS) + 2 * band_padding)
band_center = step * (0.5 - band_padding)
max_offset = float(df["jitter_x"].abs().max())  # ty: ignore[invalid-argument-type]
offset_scale = alt.Scale(
    domain=[-max_offset, max_offset],
    range=[band_center - max_offset, band_center + max_offset],
)

x = alt.X("group:N", sort=GROUPS, title=None)

# ── Points ────────────────────────────────────────────────────────────────────
point_size = alt.theme.options.get("markSize", 10)
point_opacity = alt.theme.options.get("markFillOpacity", 1.0)

points = (
    alt.Chart(df)
    .mark_circle(size=point_size, opacity=point_opacity)
    .encode(
        x=x,
        y=alt.Y("value:Q", title="Response"),
        xOffset=alt.XOffset("jitter_x:Q", scale=offset_scale),
        color=alt.Color("group:N", sort=GROUPS, legend=None),
        tooltip=[
            alt.Tooltip("group:N", title="Group"),
            alt.Tooltip("value:Q", title="Value", format=".2f"),
        ],
    )
)

# ── Median tick (via boxplot with everything hidden except the median) ─────────
median = (
    alt.Chart(df)
    .mark_boxplot(
        ticks=False,
        box={"fillOpacity": 0, "strokeOpacity": 0},
        rule={"strokeOpacity": 0},
        outliers={"opacity": 0},
    )
    .encode(x=x, y=alt.Y("value:Q", title="Response"))
)

# ── Error bars (mean ± SEM, computed manually) ────────────────────────────────
summary = df.group_by("group").agg(
    [
        pl.col("value").mean().alias("mean"),
        (pl.col("value").std() / pl.col("value").count().sqrt()).alias("sem"),
    ]
)

errorbars = (
    alt.Chart(summary)
    .mark_errorbar()
    .encode(
        x=x,
        y=alt.Y("mean:Q", title="Response"),
        yError=alt.YError("sem:Q"),
    )
)

# ── Compose ───────────────────────────────────────────────────────────────────
chart = points + errorbars + median

ds.save(chart, "strip_manual")
print("saved manual_strip")
