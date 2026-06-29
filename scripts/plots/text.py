"""
Demo of add_text() annotation helper.

Shows the three coordinate modes and the position system.

Usage (from project root):
    uv run python scripts/examples/text.py
"""

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

rng = np.random.default_rng(42)

GROUPS = ["Control", "Group A", "Group B", "Group C", "Group D", "Group E"]
n = 20

df = pl.DataFrame(
    {
        "group": sum([[g] * n for g in GROUPS], []),
        "value": np.concatenate(
            [rng.normal(loc, 0.9, n) for loc in [4.0, 4.5, 3.2, 5.4, 8.0, 7.2]]
        ),
    }
)

ds.theme(palette="blues2", chartWidth=150, chartHeight=75)

base = ds.mark_strip(df, "group", "value", GROUPS, yTitle="Response")

chart = (
    base
    + ds.add_text(
        "n = 20", x="Control", y=1.0, align="center"
    )  # nominal x + quantitative y: label at a group center
    + ds.add_text(
        "ANOVA p < 0.001", position="topLeft"
    )  # position: ANOVA result in the top-right corner, inset 4 px
    + ds.add_text(
        "Threshold = 5.0", position="bottomRight"
    )  # position: threshold note in the bottom-left corner
    + ds.add_rule(5)  # add a horizontal reference line at the threshold
)

multi = {
    "Condition A": [False, True, True, False, False, False],
    "Condition B": [False, False, True, True, True, True],
}

annotated = ds.add_multilabel(
    chart, categories=GROUPS, groups=multi, style="plusminus", categoryLabel=True
)

ds.save(annotated, "text")
print("saved text_example")
