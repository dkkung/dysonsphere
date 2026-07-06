<p align="center">
  <img src="https://raw.githubusercontent.com/dkkung/dysonsphere/main/docs/logo.svg" width="190" alt="dysonsphere" />
</p>

# dysonsphere

`dysonsphere` is an [`altair`](https://altair-viz.github.io/) utility library for publication-ready scientific figures in Python, offering:
- An attractive, cohesive, and sensible default configuration with a single invocation of `ds.theme()`.
- Perceptually uniform palettes, including those from popular data visualization libraries.
- Shareable styles through a simple `dysonsphere.toml` config file - tune the theme once and reuse it across projects.

`dysonsphere` also comes with several intuitive and powerful utilities for `altair` charts; some highlights include:
- The ability to quickly and easily layer `altair` charts with annotations like reference lines, shades, text, and data labels.
- Statistical inference with `scipy`, layered directly onto `alt.Chart` and conveniently exported as metadata in your saved chart:
    - Omnibus tests with effect sizes.
    - Brackets and *p*-values for pairwise and post hoc comparisons.
    - Correlations with fit lines.
- Multilabels that allow for rich annotations of categorical labels, *e.g.* multi-condition axes and sample sizes.
- Self-documenting exports for reproducible figures:
    - `ds.save()` writes a corrected SVG, print-ready PNG, interactive HTML, and/or Vega-Lite JSON, while also embedding the output file with its provenance: environment versions and sha256 checksums identifying both the **Vega-Lite spec and the underlying data**.
    - `ds.read()` recovers the statistics report, metadata, and even the original data from a saved figure.
    - `ds.load()` rebuilds the chart from its JSON.

`dysonsphere` is extensible with field-specific utilities, allowing domain toolkits (e.g. molecular biology, astronomy) to plug into the same theme, palettes, and export pipeline as separately installed packages.

## Installation

```sh
# with pip
pip install dysonsphere

# with pip through uv
uv pip install dysonsphere

# add as a project dependency
uv add dysonsphere
```

Requires Python 3.11+. Every function that takes a `DataFrame` accepts `polars` or `pandas`.

Dependencies:
- `altair`>=5.5.0
- `numpy`>=1.26.0
- `polars[pyarrow]`>=1.19.0
- `scipy`>=1.11.0

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

Documentation, examples, palettes, and the chart gallery: **[dkkung.github.io/dysonsphere](https://dkkung.github.io/dysonsphere/)**
