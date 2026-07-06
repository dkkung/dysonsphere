---
title: "Reading exports"
description: "Read embedded metadata, statistics, reports, and data back out of exports."
sidebar:
  order: 9
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

## `read`

```python
read(path: str, *, what: str = 'report', save: bool | str = False, output: str = 'polars', dataset: str | None = None)
```

Read back the metadata (or data) embedded by :func:`save` from a PNG, SVG, or JSON.

**Parameters**

- **`path`** (`str`) - A dysonsphere-exported ``.png``, ``.svg``, or ``.json`` file.
- **`what`** (`str`) - Which artifact to return: - ``'report'`` (default) — the human-readable report **table** as a ``str``; it is printed to stdout and returned. Joins every section of the ``report`` container (``statistics`` + ``provenance``). Falls back to re-rendering the statistics from the embedded records if the prose wasn't saved (``embedReport=False``). - ``'statistics'`` — the structured **records** (list of dicts, exact floats). - ``'metadata'`` — the whole ``{provenance, statistics, theme, report}`` dict, where ``report`` is the ``{section: text}`` container. - ``'data'`` — the **original data** Altair inlined into the spec (the whole frame, including columns the chart never plotted). **JSON only** (PNG/SVG don't carry the data). The form is chosen by ``output``.
- **`save`** (`bool | str`) - Only for ``what='report'``: ``True`` writes the report to a ``.txt`` in the cwd; a string writes to that directory.
- **`output`** (`str`) - Only for ``what='data'`` — the form to return the data in: ``'polars'`` (default) → ``pl.DataFrame``; ``'pandas'`` → ``pd.DataFrame``; ``'duckdb'`` → a ``DuckDBPyRelation``; ``'records'`` → the raw ``list[dict]`` (no dataframe library needed). ``pandas`` and ``duckdb`` are imported lazily and are not package dependencies.
