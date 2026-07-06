"""Pixel-space label placement - the pure geometry engine behind ``annotations.add_labels``.

No Altair imports here: everything takes and returns plain pixel coordinates, mirroring how
``statistics.py`` is the pure computation engine behind ``inference.py``. Placement is solved
outside the renderer (like ggrepel / adjustText / d3-labeler) because Vega-Lite has no
label-repel primitive; the wrapper feeds the results back to Altair as static positions.
"""


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
