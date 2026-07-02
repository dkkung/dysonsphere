---
title: Getting started
description: Install dysonsphere and make your first themed chart.
---

## Install

```sh
pip install dysonsphere
```

dysonsphere is an [Altair](https://altair-viz.github.io/) companion: its functions return
native Altair objects, so you keep Altair's full API and compose dysonsphere's additions with
`+`.

## Your first chart

```python
import polars as pl
import altair as alt
import dysonsphere as ds

ds.theme(palette="blues")

df = pl.DataFrame({"group": ["A", "B", "C", "D"], "value": [3.0, 5.0, 2.0, 6.0]})

chart = (
    alt.Chart(df)
    .mark_bar()
    .encode(x="group:N", y="value:Q", color=alt.Color("group:N", legend=None))
)
```

`ds.theme()` registers a global Altair theme, so every chart afterwards inherits perceptually
uniform palettes and publication-ready styling. Set the palette (or any theme option) once;
override per chart as usual with Altair encodings.

## Saving

```python
ds.save(chart, "figure")   # writes figure.svg + figure.json by default
```

`save()` also bakes provenance, theme, and (when present) statistics into the file, which
`ds.read()` and `ds.load()` can pull back out later.

## Try it live

Want to experiment without installing anything? The [live playground](/playground.html) runs
dysonsphere in your browser via WebAssembly - edit the code and see the chart update.
