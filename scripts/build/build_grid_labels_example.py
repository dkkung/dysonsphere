"""
Generates docs/grid_labels_example_light.png — the README preview for add_grid_labels.

Shows all three grid label styles (plusminus, dot, text) side by side,
each attached below a strip chart via add_grid_labels().

Usage (from project root):
    uv run python scripts/build/build_grid_labels_example.py
"""

from pathlib import Path

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as theme

CATEGORIES = ["Control", "Drug A", "Drug B", "Drug C"]

rng = np.random.default_rng(42)
df = pl.DataFrame(
    {
        "group": (["Control"] * 50 + ["Drug A"] * 50 + ["Drug B"] * 50 + ["Drug C"] * 50),
        "value": np.concatenate(
            [
                rng.normal(1.0, 0.1, 50),
                rng.normal(2.1, 0.3, 50),
                rng.normal(5.4, 0.8, 50),
                rng.normal(7.2, 0.6, 50),
            ]
        ),
    }
)

CONDITIONS = {
    "Condition 1": [True,  False, True,  True],
    "Condition 2": [False, False, True,  False],
    "Condition 3": [False, False, False, True],
}

SCORES = {
    "Score A": ["1.2", "3.4", "0.8", "2.1"],
    "Score B": ["0.4", "0.1", "1.7", "0.9"],
    "Score C": ["5", "12", "8", "20"],
}


def build_grid_labels_example():
    theme.options()

    out_base = str(Path(__file__).parent.parent.parent / "docs" / "grid_labels_example")

    def make_chart() -> alt.HConcatChart:
        chart = theme.mark_strip(df, "group", "value", CATEGORIES)
        KWARGS = dict(categories=CATEGORIES, label_align="left")

        def corner_label(style_name: str) -> alt.LayerChart:
            label = (
                alt.Chart(alt.Data(values=[{}]))
                .mark_text(align="left", baseline="top", text=f'style = "{style_name}"')
                .encode(x=alt.value(4), y=alt.value(4))
            )
            return chart + label

        pm = theme.add_grid_labels(
            corner_label("plusminus"), CONDITIONS, style="plusminus", **KWARGS
        )
        dot = theme.add_grid_labels(corner_label("symbol"), CONDITIONS, style="symbol", **KWARGS)
        txt = theme.add_grid_labels(corner_label("text"), SCORES, style="text", **KWARGS)
        return alt.hconcat(pm, dot, txt)

    theme.save(make_chart, out_base, ppi=1200)
    print(f"saved {out_base}_light.png")


if __name__ == "__main__":
    build_grid_labels_example()
