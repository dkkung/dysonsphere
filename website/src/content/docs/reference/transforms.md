---
title: "Transforms"
description: "Data transforms for jittered and beeswarm x-offsets."
sidebar:
  order: 2
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

## `add_beeswarm`

```python
add_beeswarm(
    df: pl.DataFrame | Any,
    yCol: str,
    groupBy: list[str],
    heightPx: int | None = None,
    spread: float | None = None,
    outCol: str = 'beeswarm_x',
) -> pl.DataFrame
```

Add a beeswarm x-offset column to a Polars DataFrame, computed per group.

A convenience wrapper around :func:`_beeswarm_offsets` that handles the
``with_row_index`` / ``map_groups`` / ``sort`` / ``drop`` pattern.

``spread`` is the collision radius in pixels — set it to roughly half the
rendered point diameter for non-overlapping points.  The total horizontal
width of the beeswarm grows with n.

**Parameters**

- **`df`** (`pl.DataFrame | Any`) - Input DataFrame.
- **`yCol`** (`str`) - Name of the column containing y values.
- **`groupBy`** (`list[str]`) - Column name(s) that define each beeswarm group.
- **`heightPx`** (`int | None`) - Chart height in pixels.
- **`spread`** (`float | None`) - Collision radius in pixels. Defaults to ``sqrt(markSize / π)`` from the active theme, so points naturally match the rendered mark size.
- **`outCol`** (`str`) - Name of the output offset column added to the DataFrame.

**Returns**

- `polars.DataFrame` - Original DataFrame with an additional ``outCol`` column.

**Examples**

```python
::

    df = ds.add_beeswarm(df, yCol="value", groupBy=["group"], spread=2.0)

    alt.Chart(df).mark_circle().encode(
        x=alt.X("group:N"),
        y=alt.Y("value:Q"),
        xOffset=alt.XOffset("beeswarm_x:Q"),
    )
```

## `add_jitter`

```python
add_jitter(
    df: pl.DataFrame | Any,
    spread: float | None = None,
    outCol: str = 'jitter_x',
    seed: int | None = 20220701,
) -> pl.DataFrame
```

Add a column of random Gaussian x-offsets to a Polars DataFrame.

Each offset is drawn independently from N(0, spread²), where ``spread``
is the standard deviation in pixels.  ~68% of points fall within
±spread of centre; ~95% within ±2·spread.  There is no collision
avoidance — points can overlap.  Use :func:`add_beeswarm` instead for
small n where overlap is undesirable.

**Parameters**

- **`df`** (`pl.DataFrame | Any`) - Input DataFrame.
- **`spread`** (`float | None`) - Standard deviation of the jitter in pixels. Defaults to ``min(chartWidth, chartHeight) / 50`` from the active theme (2.0 at the default 100×100 chart size).
- **`outCol`** (`str`) - Name of the output offset column added to the DataFrame.
- **`seed`** (`int | None`) - Optional random seed for reproducibility.

**Returns**

- `polars.DataFrame` - Original DataFrame with an additional ``outCol`` column.

**Examples**

```python
::

    df = ds.add_jitter(df, spread=5)

    alt.Chart(df).mark_circle().encode(
        x=alt.X("group:N"),
        y=alt.Y("value:Q"),
        xOffset=alt.XOffset("jitter_x:Q"),
    )
```
