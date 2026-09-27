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

Read back the metadata (or data) embedded by :func:`save` from a PNG, SVG, or JSON.

**Parameters**

- **`path`** (`str | Path`) - A dysonsphere-exported ``.png``, ``.svg``, or ``.json`` file.
- **`what`** (`str`) - Which artifact to return: - ``'report'`` (default) — the human-readable report **table** as a ``str``; it is printed to stdout and returned. Joins every section of the ``report`` container (``statistics`` + ``provenance``). Falls back to re-rendering the statistics from the embedded records if the prose wasn't saved (``embedReport=False``). - ``'statistics'`` — the structured **records** (list of dicts, exact floats). - ``'metadata'`` — the whole ``{provenance, statistics, theme, report}`` dict, where ``report`` is the ``{section: text}`` container. - ``'data'`` — the **original data** Altair inlined into the spec (the whole frame, including columns the chart never plotted). **JSON only** (PNG/SVG don't carry the data). The form is chosen by ``output``.
- **`saveReport`** (`bool | str | Path`) - Only for ``what='report'``: ``True`` writes the report to a ``.txt`` in the cwd; a path writes to that directory.
- **`output`** (`str`) - Only for ``what='data'`` — the form to return the data in: ``'polars'`` (default) → ``pl.DataFrame``; ``'pandas'`` → ``pd.DataFrame``; ``'duckdb'`` → a ``DuckDBPyRelation``; ``'records'`` → the raw ``list[dict]`` (no dataframe library needed). ``pandas`` and ``duckdb`` are imported lazily and are not package dependencies.

**Returns**

- `str, list[dict[str, Any]], dict[str, Any], or dataframe-like object` - The result selected by ``what`` and, for ``what='data'``, by ``output`` and ``dataset``.

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

Check a saved figure against its own embedded checksums, and optionally against its data.

Two independent questions, neither of which needs the original script:

- **Is the file internally consistent?**  The spec is re-hashed and compared with the
  recorded ``vegaliteChecksum``, so an edited spec is detectable.  JSON only - SVG and PNG
  embed the metadata block but not the full spec, so ``specValid`` is ``None`` for them.
- **Did this figure come from this data?**  Pass ``data`` and each frame's checksum is
  compared with the recorded ``dataChecksum``.  This works for **all three formats**, since
  the checksums travel in the metadata block, and it is order-independent in both senses:
  row order within a frame does not matter, nor does the order frames are passed in.

``exportIdentifier`` is reported, never checked.  It is a random UUID per ``save()`` call, or
- under ``SOURCE_DATE_EPOCH`` - one derived from the figure's own content, in which case two
saves of identical inputs share it by design.  Compare it across two files to ask whether they
came from one save; compare ``vegaliteChecksum`` to ask whether they are the same chart.

A file whose metadata is gone - screenshotted, or re-saved by a tool that drops it - cannot
be checked at all: there is nothing to compare against, and this raises.  What survives is the
trail for the DATA, because these checksums are recomputed from content rather than minted per
file.  ``frame_checksum(data)`` returns the same value for the same rows forever, so a dataframe
can still be matched against an intact sibling export or a checksum recorded elsewhere.

Passing a **list** compares figures instead of checking one.  Each may be a saved file or a
chart still in memory, in any mix.  ``what`` selects the questions - ``"spec"`` (the same
chart, however it was exported), ``"data"`` (built from the same data), ``"save"`` (produced by
one ``save()`` call) - and defaults to all three.  ``matches`` says whether every figure agrees
on each; ``groups`` numbers them, so the same number means the same figure.  A chart in memory
has no ``save`` identity, so that question comes back ``None`` for the whole call.

Comparing reads what each file RECORDED, which is what lets a PNG be compared with a JSON -
but it means an edited file still compares as the chart it claims to be.  Checking one figure
on its own is what detects an edit; the two questions are deliberately separate.

**Parameters**

- **`figure`** (`Any`) - A dysonsphere-exported ``.png``, ``.svg``, or ``.json`` to check - or a list of figures to compare, each a path or an Altair chart.
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
