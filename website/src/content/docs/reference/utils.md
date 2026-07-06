---
title: "Utilities"
description: "Shared helpers for DataFrame handling and counts."
sidebar:
  order: 11
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

## `count_n`

```python
count_n(df: pl.DataFrame, xCol: str, categories: list[str])
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
ensure_polars(df: pl.DataFrame)
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
frame_checksum(df: pl.DataFrame | Any)
```

Order-independent ``sha256:<hex>`` fingerprint of a dataframe's rows.

Same algorithm as the provenance ``dataChecksum`` (via :func:`_hash_rows`), so identical
content in any row order yields the same value.  Used to tag a statistics record with the
identity of the dataframe it was computed from, so records from distinct dataframes are
distinguishable (and identical-content frames match regardless of ordering).
