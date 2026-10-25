---
title: "Reading exports"
description: "Read exports, verify figures, and compute data checksums."
sidebar:
  order: 10
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

Access these helpers through `ds.metadata`.

## `frame_checksum`

Call as `ds.metadata.frame_checksum(...)`.

```python
def frame_checksum(data: pl.DataFrame | pd.DataFrame) -> str: ...
```

Order-independent ``multiset-sha256:<hex>`` fingerprint of a dataframe's rows.

Same algorithm as the provenance ``dataChecksum`` (via :func:`_hash_rows`), so identical
content in any row order yields the same value.  Used to tag a statistics record with the
identity of the dataframe it was computed from, so records from distinct dataframes are
distinguishable (and identical-content frames match regardless of ordering).

## `read`

Call as `ds.metadata.read(...)`.

```python
def read(
    path: str | Path,
    *,
    what: str = 'report',
    saveReport: bool | str | Path = False,
    output: str = 'polars',
    dataset: str | None = None,
) -> Any: ...
```

Read back descriptions, metadata, or data saved in a PNG, SVG, TIFF, or JSON.

**Parameters**

- **`path`** (`str | Path`) - A dysonsphere-exported ``.png``, ``.svg``, ``.tiff``/``.tif``, or ``.json`` file.
- **`what`** (`str`) - Which artifact to return: - ``'report'`` (default) – the human-readable report **table** as a ``str``; it is printed to stdout and returned. Joins every section of the ``report`` container (``statistics`` + ``provenance``). Falls back to re-rendering the statistics from the embedded records if the prose wasn't saved (``embedReport=False``). - ``'statistics'`` – the structured **records** (list of dicts, exact floats). - ``'metadata'`` – the whole ``{provenance, statistics, theme, report}`` dict, where ``report`` is the ``{section: text}`` container. - ``'description'`` – the user's description text, without printing it. Works even with ``saveMetadata=False`` and returns ``None`` when absent. Empty strings, Unicode, and line endings are preserved. Does not require or verify structured metadata. - ``'data'`` – the **original data** Altair inlined into the spec (the whole frame, including columns the chart never plotted). **JSON only** (PNG/SVG/TIFF don't carry the data). The form is chosen by ``output``.
- **`saveReport`** (`bool | str | Path`) - Only for ``what='report'``: ``True`` writes the report to a ``.txt`` in the cwd; a path writes to that directory.
- **`output`** (`str`) - Only for ``what='data'`` – the form to return the data in: ``'polars'`` (default) → ``pl.DataFrame``; ``'pandas'`` → ``pd.DataFrame``; ``'duckdb'`` → a ``DuckDBPyRelation``; ``'records'`` → the raw ``list[dict]`` (no dataframe library needed). ``pandas`` and ``duckdb`` are imported lazily and are not package dependencies.

**Returns**

- `str, None, list[dict[str, Any]], dict[str, Any], or dataframe-like object` - The result selected by ``what`` and, for ``what='data'``, by ``output`` and ``dataset``.

## `verify`

Call as `ds.metadata.verify(...)`.

```python
def verify(
    figure: Any,
    data: pl.DataFrame | pd.DataFrame | list[pl.DataFrame | pd.DataFrame] | tuple[pl.DataFrame | pd.DataFrame, ...] | None = None,
    *,
    what: str | tuple[str, ...] | list[str] = _COMPARE_KEYS,
) -> VerifyResult: ...
```

Check a saved figure's embedded checksums and optionally compare it with data.

For one figure, ``specValid`` reports whether the JSON spec matches its recorded
``vegaliteChecksum``. SVG, PNG, and TIFF files contain metadata but not the full spec, so
``specValid`` is ``None`` for those formats. When ``data`` is supplied, each frame's
checksum is compared with the recorded ``dataChecksum``. This works for all supported
formats and ignores both row order within a frame and the order of supplied frames.

``exportIdentifier`` is reported but not checked. It is a random UUID per ``save()``
call, or, under ``SOURCE_DATE_EPOCH``, a content-derived identifier that can be shared
by separate saves with identical inputs. Compare export identifiers for a match;
compare ``vegaliteChecksum`` to check whether files contain the same chart.

A file without its metadata cannot be checked and raises an error. Its data can still
be compared with another export if an independent checksum is available:
``frame_checksum(data)`` returns the same value for the same rows.

Passing a list compares figures instead of checking one. Each entry may be a saved
file or an in-memory chart. ``what`` selects ``"spec"`` (same chart), ``"data"``
(same data), or ``"save"`` (same ``save()`` call); it defaults to all three.
``matches`` reports whether all figures agree for each selected identity, and
``groups`` assigns a number to each identity. An in-memory chart has no ``save``
identity, so that comparison is ``None`` for the whole call.

List comparisons use the identities recorded by each file. An edited file is compared
as the chart it claims to contain; checking one file's own spec checksum detects edits.

**Parameters**

- **`figure`** (`Any`) - A dysonsphere-exported ``.png``, ``.svg``, ``.tiff``/``.tif``, or ``.json`` to check, or a list of figures to compare, each a path or an Altair chart.
- **`data`** (`pl.DataFrame | pd.DataFrame | list[pl.DataFrame | pd.DataFrame] | tuple[pl.DataFrame | pd.DataFrame, ...] | None`) - Optional dataframe, or list of dataframes, that the figure should have been built from. Polars or pandas. Omit to check only the spec.
- **`what`** (`str | tuple[str, ...] | list[str]`) - Which questions to ask when comparing a list: any of ``"spec"``, ``"data"``, ``"save"``. Defaults to all three. Ignored when checking a single figure.

**Returns**

- `VerifyResult` - ``.ok`` is ``True`` when every check that ran passed. ``specValid``/``dataMatches`` are ``None`` for checks that could not run.

**Examples**

```python
::

    ds.metadata.verify("fig.json").ok                 # untampered?
    ds.metadata.verify("fig.png", data=data).dataMatches  # built from this data?
    ds.metadata.verify("fig.json", data=[counts, meta]) # multi-frame chart
```
