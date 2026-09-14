<p align="center">
  <img src="https://raw.githubusercontent.com/dkkung/dysonsphere/main/docs/logo_with_text.svg" width="360" alt="dysonsphere" />
</p>

# dysonsphere

`dysonsphere` is an [`altair`](https://altair-viz.github.io/) library for plotting scientific figures in Python. It provides:
- A consistent default configuration enabled with `ds.theme()`.
- Perceptually uniform palettes, including those from popular data visualization libraries.
- Global styles through a `dysonsphere.toml` config file.

`dysonsphere` also provides several utilities for `altair` charts:
- Layer annotations such as reference lines, shades, text, and data labels onto charts.
- Statistical inference with `scipy` through `ds.stats.comparisons()` and `ds.stats.correlation()`,
  layered onto `alt.Chart` and exported as metadata:
  - Omnibus tests with effect sizes.
  - Brackets and *p*-values for pairwise and post hoc comparisons.
  - Correlations with fit lines.
- Multilabels for categorical labels, such as multi-condition axes and sample sizes.
- Self-documenting exports for reproducible figures:
  - `ds.save()` writes SVG, PNG, interactive HTML, and/or Vega-Lite JSON, and embeds figure provenance, allowing the metadata to identify the Vega-Lite spec and original data.
  - `ds.load()` rebuilds the chart from its JSON, allowing for further editing.

Separate authorable extensions can add field-specific plotting tools (such as for molecular biology or astronomy) that use the core theme, palettes, and export behavior.

## Installation

```sh
# with pip
pip install dysonsphere

# with uv
uv pip install dysonsphere

# add as a project dependency
uv add dysonsphere
```

Requires Python 3.11+. Every function that takes a `DataFrame` accepts either `polars` or `pandas`.

Dependencies:
- `altair`>=6.0.0
- `numpy`>=1.26.0
- `polars[pyarrow]`>=1.19.0
- `scipy`>=1.11.0
- `vl-convert-python`>=1.9.0

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

ds.save(chart, "my_plot") # writes my_plot.svg + my_plot.json
```

## Documentation

Documentation, examples, palettes, and an interactive chart studio can be found at **[dkkung.github.io/dysonsphere](https://dkkung.github.io/dysonsphere/)**.
