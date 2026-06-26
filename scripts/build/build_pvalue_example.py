"""
Generates docs/pvalue_example_light.png — the README preview for add_pvalue.

Shows label_style="p" on the left and label_style="asterisks" on the right,
both annotating the same three-group comparison on a boxplot.

Usage (from project root):
    uv run python scripts/build/build_pvalue_example.py
"""

from pathlib import Path

import altair as alt
import numpy as np
import polars as pl

import dysonsphere as ds

CATEGORIES = ["Group A", "Group B", "Group C"]

rng = np.random.default_rng(42)
df = pl.DataFrame(
    {
        "group": [CATEGORIES[0]] * 40 + [CATEGORIES[1]] * 40 + [CATEGORIES[2]] * 40,
        "value": np.concatenate(
            [
                rng.normal(1.0, 0.35, 40),  # Group A
                rng.normal(2.2, 0.45, 40),  # Group B — clearly different from Group A (***)
                rng.normal(1.15, 0.4, 40),  # Group C — barely different from Group A (ns)
            ]
        ),
    }
)

PAIRS = [("Group A", "Group B"), ("Group A", "Group C"), ("Group B", "Group C")]


def build_pvalue_example():
    ds.theme(palette="blues2", chartWidth=75, markSize=10, angledX=True, legend=False)

    x = alt.X("group:N", sort=CATEGORIES, title=None)

    left_base = (
        alt.Chart(df)
        .mark_boxplot(color=ds.palette("blues")[0])
        .encode(x=x, y=alt.Y("value:Q", title=None), color=alt.Color("group:N"))
    )
    right_base = (
        alt.Chart(df)
        .mark_boxplot(color=ds.palette("blues")[0])
        .encode(x=x, y=alt.Y("value:Q", title=None), color=alt.Color("group:N"))
    )

    pvalue_kwargs = dict(
        df=df,
        x_col="group",
        y_col="value",
        pairs=PAIRS,
        categories=CATEGORIES,
        y_pad=0.25,
        y_step=0.6,
    )

    title_params = dict(orient="top", anchor="start", offset=4)
    fontSize = alt.theme.options.get("fontSize", 7)

    left = (left_base + ds.add_pvalue(**pvalue_kwargs, label_style="p")).properties(
        title=alt.TitleParams(
            ['labelStyle="p"', 'bracketStyle="line"'], fontSize=fontSize, **title_params
        )
    )
    right = (
        right_base
        + ds.add_pvalue(**pvalue_kwargs, label_style="asterisks", bracket_style="bracket")
    ).properties(
        title=alt.TitleParams(
            ['labelStyle="asterisks"', 'bracketStyle="bracket"'], fontSize=fontSize, **title_params
        )
    )

    chart = alt.hconcat(left, right)

    out_base = str(Path(__file__).parent.parent.parent / "docs" / "pvalue_example")
    ds.save(chart, out_base, background=["light"])
    print(f"saved {out_base}_light.png")


if __name__ == "__main__":
    build_pvalue_example()
