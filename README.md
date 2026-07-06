<p align="center">
  <img src="https://raw.githubusercontent.com/dkkung/dysonsphere/main/docs/logo.svg" width="190" alt="dysonsphere" />
</p>

An [Altair](https://altair-viz.github.io/) theme and chart utility library for publication-ready figures: perceptually uniform palettes, precise scientific defaults, statistical annotations, and self-documenting exports.

## Installation

```sh
# with pip
pip install dysonsphere

# with uv
uv add dysonsphere
```

Requires Python 3.11+. Every function that takes a DataFrame accepts **polars** or **pandas**.

## Quick start

```python
import altair as alt
import polars as pl
import dysonsphere as ds

ds.theme()  # apply the dysonsphere theme to all charts in the session

df = pl.DataFrame({"x": [1.2, 2.4, 3.1, 4.8], "y": [0.9, 2.2, 2.8, 4.4]})

chart = (
    alt.Chart(df)
    .mark_point()
    .encode(
        x="x:Q",
        y="y:Q",
        color=alt.Color("y:Q", scale=alt.Scale(range=ds.palette("blues"))),
    )
)

ds.save(chart, "myplot") # writes myplot.svg + myplot.json
```

## Documentation

Documentation, examples, and the chart gallery: **[dkkung.github.io/dysonsphere](https://dkkung.github.io/dysonsphere/)**
