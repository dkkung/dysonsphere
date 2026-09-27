# Tables, condition rows, and offset transforms

Read this for result tables, categorical condition annotations, or custom point offsets. Examples
use synthetic data, run independently, write to the current directory, and keep Dysonsphere's
built-in export formats and raster density.

## Styled result tables

`ds.mark_table(data, ...)` returns a self-sized Altair layer that can be composed with charts or
other tables. Use `columns` to select and order displayed fields, `headerLabels` for display-only
column labels, `columnFormat` for numeric formatting, and `cellPalette` for value shading. Table
missing values render as blank cells without removing their rows or changing the source dataframe.
A cell palette maps values in its column; a diverging palette is centered at zero.

```python
# example: table
import polars as pl

import dysonsphere as ds

data = pl.DataFrame({
    "target": ["A", "B", "C"],
    "log2FC": [1.2, -0.8, 0.1],
    "pvalue": [0.01, 0.12, 0.72],
})
ds.theme(fontSize=7)
table = ds.mark_table(
    data,
    columns=["target", "log2FC", "pvalue"],
    headerLabels={"target": "Target"},
    columnFormat={"log2FC": ".2f", "pvalue": "scientific"},
    cellPalette={"log2FC": "pinksblues"},
    strokes=("outer", "header", "rows"),
)
ds.save(table, "skill_table")
```

## Condition and sample-size rows

`ds.add_multilabel(chart, groups, categories=...)` returns a vertical composition. It replaces the
chart's x-axis labels with a table aligned to the ordered categories. Each `groups` row has one
value per category; boolean values work well with `style="symbol"`. Use `showSampleSize=True` with
`data` and `x` to calculate a row of group counts. Avoid showing a sample-size row if the categories
or plotted subset do not match those counts.

```python
# example: multilabel
import altair as alt
import polars as pl

import dysonsphere as ds

data = pl.DataFrame({
    "condition": ["Control"] * 4 + ["Dose A"] * 4 + ["Dose B"] * 4,
    "response": [0.9, 1.1, 1.0, 1.4, 1.5, 1.7, 1.9, 2.1, 2.0, 2.2, 2.3, 2.5],
})
categories = ["Control", "Dose A", "Dose B"]
ds.theme(width=180, height=120)
chart = alt.Chart(data).mark_circle().encode(
    x=alt.X("condition:N", sort=categories, title=None),
    y=alt.Y("response:Q", title="Response (a.u.)"),
)
figure = ds.add_multilabel(
    chart,
    groups={"Drug present": [False, True, True]},
    categories=categories,
    showSampleSize=True,
    data=data,
    x="condition",
    style="symbol",
    categoryLabel=True,
)
ds.save(figure, "skill_multilabel")
```

## Custom point offsets

For standard distribution plots, `ds.mark_strip(..., scatter="beeswarm")` is usually the shorter
choice. Use `ds.transforms` when you need to build your own Altair encoding:

- `beeswarm(data, column=..., groupBy=...)` adds a deterministic x-offset column and avoids point
overlap, but a tightly packed group can look asymmetric. Its layout depends on chart height.
- `quasirandom(...)` adds deterministic, symmetric offsets shaped by a Gaussian KDE. Points can
  overlap; it can be more balanced for large or heavily tied groups.
- `jitter(data, spread=...)` adds seeded random Gaussian offsets in pixels. It does not avoid
  overlap and is not a substitute for measured x-values.

Offset magnitudes use pixels. Pin an `xOffset` scale to a symmetric domain so the category tick stays
centered, and recalculate the transform if chart geometry or point sizes change. Do not add offsets
to the source measurement column.

```python
# example: quasirandom
import altair as alt
import polars as pl

import dysonsphere as ds

data = pl.DataFrame({
    "condition": ["Control"] * 8 + ["Treatment"] * 8,
    "response": [1.0, 1.1, 1.3, 1.5, 1.5, 1.8, 2.0, 2.1, 1.2, 1.4, 1.6, 1.6, 1.9, 2.2, 2.4, 2.8],
})
categories = ["Control", "Treatment"]
ds.theme(width=180, height=130)
points = ds.transforms.quasirandom(data, column="response", groupBy=["condition"])
max_offset = points["quasirandom_x"].abs().max()
chart = alt.Chart(points).mark_circle().encode(
    x=alt.X("condition:N", sort=categories, title="Condition"),
    y=alt.Y("response:Q", title="Response (a.u.)"),
    xOffset=alt.XOffset(
        "quasirandom_x:Q",
        scale=alt.Scale(domain=[-max_offset, max_offset]),
    ),
)
ds.save(chart, "skill_quasirandom")
```

## Preserve analysis and data

Tables and condition rows describe the dataframe given to them; they do not establish a statistical
comparison or fix mismatched subsets. Compute a descriptive summary only when the user asks for it
or it is needed to interpret the figure. Check category order and sample counts against the plotted
observations. For statistical annotations, read [the statistics reference](statistics.md).
