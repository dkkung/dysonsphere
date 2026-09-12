"""Pure pixel-space geometry and bounded search for point-label placement."""

from __future__ import annotations

import math
import unicodedata

import numpy as np
from numpy.typing import NDArray

# ASCII advances (U+0020 through U+007E) in thousandths of an em, measured from Helvetica Neue
# Regular. Literal metrics keep the default-font estimate portable, including in Pyodide. Other
# sans faces may differ; collision padding is separate from these typographic attachment bounds.
_SANS_ADVANCES = (
    278,
    259,
    426,
    556,
    556,
    1000,
    630,
    278,
    259,
    259,
    352,
    600,
    278,
    389,
    278,
    333,
    556,
    556,
    556,
    556,
    556,
    556,
    556,
    556,
    556,
    556,
    278,
    278,
    600,
    600,
    600,
    556,
    800,
    648,
    685,
    722,
    704,
    611,
    574,
    759,
    722,
    259,
    519,
    667,
    556,
    871,
    722,
    760,
    648,
    760,
    685,
    648,
    574,
    722,
    611,
    926,
    611,
    648,
    611,
    259,
    333,
    259,
    600,
    500,
    222,
    537,
    593,
    537,
    593,
    537,
    296,
    574,
    556,
    222,
    222,
    519,
    222,
    853,
    556,
    574,
    593,
    593,
    333,
    500,
    315,
    556,
    500,
    758,
    518,
    500,
    480,
    333,
    222,
    333,
    600,
)


def _estimate_text_size(
    text: str,
    font_size: float,
    *,
    chip: bool = False,
    font_family: str | None = None,
    font_weight: str | int | float | None = None,
    font_style: str | None = None,
) -> tuple[float, float]:
    """Return a conservatively padded collision box for one rendered label."""
    width, height = _estimate_attachment_size(
        text,
        font_size,
        chip=chip,
        font_family=font_family,
        font_weight=font_weight,
        font_style=font_style,
    )
    if chip:
        return width, height
    return width + font_size * 0.35, max(height, font_size * 1.2)


def _estimate_attachment_size(
    text: str,
    font_size: float,
    *,
    chip: bool = False,
    font_family: str | None = None,
    font_weight: str | int | float | None = None,
    font_style: str | None = None,
) -> tuple[float, float]:
    """Estimate typographic attachment bounds separately from collision padding."""
    family = (font_family or "sans-serif").split(",", 1)[0].strip(" \"'").lower()
    monospace = "mono" in family or "courier" in family
    sans = family in ("sans-serif", "arial", "helvetica", "helvetica neue", "helveticaneue")
    width = 0.0
    for char in text:
        codepoint = ord(char)
        if unicodedata.combining(char):
            advance = 0.0
        elif unicodedata.east_asian_width(char) in ("W", "F"):
            advance = 1.0
        elif monospace:
            advance = 0.62
        elif sans and 32 <= codepoint <= 126:
            advance = _SANS_ADVANCES[codepoint - 32] / 1000.0
        elif char.isspace():
            advance = 0.32
        elif char in "ilIjtfr.,:;'|!()[]{}":
            advance = 0.34
        elif char in "mwMW@%&QO0":
            advance = 0.9
        elif char.isupper():
            advance = 0.7
        else:
            advance = 0.6
        width += advance * font_size
    if font_weight in ("bold", "bolder") or isinstance(font_weight, (int, float)) and font_weight >= 600:
        width *= 1.06
    if font_style in ("italic", "oblique"):
        width += font_size * 0.12
    if chip:
        return width + font_size * 0.7, font_size * 1.4
    return max(width, font_size * 0.25), font_size


def _shortened_segment(
    anchor: tuple[float, float],
    center: tuple[float, float],
    size: tuple[float, float],
    marker_gap: float,
    text_gap: float,
    *,
    stroke_width: float = 0.25,
    obstacles: list[tuple[float, float]] | NDArray[np.float64] | None = None,
    point_radius: float = 0.0,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Choose a short straight connector among sampled visible boundary attachments."""
    cx, cy = center
    hw, hh = size[0] / 2.0, size[1] / 2.0
    # Near-axis corner approaches resemble detached underlines. Prefer readable edge-body ports,
    # but allow a facing corner when the route is genuinely diagonal to both adjacent edges.
    inset = min(hw, hh)
    xlo, xhi = cx - hw + inset, cx + hw - inset
    projected_x = min(max(anchor[0], xlo), xhi)
    preferred: list[tuple[float, float]] = []
    attachments: list[tuple[float, float]] = []
    spacing = max(2.0 * point_radius + stroke_width, 0.5)
    for x, visible in ((cx - hw, anchor[0] <= cx - hw), (cx + hw, anchor[0] >= cx + hw)):
        if visible:
            preferred.append((x, cy))
            attachments.extend(((x, cy - hh * 0.5), (x, cy + hh * 0.5)))
    for y, visible in ((cy - hh, anchor[1] <= cy - hh), (cy + hh, anchor[1] >= cy + hh)):
        if visible:
            preferred.append((projected_x, y))
            for offset in (-2.0 * spacing, -spacing, spacing, 2.0 * spacing):
                attachments.append((min(max(projected_x + offset, xlo), xhi), y))
    for x, x_visible in ((cx - hw, anchor[0] < cx - hw), (cx + hw, anchor[0] > cx + hw)):
        for y, y_visible in ((cy - hh, anchor[1] < cy - hh), (cy + hh, anchor[1] > cy + hh)):
            dx, dy = abs(x - anchor[0]), abs(y - anchor[1])
            # Both faces must face the anchor. Exclude only essentially edge-parallel approaches
            # (within about 6 degrees), not the shallow but readable diagonals of short leaders.
            if x_visible and y_visible and min(dx, dy) >= 0.1 * max(dx, dy):
                preferred.append((x, y))
    if not preferred:
        # A label covering its anchor is already an infeasible overlap. A connector through the
        # label's own interior cannot explain the association more clearly.
        return None
    nearest = min(preferred, key=lambda p: math.dist(anchor, p))
    attachments = list(dict.fromkeys([*preferred, *attachments]))

    def shorten(end: tuple[float, float]):
        length = math.dist(anchor, end)
        gm, gt = marker_gap, text_gap
        if length < gm + gt + 4.0 * stroke_width:
            return None
        if length <= 0:
            return anchor, anchor
        ux, uy = (end[0] - anchor[0]) / length, (end[1] - anchor[1]) / length
        return (anchor[0] + ux * gm, anchor[1] + uy * gm), (end[0] - ux * gt, end[1] - uy * gt)

    points = np.asarray(obstacles if obstacles is not None else [], dtype=float).reshape(-1, 2)
    radius = point_radius + stroke_width / 2
    low = np.minimum(anchor, (cx - hw, cy - hh)) - radius
    high = np.maximum(anchor, (cx + hw, cy + hh)) + radius
    points = points[((points >= low) & (points <= high)).all(axis=1)]
    if not isinstance(obstacles, np.ndarray):
        points = np.unique(points, axis=0)
    points = points[np.linalg.norm(points - anchor, axis=1) > 1e-9]
    nearest_line = shorten(nearest)
    if nearest_line is None or not len(points):
        return nearest_line
    start, finish = np.asarray(nearest_line)
    vec = finish - start
    length2 = float(vec @ vec)
    t = np.clip((points - start) @ vec / length2, 0, 1) if length2 else np.zeros(len(points))
    if np.all(np.linalg.norm(points - start - t[:, None] * vec, axis=1) >= point_radius + stroke_width / 2):
        # Keep the readable edge-body attachment when clear; sliding is an obstacle fallback.
        return nearest_line
    lines = [shorten(end) for end in attachments]
    active = np.array([line is not None for line in lines])
    starts = np.array([line[0] if line is not None else anchor for line in lines])
    ends = np.array([line[1] if line is not None else anchor for line in lines])
    vec = ends - starts
    length2 = np.sum(vec * vec, axis=1)
    relative = points[None, :, :] - starts[:, None, :]
    t = np.divide(
        np.sum(relative * vec[:, None, :], axis=2),
        length2[:, None],
        out=np.zeros((len(lines), len(points))),
        where=length2[:, None] > 0,
    )
    nearest = starts[:, None, :] + np.clip(t, 0, 1)[:, :, None] * vec[:, None, :]
    hits = (
        (np.linalg.norm(points[None, :, :] - nearest, axis=2) < point_radius + stroke_width / 2) & active[:, None]
    ).sum(axis=1)
    pick = int(np.lexsort((length2, hits))[0])
    return lines[pick]


def _repel_labels(
    anchors: list[tuple[float, float]],
    sizes: list[tuple[float, float]],
    *,
    width: float,
    height: float,
    obstacles: list[tuple[float, float]] | None = None,
    point_radius: float = 3.0,
    marker_gap: float = 0.0,
    text_gap: float = 0.0,
    connector: bool = True,
    always_show: bool = False,
    stroke_width: float = 0.25,
    attachment_sizes: list[tuple[float, float]] | None = None,
) -> list[tuple[float, float]]:
    """Place every label using a deterministic, finite geometry-aware candidate search.

    Boxes remain in the panel whenever they fit. The score treats label/point overlap and every
    symmetric label/connector collision as defects before minimizing visible connector length.
    The search has fixed bounded passes and retains oversized labels at the panel center.
    """
    import numpy as np

    n = len(anchors)
    if n == 0:
        return []
    a = np.asarray(anchors, dtype=float)
    obs = np.asarray(obstacles if obstacles is not None else anchors, dtype=float).reshape(-1, 2)
    # Coincident rows paint the same obstacle; duplicates must not multiply a geometric penalty.
    obs = np.unique(obs, axis=0)
    sz = np.asarray(sizes, dtype=float)
    attach_sz = np.asarray(attachment_sizes if attachment_sizes is not None else sizes, dtype=float)
    half = sz / 2.0

    def candidates(k: int) -> np.ndarray:
        hw, hh = half[k]
        # Edge-relative seats first; lateral variants let long labels attach near their ends without
        # paying for an unnecessary trip to the text center. Larger rings are escape candidates.
        values: list[tuple[float, float]] = []
        minimum = max(text_gap, marker_gap + text_gap + 4.0 * stroke_width if always_show and connector else 0.25)
        for extra in (minimum, minimum + 2.0, minimum + 5.0, minimum + 10.0, minimum + 20.0, minimum + 34.0):
            gx, gy = hw + point_radius + extra, hh + point_radius + extra
            for sx, sy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                base = a[k] + (sx * gx, sy * gy)
                lateral = hh * 0.65 if sx else hw * 0.65
                near_shift = max(lateral, 6.0)
                for shift in (0.0, -near_shift, near_shift, -12.0, 12.0):
                    values.append((base[0] + (0 if sx else shift), base[1] + (shift if sx else 0)))
        # A sparse panel-wide grid provides escape seats not restricted to an anchor's neighborhood.
        values.extend(
            (float(x), float(y)) for x in np.linspace(hw, width - hw, 9) for y in np.linspace(hh, height - hh, 7)
        )
        c = np.asarray(values)
        if 2 * hw <= width:
            c[:, 0] = np.clip(c[:, 0], hw, width - hw)
        else:
            c[:, 0] = width / 2.0
        if 2 * hh <= height:
            c[:, 1] = np.clip(c[:, 1], hh, height - hh)
        else:
            c[:, 1] = height / 2.0
        return np.unique(c, axis=0)

    cand = [candidates(k) for k in range(n)]
    segment_cache: dict[tuple[int, float, float], tuple[tuple[float, float], tuple[float, float]] | None] = {}

    def segments(k: int, centers: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        lines = []
        for c in centers:
            key = (k, float(c[0]), float(c[1]))
            if key not in segment_cache:
                segment_cache[key] = (
                    _shortened_segment(
                        tuple(a[k]),
                        tuple(c),
                        tuple(attach_sz[k]),
                        marker_gap,
                        text_gap,
                        stroke_width=stroke_width,
                        obstacles=obs,
                        point_radius=point_radius,
                    )
                    if connector
                    else None
                )
            lines.append(segment_cache[key])
        active = np.array([line is not None for line in lines])
        starts = np.array([line[0] if line is not None else a[k] for line in lines])
        ends = np.array([line[1] if line is not None else a[k] for line in lines])
        return starts, ends, active

    def seg_point_dist(start: np.ndarray, end: np.ndarray, points: np.ndarray) -> np.ndarray:
        v = end - start
        vv = np.sum(v * v, axis=1)
        rel = points[None, :, :] - start[:, None, :]
        t = np.divide(
            np.sum(rel * v[:, None, :], axis=2),
            vv[:, None],
            out=np.zeros((len(start), len(points))),
            where=vv[:, None] > 0,
        )
        near = start[:, None, :] + np.clip(t, 0, 1)[:, :, None] * v[:, None, :]
        return np.linalg.norm(points[None, :, :] - near, axis=2)

    def seg_box(start: np.ndarray, end: np.ndarray, centers: np.ndarray, h: np.ndarray) -> np.ndarray:
        # Slab intersection, vectorized candidates x boxes.
        d = end - start
        lo = centers[None, :, :] - h[None, :, :]
        hi = centers[None, :, :] + h[None, :, :]
        with np.errstate(divide="ignore", invalid="ignore"):
            t1 = (lo - start[:, None, :]) / d[:, None, :]
            t2 = (hi - start[:, None, :]) / d[:, None, :]
        parallel = np.abs(d[:, None, :]) < 1e-12
        inside = (start[:, None, :] >= lo) & (start[:, None, :] <= hi)
        axis_ok = (~parallel) | inside
        enter = np.max(np.where(parallel, -np.inf, np.minimum(t1, t2)), axis=2)
        leave = np.min(np.where(parallel, np.inf, np.maximum(t1, t2)), axis=2)
        return axis_ok.all(axis=2) & (np.maximum(enter, 0.0) <= np.minimum(leave, 1.0))

    static: list[np.ndarray] = []
    for k, c in enumerate(cand):
        dx = np.abs(c[:, None, 0] - obs[None, :, 0])
        dy = np.abs(c[:, None, 1] - obs[None, :, 1])
        label_point = ((dx < half[k, 0] + point_radius) & (dy < half[k, 1] + point_radius)).sum(axis=1)
        start, end, active = segments(k, c)
        connector_point = (seg_point_dist(start, end, obs) < point_radius + stroke_width / 2) & active[:, None]
        connector_point[:, np.linalg.norm(obs - a[k], axis=1) < 1e-9] = False
        distance = np.linalg.norm(np.maximum(np.abs(c - a[k]) - half[k], 0), axis=1)
        route_length = np.linalg.norm(end - start, axis=1)
        # Compactness also matters without drawn connectors. Count saturation bounds the influence
        # of a dense, infeasible cloud rather than trading one text overlap for hundreds of dots.
        static.append(
            250_000.0 * np.minimum(label_point, 4)
            + 60_000.0 * np.minimum(connector_point.sum(axis=1), 4)
            + distance
            + 0.1 * np.maximum(distance - 12, 0) ** 2
            + route_length
            + 0.5 * np.maximum(route_length - 12, 0) ** 2
            + (20_000_000.0 * (~active) if always_show and connector else 0.0)
        )

    result = np.zeros((n, 2))
    placed: list[int] = []

    def pair_cost(k: int, c: np.ndarray, others: list[int]) -> np.ndarray:
        if not others:
            return np.zeros(len(c))
        op = result[others]
        oh = half[others]
        overlap = (np.abs(c[:, None, 0] - op[None, :, 0]) < half[k, 0] + oh[:, 0]) & (
            np.abs(c[:, None, 1] - op[None, :, 1]) < half[k, 1] + oh[:, 1]
        )
        start, end, active = segments(k, c)
        through_other = seg_box(start, end, op, oh) & active[:, None]
        total = 10_000_000.0 * overlap.sum(axis=1) + 120_000.0 * through_other.sum(axis=1)
        for q in others:  # labels only (normally <=25), while candidate x point work stays vectorized
            qs, qe, qactive = segments(q, result[q : q + 1])
            if not qactive[0]:
                continue
            total += 120_000.0 * seg_box(qs, qe, c, np.broadcast_to(half[k], c.shape))[0]
            v = end - start
            w = qe[0] - qs[0]
            den = v[:, 0] * w[1] - v[:, 1] * w[0]
            rel = qs[0] - start
            with np.errstate(divide="ignore", invalid="ignore"):
                t = (rel[:, 0] * w[1] - rel[:, 1] * w[0]) / den
                u = (rel[:, 0] * v[:, 1] - rel[:, 1] * v[:, 0]) / den
            total += 30_000.0 * (active & (np.abs(den) > 1e-12) & (t > 0) & (t < 1) & (u > 0) & (u < 1))
        return total

    order = sorted(range(n), key=lambda k: (-sz[k, 0], k))
    for k in order:
        score = static[k] + pair_cost(k, cand[k], placed)
        result[k] = cand[k][int(np.argmin(score))]
        placed.append(k)
    for _ in range(6):
        changed = False
        for k in order:
            others = [q for q in range(n) if q != k]
            score = static[k] + pair_cost(k, cand[k], others)
            chosen = cand[k][int(np.argmin(score))]
            if not np.array_equal(chosen, result[k]):
                result[k] = chosen
                changed = True
        if not changed:
            break
    return [(float(p[0]), float(p[1])) for p in result]


def _sample_spread(xs: list[float], ys: list[float], n: int) -> list[int]:
    """Return deterministic farthest-point sampling indices over the normalized extent."""
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
    p = (pts - lo) / span
    chosen = [int(np.argmin(p.sum(axis=1)))]
    dist = np.linalg.norm(p - p[chosen[0]], axis=1)
    for _ in range(n - 1):
        i = int(np.argmax(dist))
        chosen.append(i)
        dist = np.minimum(dist, np.linalg.norm(p - p[i], axis=1))
    return chosen
