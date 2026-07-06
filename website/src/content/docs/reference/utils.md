---
title: "Utilities"
description: "Shared helpers: DataFrame handling, counts, band geometry, checksums."
sidebar:
  order: 15
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

## `band_geometry`

```python
band_geometry(
    n: int,
    span: float | None = None,
    *,
    scale: str = 'offset',
    bandPadding: float | None = None,
) -> BandGeometry
```

Compute the pixel geometry of an ``n``-category band axis - the single source of
truth for dysonsphere's band-position math (violin centres, shade rects, bracket
midpoints, multilabel spans).

Vega-Lite lowers a nominal axis to a D3 band scale whose step size depends on the
padding configuration, which differs by mark type. ``scale`` picks the variant:

- ``"offset"`` (default) - ``paddingInner=0``, ``paddingOuter=bandPadding``: what an
  ``xOffset`` encoding (``mark_circle``/``mark_strip``) or an ``add_shade`` rect sees.
  ``step = span / (n + 2*bandPadding)``; band ``i`` spans
  ``[step*(bandPadding+i), step*(bandPadding+i+1)]``.
- ``"band"`` - ``paddingInner=paddingOuter=bandPadding``: what ``mark_boxplot``
  (and so ``mark_violin``'s embedded boxplot) sees.
  ``step = span / (n + bandPadding)``; centre ``i`` is ``step*(0.5+bandPadding/2+i)``.
- ``"point"`` - a point scale: ``step = span / n``; centre ``i`` is ``step*(0.5+i)``
  (``starts``/``ends`` equal ``centers``).

**Parameters**

- **`n`** (`int`) - Number of categories.
- **`span`** (`float | None`) - Pixel extent of the axis. ``None`` (default) reads ``chartWidth`` from the active theme (pass ``chartHeight`` explicitly for a y-axis).
- **`scale`** (`str`) - ``"offset"``, ``"band"``, or ``"point"`` (see above).
- **`bandPadding`** (`float | None`) - Band padding fraction. ``None`` (default) reads the active theme.

**Returns**

- `BandGeometry` - A named tuple ``(step, centers, starts, ends)``, each position list in category-index order.

## `count_n`

```python
count_n(df: pl.DataFrame, xCol: str, categories: list[str]) -> list[int]
```

Count the number of rows in ``df`` belonging to each category.

**Parameters**

- **`df`** (`pl.DataFrame`) - A ``polars.DataFrame`` or ``pandas.DataFrame``.
- **`xCol`** (`str`) - Column name used for grouping (the x-axis column).
- **`categories`** (`list[str]`) - Ordered list of category labels; the returned counts follow this order. Categories with no matching rows return 0.

**Returns**

- `list[int]` - Per-category row counts in the same order as ``categories``.

**Examples**

```python
::

    counts = ds.count_n(df, "group", ["Control", "Group A", "Group B"])
    # [12, 15, 11]
```

## `ensure_polars`

```python
ensure_polars(df: pl.DataFrame) -> pl.DataFrame
```

Convert a pandas DataFrame to Polars, or pass a Polars DataFrame through unchanged.

Accepts either a ``polars.DataFrame`` or a ``pandas.DataFrame`` without
requiring pandas as a hard dependency — the check is done via the module
name only.  If ``df`` is neither, a ``TypeError`` is raised.

**Parameters**

- **`df`** (`pl.DataFrame`) - A ``polars.DataFrame`` or ``pandas.DataFrame``.

**Returns**

- `polars.DataFrame` - The original DataFrame if already Polars, otherwise the result of ``polars.from_pandas(df)``.

**Examples**

```python
::

    import pandas as pd
    pdf = pd.DataFrame({"group": ["A", "B"], "value": [1.0, 2.0]})
    pldf = ds.ensure_polars(pdf)  # returns a polars.DataFrame
```

## `frame_checksum`

```python
frame_checksum(df: pl.DataFrame | Any) -> str
```

Order-independent ``sha256:<hex>`` fingerprint of a dataframe's rows.

Same algorithm as the provenance ``dataChecksum`` (via :func:`_hash_rows`), so identical
content in any row order yields the same value.  Used to tag a statistics record with the
identity of the dataframe it was computed from, so records from distinct dataframes are
distinguishable (and identical-content frames match regardless of ordering).
