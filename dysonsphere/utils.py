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
    obstacles: "list[tuple[float, float]] | None" = None,
    iterations: int = 300,
) -> list[tuple[float, float]]:
    """Nearest-clear-spot label placement (deterministic) - the engine behind :func:`add_labels`.

    ``anchors`` are the pixel positions of the points being labelled and ``sizes`` each label's
    ``(width, height)`` box in pixels (origin top-left, y growing downward, matching a rendered SVG).
    ``obstacles`` are the pixel positions of ALL plotted points to avoid covering (default: just the
    ``anchors``). Returns one label-CENTRE pixel position per anchor.

    Each label is placed at the position of **minimal displacement** from its point (so the connector
    is as short as possible) whose box still clears the markers and the already-placed labels - found
    by a ring search stepping outward from the point that, at each radius, tries candidate angles in
    OUTWARD order (mark - data centroid) as a **soft directionality tiebreak** (left mark -> left
    label), never forcing a longer connector. Labels are placed in order of local sparsity, so the
    easy isolated ones lock in their short connectors first and the crowded ones search among what
    remains. A final **2-opt pass** then swaps which label owns which slot whenever that lowers the
    total cost (connector length + marker/label-overlap penalties + a small inward penalty ``w_dir``
    that keeps the soft outward lean): by the uncrossing lemma, minimizing length removes crossing
    leaders for free. Connector length is therefore **dynamic**: tiny where there is open space beside
    the point, longer only where the point is genuinely buried. Fully deterministic (no RNG). **Never
    drops a label** (force-show): if nothing fully clears within the panel, the label takes its
    least-overlapping candidate (label-label overlap is weighted far above marker overlap). Directionality
    is deliberately SOFT (a tiebreak/bias, not a hard outward rule) so it stays general beyond volcano-
    shaped data. ``iterations`` is unused (kept for call compatibility).
    """
    import numpy as np

    n = len(anchors)
    if n == 0:
        return []
    a = np.array(anchors, dtype=float)
    obs = np.array(obstacles if obstacles is not None else anchors, dtype=float)
    half = np.array(sizes, dtype=float) / 2.0 + 2.0  # +2px padding so boxes gap, not just touch
    point_r = 3.0  # marker clearance radius (a label box within this of a marker "covers" it)
    centroid = obs.mean(axis=0)  # data centre; a SOFT outward bias (below) leans labels away from it
    w_dir = 10.0  # (left mark -> left label, right mark -> right) as a tiebreak, never forcing length.

    # Placement order: sparsest anchors first (few nearby markers -> short connectors lock in early),
    # so the crowded ones search among what is left. Deterministic (stable argsort, no RNG).
    near_r = 0.3 * min(width, height)
    local = np.array([int((np.hypot(obs[:, 0] - a[i, 0], obs[:, 1] - a[i, 1]) < near_r).sum()) for i in range(n)])
    order = list(np.argsort(local, kind="stable"))

    # Ring search: radii step outward in pixels; at each radius try 24 angles, ordered per label so
    # the OUTWARD side (toward the margins) is tried first. First zero-cost (fully clear) candidate wins.
    radii = np.arange(0.0, 0.6 * float(np.hypot(width, height)), 2.0)
    base_ang = np.linspace(0.0, 2.0 * np.pi, 24, endpoint=False)

    result: list[tuple[float, float]] = [(0.0, 0.0)] * n
    placed: list[tuple[float, float, float, float]] = []  # (cx, cy, hw, hh) of already-placed labels

    for idx in order:
        ax, ay = float(a[idx, 0]), float(a[idx, 1])
        hw, hh = float(half[idx, 0]), float(half[idx, 1])
        # Preferred direction: OUTWARD from the data centroid (a left mark faces left, a right mark
        # right), so labels lean toward the margins. For a mark near the centroid (no clear outward
        # side) fall back to "away from the distance-weighted local crowd". SOFT tiebreak only - the
        # label still takes the NEAREST clear spot below; outward just orders the angles tried.
        v = a[idx] - centroid
        if np.hypot(v[0], v[1]) < 0.05 * min(width, height):
            d = a[idx] - obs
            dist = np.hypot(d[:, 0], d[:, 1])
            m = (dist > 1e-9) & (dist < near_r)
            v = (d[m] * (1.0 / dist[m] ** 2)[:, None]).sum(axis=0) if m.any() else np.array([0.0, -1.0])
        open_ang = float(np.arctan2(v[1], v[0])) if np.hypot(v[0], v[1]) > 1e-9 else -np.pi / 2.0
        diff = np.abs((base_ang - open_ang + np.pi) % (2.0 * np.pi) - np.pi)
        angs = base_ang[np.argsort(diff, kind="stable")]

        chosen: tuple[float, float] | None = None
        best: tuple[float, float] | None = None
        best_cost = None
        for r in radii:
            for ang in angs:
                cx = ax + r * float(np.cos(ang))
                cy = ay + r * float(np.sin(ang))
                if cx - hw < 0 or cx + hw > width or cy - hh < 0 or cy + hh > height:
                    continue
                markers = int(((np.abs(obs[:, 0] - cx) < hw + point_r) & (np.abs(obs[:, 1] - cy) < hh + point_r)).sum())
                labels_hit = sum(
                    1 for (px, py, phw, phh) in placed if abs(px - cx) < hw + phw and abs(py - cy) < hh + phh
                )
                cost = markers + labels_hit * 1000  # a label-label overlap is far worse than a marker
                if cost == 0:
                    chosen = (cx, cy)
                    break
                if best_cost is None or cost < best_cost:
                    best_cost = cost
                    best = (cx, cy)
            if chosen is not None:
                break
        c = chosen if chosen is not None else (best if best is not None else (ax, ay))
        result[idx] = c
        placed.append((c[0], c[1], hw, hh))

    # 2-opt assignment refinement. The greedy fixes a good CENTRE per label, but a label can end up
    # owning a slot that makes its leader long or cross another label's. Swapping which label owns
    # which slot, whenever that lowers the total cost, shortens leaders and - by the uncrossing lemma
    # (swapping the far ends of two crossing segments always shortens the pair) - removes crossings,
    # while the overlap penalties stop a swap that would collide boxes. n is small (top-N labels), so
    # a full-cost recompute per candidate swap is cheap.
    def _config_cost(assign: list[tuple[float, float]]) -> float:
        total = 0.0
        for k in range(n):
            cx, cy = assign[k]
            hw_k, hh_k = float(half[k, 0]), float(half[k, 1])
            total += float(np.hypot(cx - a[k, 0], cy - a[k, 1]))  # connector length
            total += 50.0 * int(
                ((np.abs(obs[:, 0] - cx) < hw_k + point_r) & (np.abs(obs[:, 1] - cy) < hh_k + point_r)).sum()
            )
            # soft outward preference: penalise a label sitting INWARD of its mark (toward the
            # centroid), biasing the 2-opt to keep left marks left / right marks right.
            ox, oy = float(a[k, 0] - centroid[0]), float(a[k, 1] - centroid[1])
            onrm = float(np.hypot(ox, oy))
            if onrm > 1e-9:
                inward = -((cx - a[k, 0]) * ox + (cy - a[k, 1]) * oy) / onrm
                if inward > 0.0:
                    total += w_dir * inward
        for p in range(n):
            for q in range(p + 1, n):
                (cx1, cy1), (cx2, cy2) = assign[p], assign[q]
                if abs(cx1 - cx2) < half[p, 0] + half[q, 0] and abs(cy1 - cy2) < half[p, 1] + half[q, 1]:
                    total += 5000.0  # label-label overlap: effectively forbidden
        return total

    for _ in range(20):
        improved = False
        base = _config_cost(result)
        for i in range(n):
            for j in range(i + 1, n):
                result[i], result[j] = result[j], result[i]
                new = _config_cost(result)
                if new < base - 1e-6:
                    base = new
                    improved = True
                else:
                    result[i], result[j] = result[j], result[i]  # revert
        if not improved:
            break

    return [(float(cx), float(cy)) for cx, cy in result]


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


def _nice_domain(lo: float, hi: float, count: int = 10) -> tuple[float, float]:
    """Round ``(lo, hi)`` outward to nice tick-increment multiples - d3's ``nice()`` algorithm.

    Used by ``add_labels`` to pin the shared scale to nice bounds instead of the raw data extent,
    so the pinned axes read like Vega's own ``nice: true`` (whose rounding this replicates: the
    d3-scale 1/2/5/10 tick increment at ``count`` ~ticks, applied twice so the widened domain can
    settle on a coarser step). Exactness vs Vega does not matter - the caller FORCES the returned
    domain, so whatever this computes is what renders. Degenerate spans return unchanged.
    """
    import math

    if not (hi > lo):
        return lo, hi
    for _ in range(2):
        step = (hi - lo) / count
        power = 10.0 ** math.floor(math.log10(step))
        err = step / power
        # d3's tickIncrement thresholds: sqrt(50), sqrt(10), sqrt(2)
        step = power * (10 if err >= math.sqrt(50) else 5 if err >= math.sqrt(10) else 2 if err >= math.sqrt(2) else 1)
        lo2, hi2 = math.floor(lo / step) * step, math.ceil(hi / step) * step
        if (lo2, hi2) == (lo, hi):
            break
        lo, hi = lo2, hi2
    return lo, hi


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
