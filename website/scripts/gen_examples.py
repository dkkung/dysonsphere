#!/usr/bin/env python
"""Build the gallery's example charts and write their Vega-Lite specs for live rendering.

Uses the standard vega-datasets (cars, barley, stocks) rather than synthetic data, styled with
dysonsphere. Each chart's ``to_dict()`` spec is written to website/public/charts/<name>.json,
which the Chart.astro component renders live via vega-embed.

Run from the repo/worktree root:

    uv run --with vega-datasets python website/scripts/gen_examples.py
"""

from __future__ import annotations

import json
from pathlib import Path

import altair as alt
from vega_datasets import data

import dysonsphere as ds

OUT = Path("website/public/charts")
ORIGINS = ["USA", "Europe", "Japan"]


def build() -> dict[str, alt.TopLevelMixin]:
    ds.theme()
    cars = ds.ensure_polars(data.cars()).drop_nulls(["Miles_per_Gallon", "Horsepower"])
    barley = ds.ensure_polars(data.barley())
    stocks = ds.ensure_polars(data.stocks())

    charts: dict[str, alt.TopLevelMixin] = {}

    # Strip plot: fuel economy by region of origin.
    charts["strip"] = ds.mark_strip(cars, "Origin", "Miles_per_Gallon", ORIGINS, yTitle="Miles per gallon")

    # Violin plot: engine power by region.
    charts["violin"] = ds.mark_violin(cars, "Origin", "Horsepower", ORIGINS, yTitle="Horsepower")

    # Statistical comparisons: ANOVA + pairwise brackets.
    strip = ds.mark_strip(cars, "Origin", "Miles_per_Gallon", ORIGINS, yTitle="Miles per gallon")
    charts["comparisons"] = strip + ds.add_comparisons(
        cars, "Origin", "Miles_per_Gallon", [("USA", "Europe"), ("USA", "Japan")], test="anova", categories=ORIGINS
    )

    # Correlation: horsepower vs. fuel economy with an OLS fit.
    scatter = alt.Chart(cars).mark_point().encode(
        x=alt.X("Horsepower:Q"), y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon")
    )
    charts["correlation"] = scatter + ds.add_correlation(cars, "Horsepower", "Miles_per_Gallon", verbose=True)

    # Bar with the category palette: mean barley yield by variety.
    charts["bar"] = (
        alt.Chart(barley)
        .mark_bar()
        .encode(
            x=alt.X("variety:N", sort="-y", title="Variety"),
            y=alt.Y("mean(yield):Q", title="Mean yield (bu/acre)"),
            color=alt.Color("variety:N", legend=None),
        )
    )

    # Log-scale axis with minor ticks: stock prices over time.
    line = alt.Chart(stocks).mark_line().encode(
        x=alt.X("date:T", title=None),
        y=alt.Y("price:Q", scale=alt.Scale(type="log"), title="Price (USD)"),
        color=alt.Color("symbol:N", title="Symbol"),
    )
    charts["log"] = ds.add_log_ticks(line, stocks, "price", axis="y")

    return charts


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, chart in build().items():
        (OUT / f"{name}.json").write_text(json.dumps(chart.to_dict()), encoding="utf-8")
        print(f"wrote {OUT / f'{name}.json'}")
    ds.clear_stats()


if __name__ == "__main__":
    main()
