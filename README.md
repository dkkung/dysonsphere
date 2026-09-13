<p align="center">
  <img src="https://raw.githubusercontent.com/dkkung/dysonsphere/main/docs/logo_with_text.svg" width="360" alt="dysonsphere" />
</p>

# dysonsphere

`dysonsphere` is an [`altair`](https://altair-viz.github.io/) utility library for scientific figures in Python. It provides:
- A consistent default configuration enabled with `ds.theme()`.
- Perceptually uniform palettes, including those from popular data visualization libraries.
- Shareable styles through a `dysonsphere.toml` config file.

It also provides utilities for `altair` charts:
- Layer annotations such as reference lines, shades, text, and data labels onto `altair` charts.
- Statistical inference with `scipy` through `ds.stats.comparisons()` and `ds.stats.correlation()`,
  layered onto `alt.Chart` and exported as metadata:
  - Omnibus tests with effect sizes.
  - Brackets and *p*-values for pairwise and post hoc comparisons.
  - Correlations with fit lines.
- Multilabels for categorical labels, such as multi-condition axes and sample sizes.
- Self-documenting exports for reproducible figures:
  - `ds.save()` writes corrected SVG, PNG, interactive HTML, and/or Vega-Lite JSON, and embeds
    provenance. Environment versions and SHA-256 checksums identify the Vega-Lite spec and data.
  - `ds.metadata.read()` recovers the statistics report, metadata, and original data from a saved figure.
  - `ds.load()` rebuilds the chart from its JSON.

Separate packages can add field-specific plotting toolkits (such as molecular biology or astronomy) that use the core theme, palettes, and export pipeline.

## Installation

```sh
# with pip
pip install dysonsphere

# with uv
uv pip install dysonsphere

# add as a project dependency
uv add dysonsphere
```

Requires Python 3.11+. Every function that takes a `DataFrame` accepts `polars` or `pandas`.

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

ds.save(chart, "myplot") # writes myplot.svg + myplot.json
```

## Documentation

Documentation, examples, palettes, and an interactive chart studio at **[dkkung.github.io/dysonsphere](https://dkkung.github.io/dysonsphere/)**

## Agent skill

The core [Dysonsphere skill](skills/README.md) provides plotting, statistical-annotation, and export
guidance for Claude Code, Codex, and OpenCode. It is installed separately from the Python library
and targets Dysonsphere 4.0.0. See its installation instructions and compatibility notes before
using it with a different release.
