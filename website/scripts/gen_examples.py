#!/usr/bin/env python
"""Build the site's example charts and write light + dark Vega-Lite specs for live rendering.

Uses the standard vega-datasets (cars, barley, stocks) styled with dysonsphere. Each chart is
rendered twice - once with ``darkmode=False`` (black ink) and once with ``darkmode=True`` (white
ink) - both with ``transparentBackground=True``, so the Chart component can swap to the variant
matching the site's light/dark theme and let the page background provide contrast (no card).

The theme render args (``darkmode`` / ``transparentBackground``) live only here, never in the
snippets shown to users; the chart-building code is what a user would actually write.

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


def examples() -> dict:
    """Chart builders keyed by name. Each reads the *current* global theme when called, so we can
    build every chart once per light/dark theme."""
    cars = ds.ensure_polars(data.cars()).drop_nulls(["Miles_per_Gallon", "Horsepower"])
    barley = ds.ensure_polars(data.barley())
    stocks = ds.ensure_polars(data.stocks())

    def strip():
        return ds.mark_strip(cars, "Origin", "Miles_per_Gallon", ORIGINS, yTitle="Miles per gallon")

    def violin():
        return ds.mark_violin(cars, "Origin", "Horsepower", ORIGINS, yTitle="Horsepower")

    def comparisons():
        base = ds.mark_strip(cars, "Origin", "Miles_per_Gallon", ORIGINS, yTitle="Miles per gallon")
        return base + ds.add_comparisons(
            cars, "Origin", "Miles_per_Gallon", [("USA", "Europe"), ("USA", "Japan")], test="anova", categories=ORIGINS
        )

    def correlation():
        scatter = alt.Chart(cars).mark_point().encode(
            x=alt.X("Horsepower:Q"), y=alt.Y("Miles_per_Gallon:Q", title="Miles per gallon")
        )
        return scatter + ds.add_correlation(cars, "Horsepower", "Miles_per_Gallon", verbose=True)

    def bar():
        return (
            alt.Chart(barley)
            .mark_bar()
            .encode(
                x=alt.X("variety:N", sort="-y", title="Variety"),
                y=alt.Y("mean(yield):Q", title="Mean yield (bu/acre)"),
                color=alt.Color("variety:N", legend=None),
            )
        )

    def log():
        line = alt.Chart(stocks).mark_line().encode(
            x=alt.X("date:T", title=None),
            y=alt.Y("price:Q", scale=alt.Scale(type="log"), title="Price (USD)"),
            color=alt.Color("symbol:N", title="Symbol"),
        )
        return ds.add_log_ticks(line, stocks, "price", axis="y")

    return {
        "strip": strip,
        "violin": violin,
        "comparisons": comparisons,
        "correlation": correlation,
        "bar": bar,
        "log": log,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    builders = examples()
    # Per-example theme overrides so a guide's shown snippet matches its rendered chart.
    theme_overrides = {"bar": {"palette": "blues"}}
    for mode, dark in (("light", False), ("dark", True)):
        for name, builder in builders.items():
            ds.theme(transparentBackground=True, darkmode=dark, **theme_overrides.get(name, {}))
            (OUT / f"{name}-{mode}.json").write_text(json.dumps(builder().to_dict()), encoding="utf-8")
            print(f"wrote {name}-{mode}.json")
        ds.clear_stats()


if __name__ == "__main__":
    main()
