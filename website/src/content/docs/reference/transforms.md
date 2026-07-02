---
title: "Transforms"
description: "Data transforms for jittered and beeswarm x-offsets."
sidebar:
  order: 7
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

## `beeswarm_offsets`

```python
beeswarm_offsets(yVals, heightPx: int | None = None, spread: float | None = None)
```

Compute x offsets (pixels) for a beeswarm plot using collision avoidance.

**Parameters**

- **`yVals`** - Array of y values for one group.
- **`heightPx`** (`int | None`) - Chart height in pixels. Should match ``.properties(height=...)``.
- **`spread`** (`float | None`) - Collision radius in pixels. Points are placed so no two centres are closer than ``2 * spread``. Defaults to 2.0.
- **`step`** - x step size (px) between candidate positions. Defaults to ``spread`` so the candidate grid aligns with the point diameter.

**Returns**

- `numpy.ndarray` - x offsets in pixels, one per input value, in the same order.

**Examples**

```python
Compute offsets per group with Polars then plot in Altair::

    df = (
        df
        .with_row_index("__idx")
        .group_by(["group", "time"])
        .map_groups(lambda g: g.with_columns(
            pl.Series("beeswarm_x", ds.beeswarm_offsets(
                g["value"].to_numpy(),
                heightPx=200,
                spread=2.0,
            ))
        ))
        .sort("__idx")
        .drop("__idx")
    )

    alt.Chart(df).mark_circle().encode(
        x=alt.X("time:O"),
        y=alt.Y("value:Q"),
        xOffset=alt.XOffset("beeswarm_x:Q"),
    )
```

## `add_beeswarm`

```python
add_beeswarm(df: pl.DataFrame | Any, yCol: str, groupBy: list[str], heightPx: int | None = None, spread: float | None = None, outCol: str = 'beeswarm_x')
```

Add a beeswarm x-offset column to a Polars DataFrame, computed per group.

A convenience wrapper around :func:`beeswarm_offsets` that handles the
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
add_jitter(df: pl.DataFrame | Any, spread: float | None = None, outCol: str = 'jitter_x', seed: int | None = 20220701)
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
