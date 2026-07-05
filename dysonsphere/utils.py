import hashlib
import json
from typing import Any, NamedTuple

import polars as pl


class BandGeometry(NamedTuple):
    """Pixel geometry of an n-category band axis - see :func:`band_geometry`."""

    step: float
    centers: tuple[float, ...]
    starts: tuple[float, ...]
    ends: tuple[float, ...]


def band_geometry(
    n: int,
    span: float | None = None,
    *,
    scale: str = "offset",
    bandPadding: float | None = None,
) -> BandGeometry:
    """
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

    Parameters
    ----------
    n:
        Number of categories.
    span:
        Pixel extent of the axis. ``None`` (default) reads ``chartWidth`` from the
        active theme (pass ``chartHeight`` explicitly for a y-axis).
    scale:
        ``"offset"``, ``"band"``, or ``"point"`` (see above).
    bandPadding:
        Band padding fraction. ``None`` (default) reads the active theme.

    Returns
    -------
    BandGeometry
        A named tuple ``(step, centers, starts, ends)``, each position list in
        category-index order.
    """
    import altair as alt

    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    if span is None:
        span = alt.theme.options.get("chartWidth", 100)
    if bandPadding is None:
        bandPadding = alt.theme.options.get("bandPadding", 0.1)
    bp = bandPadding
    if scale == "offset":
        step = span / (n + 2 * bp)
        centers = tuple(step * (bp + i + 0.5) for i in range(n))
        starts = tuple(step * (bp + i) for i in range(n))
        ends = tuple(step * (bp + i + 1) for i in range(n))
    elif scale == "band":
        step = span / (n + bp)
        centers = tuple(step * (0.5 + bp / 2 + i) for i in range(n))
        starts = tuple(step * (bp + i) for i in range(n))
        ends = tuple(step * (bp + i) + step * (1 - bp) for i in range(n))
    elif scale == "point":
        step = span / n
        centers = tuple(step * (0.5 + i) for i in range(n))
        starts = ends = centers
    else:
        raise ValueError(f"scale must be 'offset', 'band', or 'point', got {scale!r}")
    return BandGeometry(step, centers, starts, ends)


def count_n(df: pl.DataFrame, xCol: str, categories: list[str]) -> list[int]:
    """
    Count the number of rows in ``df`` belonging to each category.

    Parameters
    ----------
    df:
        A ``polars.DataFrame`` or ``pandas.DataFrame``.
    xCol:
        Column name used for grouping (the x-axis column).
    categories:
        Ordered list of category labels; the returned counts follow this order.
        Categories with no matching rows return 0.

    Returns
    -------
    list[int]
        Per-category row counts in the same order as ``categories``.

    Examples
    --------
    ::

        counts = ds.count_n(df, "group", ["Control", "Group A", "Group B"])
        # [12, 15, 11]
    """
    df = ensure_polars(df)
    return [len(df.filter(pl.col(xCol) == cat)) for cat in categories]


def ensure_polars(df: pl.DataFrame) -> pl.DataFrame:
    """
    Convert a pandas DataFrame to Polars, or pass a Polars DataFrame through unchanged.

    Accepts either a ``polars.DataFrame`` or a ``pandas.DataFrame`` without
    requiring pandas as a hard dependency — the check is done via the module
    name only.  If ``df`` is neither, a ``TypeError`` is raised.

    Parameters
    ----------
    df:
        A ``polars.DataFrame`` or ``pandas.DataFrame``.

    Returns
    -------
    polars.DataFrame
        The original DataFrame if already Polars, otherwise the result of
        ``polars.from_pandas(df)``.

    Examples
    --------
    ::

        import pandas as pd
        pdf = pd.DataFrame({"group": ["A", "B"], "value": [1.0, 2.0]})
        pldf = ds.ensure_polars(pdf)  # returns a polars.DataFrame
    """
    if isinstance(df, pl.DataFrame):
        return df
    if type(df).__module__.startswith("pandas"):
        return pl.from_pandas(df)
    raise TypeError(f"Expected a polars.DataFrame or pandas.DataFrame, got {type(df).__name__}.")


def _hash_rows(rows: list[dict]) -> str:
    """Order-independent ``sha256:<hex>`` of a list of record dicts.

    Hashes the *multiset* of per-row canonical-JSON digests (sort the digests, then hash), so a
    reordered-but-identical set yields the same value; duplicate rows are preserved.  The single
    implementation shared by the provenance ``dataChecksum`` (over a spec's inlined datasets) and
    ``frame_checksum`` (over a raw dataframe), so both compute identical values for identical rows.
    ``default=str`` keeps it total for non-JSON-native cell types (dates, Decimals); JSON-native
    values are unaffected, so the provenance path is byte-identical to before.
    """
    digests = sorted(
        hashlib.sha256(
            json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()
        ).hexdigest()
        for r in rows
    )
    return "sha256:" + hashlib.sha256(json.dumps(digests, separators=(",", ":")).encode()).hexdigest()


def frame_checksum(df: "pl.DataFrame | Any") -> str:
    """Order-independent ``sha256:<hex>`` fingerprint of a dataframe's rows.

    Same algorithm as the provenance ``dataChecksum`` (via :func:`_hash_rows`), so identical
    content in any row order yields the same value.  Used to tag a statistics record with the
    identity of the dataframe it was computed from, so records from distinct dataframes are
    distinguishable (and identical-content frames match regardless of ordering).
    """
    return _hash_rows(ensure_polars(df).to_dicts())


# ── Internal-data sentinel ───────────────────────────────────────────────────
# dysonsphere's composite marks / annotations generate their own small "sidecar" data
# (bracket coords, mean/error bars, KDE curves, labels, …).  Altair inlines each of those
# as a separate named dataset in the saved spec, alongside the user's dataframe.  To let
# export.read(what="data") return only the USER's frame(s), every internal data source is
# tagged with this sentinel column; read() treats any dataset carrying it as internal.
#
# DISCIPLINE: any NEW code that builds a dysonsphere-generated data source for a chart layer
# MUST route it through `_internal_data(...)` (i.e. `alt.Chart(_internal_data(rows_or_df))`).
# Miss one, and that sidecar leaks as a phantom "user" dataframe on read.  See CLAUDE.md.
_INTERNAL_COL = "__dysonsphere__"


def _internal_data(data: "list[dict] | pl.DataFrame | Any") -> "Any":
    """Tag dysonsphere-generated (non-user) chart data with the internal sentinel column.

    Accepts a list of record dicts (returned as an ``alt.Data``) or a polars/pandas
    DataFrame (returned as a polars DataFrame with the sentinel column added).  Pass the
    result straight to ``alt.Chart(...)``.
    """
    import altair as alt

    if isinstance(data, list):
        return alt.Data(values=[{**dict(row), _INTERNAL_COL: 1} for row in data])
    return ensure_polars(data).with_columns(pl.lit(1).alias(_INTERNAL_COL))
