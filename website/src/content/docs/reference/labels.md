---
title: "Display labels"
description: "Map raw data values to display labels on axes, legends, and headers."
sidebar:
  order: 6
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

Display-label helpers: map raw data values to presentable labels at render time.

## `label_expr`

```python
label_expr(mapping: Mapping[Any, str | list[str]]) -> str
```

Build a Vega ``labelExpr`` that maps raw data values to display labels.

The common Altair pain: the dataframe holds machine values (``metadata_group1``)
but the plot needs presentable labels (``group 1``), and hand-writing the Vega
expression is tedious and quoting-fragile. This returns that expression for you::

    expr = ds.label_expr({"metadata_group1": "group 1", "metadata_group2": "group 2"})
    alt.X("treatment:N", axis=alt.Axis(labelExpr=expr))

The same string works everywhere Vega-Lite accepts a label expression: axis tick
labels (``alt.Axis(labelExpr=)``), legend entries (``alt.Legend(labelExpr=)``),
and facet headers (``alt.Header(labelExpr=)``). Only the rendered labels change -
the data, exported JSON, checksums, and statistics records keep the raw values.

**Parameters**

- **`mapping`** (`Mapping[Any, str | list[str]]`) - ``{raw_value: label}``. Keys may be strings or numbers (compared against ``datum.value``). A label may be a single string, or a **list of strings for a multi-line label** (each list item renders as one line). Values not present in the mapping fall back to the raw value; map a value to ``""`` to hide it.

**Returns**

- `str` - A Vega expression - a ternary chain, e.g. ``"datum.value == 'a' ? 'A' : datum.value == 'b' ? 'B' : datum.value"``. (A ternary chain rather than the object-lookup idiom ``{...}[datum.value] || datum.value``, whose ``||`` fallback silently misfires for falsy labels like ``""`` or ``0``.)

**Examples**

```python
::

    labels = {"tnf_10ng": ["TNF-α", "(10 ng/mL)"], "ctrl": "Control"}  # multi-line + plain
    chart = alt.Chart(df).mark_point().encode(
        x=alt.X("treatment:N", axis=alt.Axis(labelExpr=ds.label_expr(labels))),
        color=alt.Color("treatment:N", legend=alt.Legend(labelExpr=ds.label_expr(labels))),
        y="value:Q",
    )
```
