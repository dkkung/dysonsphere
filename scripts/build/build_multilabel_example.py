"""
Generates docs/multilabel_example_light.png — the README preview for add_multilabel.

Shows all three grid label styles (plusminus, symbol, text) side by side,
each attached below a strip chart via add_multilabel().

Usage (from project root):
    uv run python scripts/build/build_multilabel_example.py
"""

from pathlib import Path
from typing import Any

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

ROOT = Path(__file__).resolve().parents[2]


CATEGORIES = ["Control", "Group A", "Group B", "Group C"]

rng = np.random.default_rng(42)
df = pl.DataFrame(
    {
        "group": (["Control"] * 38 + ["Group A"] * 45 + ["Group B"] * 52 + ["Group C"] * 41),
        "value": np.concatenate(
            [
                rng.normal(1.0, 0.1, 38),
                rng.normal(2.1, 0.3, 45),
                rng.normal(5.4, 0.8, 52),
                rng.normal(7.2, 0.6, 41),
            ]
        ),
    }
)

CONDITIONS = {
    "Condition 1": [False, False, False, True],
    "Condition 2": [False, False, True, True],
    "Condition 3": [False, True, True, True],
}

SCORES = {
    "Score A": ["1.2", "3.4", "0.8", "2.1"],
    "Score B": ["0.4", "0.1", "1.7", "0.9"],
    "Score C": ["5", "12", "8", "20"],
}

ds.theme(chartFill="white", palette="blues2")

chart = ds.mark_strip(df, "group", "value", CATEGORIES, yTitle="Value")
KWARGS: dict[str, Any] = dict(categories=CATEGORIES, labelAlign="left")


def corner_label(base: alt.LayerChart, text: str) -> alt.LayerChart:
    lines = text.split("\n")
    label = (
        alt.Chart(alt.Data(values=[{}]))
        .mark_text(align="left", baseline="top", text=lines if len(lines) > 1 else lines[0])
        .encode(x=alt.value(4), y=alt.value(4))
    )
    return base + label


pm = ds.add_multilabel(corner_label(chart, 'style = "plusminus"'), CONDITIONS, style="plusminus", **KWARGS)
dot = ds.add_multilabel(corner_label(chart, 'style = "symbol"'), CONDITIONS, style="symbol", **KWARGS)
txt = ds.add_multilabel(
    corner_label(chart, 'showSampleSize = True\nstyle = "text"'),
    {"Score A": SCORES["Score B"], "Score B": SCORES["Score C"]},
    style="text",
    showSampleSize=True,
    df=df,
    xCol="group",
    **KWARGS,
)
combined = alt.hconcat(pm, dot, txt)

out = ROOT / "docs" / "multilabel_example"
ds.save(combined, str(out), background=["light"], saveVegaSpec=False, saveMetadata=False)
print(f"saved {out}_light.png")
