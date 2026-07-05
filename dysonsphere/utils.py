import hashlib
import json
from typing import Any, NamedTuple

import polars as pl

from .theme import _opt


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

    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    if span is None:
        span = _opt("chartWidth")
    if bandPadding is None:
        bandPadding = _opt("bandPadding")
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


def _repel_labels(
    anchors: list[tuple[float, float]],
    sizes: list[tuple[float, float]],
    *,
    width: float,
    height: float,
    iterations: int = 300,
) -> list[tuple[float, float]]:
    """Force-directed, non-overlapping label placement (deterministic) - the engine behind
    :func:`add_labels`.

    ``anchors`` are the pixel positions of the points being labelled and ``sizes`` each label's
    ``(width, height)`` box in pixels (pixel origin top-left, y growing downward, matching a
    rendered SVG). Returns one label-CENTRE pixel position per anchor. Each label box repels the
    others (pushed apart along its axis of least penetration), a weak spring pulls it back toward
    its anchor, and it is clamped inside the ``width`` x ``height`` panel; iterated to a relaxed
    layout. Fully deterministic (no RNG - a tiny index-based offset breaks exact ties), so the
    same inputs always give the same figure. **Never drops a label** (force-show): in an
    impossibly dense region labels settle at their least-overlapping positions rather than
    disappearing.
    """
    import numpy as np

    n = len(anchors)
    if n == 0:
        return []
    a = np.array(anchors, dtype=float)
    half = np.array(sizes, dtype=float) / 2.0 + 2.0  # +2px padding so boxes gap, not just touch
    pos = a.copy()
    pos[:, 1] -= half[:, 1] + 2.0  # start just above each anchor (y grows downward)
    pos[:, 0] += np.arange(n) * 1e-3  # deterministic tie-break for coincident anchors

    k_spring, k_label, k_point, point_r = 0.015, 0.4, 0.4, 3.0
    for _ in range(iterations):
        disp = np.zeros_like(pos)
        for i in range(n):
            for j in range(i + 1, n):  # label <-> label box repulsion
                d = pos[i] - pos[j]
                overlap = (half[i] + half[j]) - np.abs(d)
                if overlap[0] > 0 and overlap[1] > 0:
                    # push apart along whichever axis is least overlapping (smaller move)
                    if overlap[0] <= overlap[1]:
                        push = np.array([overlap[0] * (1.0 if d[0] >= 0 else -1.0), 0.0])
                    else:
                        push = np.array([0.0, overlap[1] * (1.0 if d[1] >= 0 else -1.0)])
                    disp[i] += push * k_label
                    disp[j] -= push * k_label
            for k in range(n):  # label <-> point repulsion (lift labels off the markers)
                d = pos[i] - a[k]
                ox, oy = (half[i, 0] + point_r) - abs(d[0]), (half[i, 1] + point_r) - abs(d[1])
                if ox > 0 and oy > 0:
                    if ox <= oy:
                        disp[i, 0] += ox * (1.0 if d[0] >= 0 else -1.0) * k_point
                    else:
                        disp[i, 1] += oy * (1.0 if d[1] >= 0 else -1.0) * k_point
        disp += (a - pos) * k_spring  # weak spring back toward anchor
        pos += disp
        pos[:, 0] = np.clip(pos[:, 0], half[:, 0], width - half[:, 0])
        pos[:, 1] = np.clip(pos[:, 1], half[:, 1], height - half[:, 1])
    return [(float(p[0]), float(p[1])) for p in pos]


def _sample_spread(xs: list[float], ys: list[float], n: int) -> list[int]:
    """Return the indices of ``n`` points spread as evenly as possible across the (x, y) extent -
    farthest-point sampling, deterministic (no RNG).

    Used by ``add_labels(labels=n)`` to auto-pick a readable, unbiased subset to label without the
    caller cherry-picking. Preferred over a uniform random sample, which is density-weighted and so
    would clump labels in the busiest region. Coordinates are normalized to a unit square (so x and
    y weigh equally); the seed is the point nearest the low corner, then each next point is the one
    farthest from all already-chosen. ``n >= len`` returns every index; ``n <= 0`` returns none.
    """
    import numpy as np

    total = len(xs)
    if n >= total:
        return list(range(total))
    if n <= 0:
        return []
    pts = np.column_stack([xs, ys]).astype(float)
    lo = pts.min(axis=0)
    span = pts.max(axis=0) - lo
    span[span == 0] = 1.0
    p = (pts - lo) / span  # unit square
    chosen = [int(np.argmin(p.sum(axis=1)))]  # deterministic seed: nearest the low corner
    dist = np.linalg.norm(p - p[chosen[0]], axis=1)
    for _ in range(n - 1):
        i = int(np.argmax(dist))
        chosen.append(i)
        dist = np.minimum(dist, np.linalg.norm(p - p[i], axis=1))
    return chosen


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
