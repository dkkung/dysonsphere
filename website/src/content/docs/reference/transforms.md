---
title: "Transforms"
description: "Data transforms for jittered and beeswarm x-offsets."
sidebar:
  order: 15
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

## `add_beeswarm`

```python
def add_beeswarm(
    df: pl.DataFrame | Any,
    yCol: str,
    groupBy: list[str],
    heightPx: int | None = None,
    spread: float | None = None,
    outCol: str = 'beeswarm_x',
) -> pl.DataFrame: ...
```

Add a swarm beeswarm x-offset column to a Polars DataFrame, computed per group.

Wraps :func:`_beeswarm_offsets` (the greedy exact-collision "swarm" layout, R
ggbeeswarm's ``geom_beeswarm(method="swarm")``): every point is guaranteed
non-overlapping. The trade is that tightly-packed rows can look lopsided (an
even-count row parks a point on the tick, lone points get pushed to one side) -
inherent to the swarm algorithm. For a symmetric, density-shaped alternative that
allows mild overlap, see :func:`add_quasirandom`.

``spread`` is the collision radius in pixels - set it to roughly half the rendered
point diameter for non-overlapping points. The total horizontal width is emergent
and grows with n.

**Parameters**

- **`df`** (`pl.DataFrame | Any`) - Input DataFrame.
- **`yCol`** (`str`) - Name of the column containing y values.
- **`groupBy`** (`list[str]`) - Column name(s) that define each beeswarm group.
- **`heightPx`** (`int | None`) - Chart height in pixels. Defaults to the theme's ``chartHeight``.
- **`spread`** (`float | None`) - Collision radius in pixels. Defaults to ``sqrt(markSize / π)`` from the active theme, so points naturally match the rendered mark size.
- **`outCol`** (`str`) - Name of the output offset column added to the DataFrame.

**Returns**

- `polars.DataFrame` - Original DataFrame with an additional ``outCol`` column.

**Examples**

```python
::

    df = ds.add_beeswarm(df, yCol="value", groupBy=["group"])

    alt.Chart(df).mark_circle().encode(
        x=alt.X("group:N"),
        y=alt.Y("value:Q"),
        xOffset=alt.XOffset("beeswarm_x:Q"),
    )
```

## `add_quasirandom`

```python
def add_quasirandom(
    df: pl.DataFrame | Any,
    yCol: str,
    groupBy: list[str],
    heightPx: int | None = None,
    spread: float | None = None,
    outCol: str = 'quasirandom_x',
    width: float | None = None,
    bandwidth: float | None = None,
) -> pl.DataFrame: ...
```

Add a quasirandom x-offset column to a Polars DataFrame, computed per group.

Wraps :func:`_quasirandom_offsets` - a density-scaled quasirandom spread (van der
Corput low-discrepancy sequence weighted by a Gaussian KDE), R ggbeeswarm's
``geom_quasirandom``. It gives a symmetric, violin-shaped swarm that stays centred
on the tick, sidestepping :func:`add_beeswarm`'s lopsided tightly-packed rows. Fully
deterministic (no RNG), so figures reproduce. The trade is that it does NOT guarantee
non-overlap - the cost of the smoother, symmetric look. It is the better choice for
large or heavily-tied groups; use :func:`add_beeswarm` for small groups where exact
non-overlap matters.

**Parameters**

- **`df`** (`pl.DataFrame | Any`) - Input DataFrame.
- **`yCol`** (`str`) - Name of the column containing y values.
- **`groupBy`** (`list[str]`) - Column name(s) that define each group.
- **`heightPx`** (`int | None`) - Chart height in pixels. Defaults to the theme's ``chartHeight``.
- **`spread`** (`float | None`) - Point radius in pixels - the unit the auto ``width`` is built from. Defaults to ``sqrt(markSize / π)`` from the active theme, matching :func:`add_beeswarm`.
- **`outCol`** (`str`) - Name of the output offset column added to the DataFrame.
- **`width`** (`float | None`) - Peak half-width of the swarm in pixels. ``None`` (default) auto-sizes it to the swarm's footprint (see :func:`_quasirandom_offsets`).
- **`bandwidth`** (`float | None`) - KDE bandwidth (``gaussian_kde`` ``bw_method``). ``None`` (default) uses Scott's rule.

**Returns**

- `polars.DataFrame` - Original DataFrame with an additional ``outCol`` column.

**Examples**

```python
::

    df = ds.add_quasirandom(df, yCol="value", groupBy=["group"])

    alt.Chart(df).mark_circle().encode(
        x=alt.X("group:N"),
        y=alt.Y("value:Q"),
        xOffset=alt.XOffset("quasirandom_x:Q"),
    )
```

## `add_jitter`

```python
def add_jitter(
    df: pl.DataFrame | Any,
    spread: float | None = None,
    outCol: str = 'jitter_x',
    seed: int | None = 20220701,
) -> pl.DataFrame: ...
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
