"""Private SVG geometry, layering, and simplification corrections."""

from __future__ import annotations

import json
import math
import re
import xml.etree.ElementTree as ET

from .utils import _RULE_CAP_PREFIX, _SHADE_PREFIX

__all__: list[str] = []

_SVG_NS = "http://www.w3.org/2000/svg"
# Registered once so ET serializes SVG without ns0: prefixes, from any fixer or test.
ET.register_namespace("", _SVG_NS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
_LINE_TRANSLATE = re.compile(r"^translate\(\s*([-\d.eE]+)[,\s]+([-\d.eE]+)\s*\)$")


def _rule_cap_options(cls: str) -> tuple[str | None, str | None, float, float] | None:
    """Decode the durable rule-decoration payload carried by a rendered line's aria-label."""
    marker = next((part for part in cls.split() if part.startswith(_RULE_CAP_PREFIX)), None)
    if marker is None:
        return None
    token = re.match(r"[0-9a-f]+", marker[len(_RULE_CAP_PREFIX) :])
    if token is None:
        return None
    try:
        start_cap, end_cap, start_gap, end_gap = json.loads(bytes.fromhex(token.group()).decode())
        return start_cap, end_cap, float(start_gap), float(end_gap)
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _decorate_rule_segments(root: ET.Element) -> None:
    """Apply pixel-accurate caps and gaps to opted-in rule lines in the rendered SVG tree.

    Geometry is measured after Vega has resolved scales, facets, dimensions, and reversals. Each
    original line is shortened in its own SVG coordinate system and cap elements are inserted beside
    it, preserving editable SVG objects. Screen-coincident segments and segments too short to fit
    the full endpoint insets are omitted, including their caps, rather than reducing clearance.

    This low-level segment operation deliberately knows nothing about ``rule`` data coordinates;
    both reference rules and label connectors carry the same durable decoration marker.
    """
    decorated = [
        (line, options)
        for line in root.iter(f"{{{_SVG_NS}}}line")
        if (options := _rule_cap_options(line.get("aria-label", ""))) is not None
    ]
    if not decorated:
        return
    parents = {child: parent for parent in root.iter() for child in parent}

    def point_text(x: float, y: float) -> str:
        return f"{x:.12g},{y:.12g}"

    for line, options in decorated:
        start_cap, end_cap, start_gap, end_gap = options
        parent = parents.get(line)
        if parent is None:
            continue
        match = _LINE_TRANSLATE.match(line.get("transform", ""))
        if match is None:
            continue
        x0 = float(match.group(1)) + float(line.get("x1") or line.get("x") or 0)
        y0 = float(match.group(2)) + float(line.get("y1") or line.get("y") or 0)
        x1 = float(match.group(1)) + float(line.get("x2") or 0)
        y1 = float(match.group(2)) + float(line.get("y2") or 0)
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        if length <= 1e-12:
            line.set("display", "none")
            continue
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        stroke_width = float(line.get("stroke-width") or 1)

        def cap_size(cap: str | None) -> float:
            return 4.0 * math.sqrt(stroke_width) if cap == "arrow" else max(4.0, 4.0 * stroke_width)

        start_extent = start_gap + (cap_size(start_cap) if start_cap is not None else 0)
        end_extent = end_gap + (cap_size(end_cap) if end_cap is not None else 0)
        if start_extent + end_extent >= length:
            # Never move a decoration beyond the opposite target or silently reduce a requested
            # clearance. There is no drawable segment when the full endpoint extents do not fit.
            line.set("display", "none")
            continue

        def cap_geometry(cap: str | None, x: float, y: float, ix: float, iy: float, gap: float):
            tip_x, tip_y = x + ix * gap, y + iy * gap
            if cap is None:
                return tip_x, tip_y, None
            size = cap_size(cap)
            if size == 0:
                return tip_x, tip_y, None
            if cap == "arrow":
                base_x, base_y = tip_x + ix * size, tip_y + iy * size
                half_width = size * 0.6
                path = ET.Element(f"{{{_SVG_NS}}}path")
                path.set(
                    "d",
                    f"M{point_text(tip_x, tip_y)}L{point_text(base_x + px * half_width, base_y + py * half_width)}"
                    f"L{point_text(base_x - px * half_width, base_y - py * half_width)}Z",
                )
                return base_x, base_y, path
            half = size / 2
            center_x, center_y = tip_x + ix * half, tip_y + iy * half
            if cap == "circle":
                shape = ET.Element(
                    f"{{{_SVG_NS}}}circle",
                    {"cx": f"{center_x:.12g}", "cy": f"{center_y:.12g}", "r": f"{half:.12g}"},
                )
            else:
                corners = [
                    (center_x + sx * ix * half + sy * px * half, center_y + sx * iy * half + sy * py * half)
                    for sx, sy in ((-1, -1), (-1, 1), (1, 1), (1, -1))
                ]
                shape = ET.Element(f"{{{_SVG_NS}}}path", {"d": "M" + "L".join(point_text(*p) for p in corners) + "Z"})
            # Meet the decoration at its inward edge rather than drawing underneath it; this
            # avoids darkening translucent caps through alpha overlap.
            return center_x + ix * half, center_y + iy * half, shape

        sx, sy, start_shape = cap_geometry(start_cap, x0, y0, ux, uy, start_gap)
        ex, ey, end_shape = cap_geometry(end_cap, x1, y1, -ux, -uy, end_gap)
        for shape in (start_shape, end_shape):
            if shape is None:
                continue
            shape.set("class", "ds-rule-cap")
            shape.set("fill", line.get("stroke", "black"))
            shape.set("stroke", "none")
            shape.set("opacity", line.get("opacity", "1"))
            shape.set("fill-opacity", line.get("stroke-opacity", "1"))
            shape.set("pointer-events", "none")
            parent.insert(list(parent).index(line) + 1, shape)
        remaining = (ex - sx) * ux + (ey - sy) * uy
        if remaining <= 0:
            line.set("display", "none")
        else:
            line.set("transform", f"translate({sx:.12g},{sy:.12g})")
            line.set("x1", "0")
            line.set("y1", "0")
            line.set("x2", f"{ex - sx:.12g}")
            line.set("y2", f"{ey - sy:.12g}")
            line.set("stroke-linecap", "butt")


def _align_grid_to_content(root: ET.Element, axis_offset: float) -> None:
    """Seat every grid line onto the plot content rectangle, off the detached axes.

    On an open plot, each axis is drawn ``axis_offset`` px away from the plot (the detached-axis
    gap): the x-axis sits below, and the y-axis sits left. Vega renders each grid line inside its
    axis group, so the grid inherits that offset. Vertical grid lines in the x-axis group shift
    down (the top falls short of the highest tick, and the bottom extends onto the x-axis); the
    horizontal grid lines in the y-axis group shift left (touching the y-axis and falling short
    of the right edge). Translating each line back by ``axis_offset`` leaves its span unchanged:
    vertical lines move up and horizontal lines move right, so both span the plot content exactly
    and sit symmetrically off the detached axes. Closed-plot axes are flush with the grid, so this
    fixer is skipped for closed plots.

    A vertical grid line is a ``translate(x,-H)`` (``ty<0``) with ``y2=H``; a horizontal one is a
    ``translate(0,y)`` with ``x2=W``.  Both live inside a ``role-axis-grid`` group.

    Mutates the parsed SVG tree in place, like the other fixers in the corrected-SVG pipeline.
    Tick and grid positions already match the fractional scale positions because the theme uses
    ``tickRound: false`` and ``axisBand.tickOffset: 0``.
    """
    _xlate = re.compile(r"translate\(\s*([-\d.eE]+)[,\s]+([-\d.eE]+)\s*\)")

    def _walk(el: ET.Element) -> None:
        for ch in el:
            if ch.get("class") == "mark-rule role-axis-grid":
                for line in ch:
                    m = _xlate.match(line.get("transform", ""))
                    if not m:
                        continue
                    tx, ty = float(m.group(1)), float(m.group(2))
                    x2 = float(line.get("x2") or 0)
                    y2 = float(line.get("y2") or 0)
                    if abs(y2) > abs(x2) and ty < 0:  # vertical grid (x-axis group, offset down): lift up
                        line.set("transform", f"translate({tx},{ty - axis_offset})")
                    elif abs(x2) > abs(y2):  # horizontal grid (y-axis group, offset left): shift right
                        line.set("transform", f"translate({tx + axis_offset},{ty})")
            else:
                _walk(ch)

    _walk(root)


def _flip_ticks_inward(root: ET.Element) -> None:
    """Negate axis-tick line geometry so ticks point into the plot (theme(tickDirection="in")).

    Vega/Vega-Lite render ticks outward and reject a negative ``tickSize``, so inward ticks
    are produced here as an SVG post-process that negates the non-zero ``x2``/``y2`` of every
    ``<line>`` inside an axis-tick group. x-axis ticks carry their length in ``y2`` (``x2="0"``);
    y-axis ticks carry it in ``x2`` (``y2="0"``). Negating the non-zero coordinate flips each
    tick. This covers primary, secondary (right/top), major, and minor (log/power) ticks because
    they all use ``role-axis-tick`` groups.

    Vega places labels and titles beyond outward ticks. When the ticks flip, that spacing would
    leave a gap between the domain line and labels. Every ``<text>`` in each axis's
    ``role-axis-label`` / ``role-axis-title`` group is translated toward the view by that axis's
    tick vector, read before negation. Per-axis lengths, such as half-size log/power minor ticks,
    determine the shift; those axes have no labels. The shift is applied to each text element's
    own ``translate``, not its group, because ``_simplify_svg`` later flattens the ``<g>`` wrappers
    and would drop a group transform. Trailing transform parts, such as label ``rotate``, are
    preserved. The label-to-title gap is preserved because both move together; an axis without
    tick lines is left unchanged.
    """
    _xlate = re.compile(r"^translate\(\s*([-\d.eE]+)[,\s]+([-\d.eE]+)\s*\)(.*)$")
    # Pass 1: pull labels + title in by the tick length, per axis group (pre-negation read).
    for axis in root.iter(f"{{{_SVG_NS}}}g"):
        cls = axis.get("class", "")
        if "mark-group" not in cls or "role-axis" not in cls:
            continue
        tick_line = next(
            (
                line
                for g in axis.iter(f"{{{_SVG_NS}}}g")
                if "role-axis-tick" in g.get("class", "")
                for line in g.iter(f"{{{_SVG_NS}}}line")
            ),
            None,
        )
        if tick_line is None:
            continue
        dx = -float(tick_line.get("x2") or 0)
        dy = -float(tick_line.get("y2") or 0)
        if dx == 0 and dy == 0:
            continue
        for g in axis.iter(f"{{{_SVG_NS}}}g"):
            gcls = g.get("class", "")
            if "role-axis-label" not in gcls and "role-axis-title" not in gcls:
                continue
            for text in g.iter(f"{{{_SVG_NS}}}text"):
                m = _xlate.match(text.get("transform", ""))
                if not m:
                    continue
                x, y, rest = float(m.group(1)), float(m.group(2)), m.group(3)
                text.set("transform", f"translate({x + dx:g},{y + dy:g}){rest}")
    # Pass 2: negate the tick geometry itself.
    for g in root.iter(f"{{{_SVG_NS}}}g"):
        if "role-axis-tick" not in g.get("class", ""):
            continue
        for line in g.iter(f"{{{_SVG_NS}}}line"):
            for attr in ("x2", "y2"):
                v = line.get(attr)
                if v is not None and float(v) != 0.0:
                    line.set(attr, v[1:] if v.startswith("-") else "-" + v)


_FIGURE_LABEL_PREFIX = "__dsfigure_label_"
_TRANSLATE = re.compile(r"translate\(\s*([-\d.eE]+)\s*[,\s]\s*([-\d.eE]+)\s*\)")


def _label_wrapper_parts(node: ET.Element, tx: float, ty: float) -> tuple[ET.Element | None, float, float | None]:
    """Within one labelled member, find its label text and its plot area's x.

    Nested labelled members are not descended into, so an outer figure label is measured
    against its own panel rather than a child's.
    """
    text: ET.Element | None = None
    label_x = plot_x = None

    def walk(el: ET.Element, x: float, y: float, top: bool, in_title: bool) -> None:
        nonlocal text, label_x, plot_x
        cls = el.get("class") or ""
        if not top and _FIGURE_LABEL_PREFIX in cls:
            return
        in_title = in_title or "role-title" in cls
        m = _TRANSLATE.search(el.get("transform") or "")
        if m:
            x, y = x + float(m.group(1)), y + float(m.group(2))
        # Only the title text – chart axis labels come first in document order.
        if in_title and text is None and el.tag == f"{{{_SVG_NS}}}text" and (el.text or "").strip():
            text, label_x = el, x + float(el.get("x") or 0)
        # The view rectangle – the first background path carrying geometry.
        if plot_x is None and el.tag == f"{{{_SVG_NS}}}path" and el.get("class") == "background":
            if (el.get("d") or "M0,0") != "M0,0":
                plot_x = x
        for child in el:
            walk(child, x, y, False, in_title)

    walk(node, tx, ty, True, False)
    return text, label_x or 0.0, plot_x


def _align_figure_labels(root: ET.Element) -> None:
    """Seat every figure label at the leftmost panel edge in its column.

    Vega aligns concat members by their plot area, but a label anchors to its member's
    bounding box. The difference is that member's axis margin, which misaligns labels while
    plots remain aligned. The largest mismatch occurs against a blank member, whose margin is
    zero. For two real charts with different y-axis widths, measured offsets were 26.6 px and
    5.2 px. Members in a column have the same plot-area x, so grouping on that value and taking
    the smallest label x per column aligns them without measuring text.

    Run this before ``_simplify_svg``, which flattens the group transforms it reads. The shift
    is baked into each label's own transform for the same reason.
    """
    found: list[tuple[ET.Element, float, float]] = []

    def collect(el: ET.Element, x: float, y: float) -> None:
        m = _TRANSLATE.search(el.get("transform") or "")
        if m:
            x, y = x + float(m.group(1)), y + float(m.group(2))
        if _FIGURE_LABEL_PREFIX in (el.get("class") or ""):
            text, label_x, plot_x = _label_wrapper_parts(el, x, y)
            if text is not None and plot_x is not None:
                found.append((text, label_x, plot_x))
        for child in el:
            collect(child, x, y)

    collect(root, 0.0, 0.0)
    columns: dict[float, list[tuple[ET.Element, float]]] = {}
    for text, label_x, plot_x in found:
        columns.setdefault(round(plot_x, 3), []).append((text, label_x))
    for column in columns.values():
        target = min(x for _, x in column)
        for text, label_x in column:
            shift = target - label_x
            if abs(shift) < 1e-6:
                continue
            m = _TRANSLATE.search(text.get("transform") or "")
            if m:
                text.set("transform", f"translate({float(m.group(1)) + shift},{m.group(2)})")
            else:
                text.set("x", str(float(text.get("x") or 0) + shift))


_IDENTITY_TRANSFORMS = (None, "", "translate(0,0)", "translate(0, 0)")


def _sink_border_below_shade(root: ET.Element) -> None:
    """Move a closed plot's border so it paints after the ``shade`` background.

    Vega emits the stroked view border as a sibling of the group that holds the marks, with
    the border first, so an opaque shade rectangle paints over it. The left and bottom edges
    survive because the x/y axis domain lines repaint them. ``axisRight`` and ``axisTop`` are
    off by default, so the border alone draws the top and right edges, which would otherwise
    be covered.

    ``_layer_axes_below_marks`` cannot fix this because it reorders within one group, while
    the border and shade are at different depths. The border is moved into the group holding
    the shade, directly after the last shade rectangle – above the shading but below the axes
    and data. This is done only when the intervening groups have no transform, so the border's
    coordinates stay in the same space; otherwise it is left in place.
    """
    parents = {child: parent for parent in root.iter() for child in parent}

    def stroked_border(el: ET.Element) -> bool:
        return (
            el.tag == f"{{{_SVG_NS}}}path"
            and el.get("class") == "background"
            and el.get("stroke") not in (None, "none")
            and el.get("display") != "none"
        )

    for group in list(root.iter(f"{{{_SVG_NS}}}g")):
        shade = [c for c in group if _SHADE_PREFIX in (c.get("class") or "")]
        if not shade:
            continue
        # Walk up while the path back to the border is geometrically neutral.
        node = group
        while node in parents:
            if node.get("transform") not in _IDENTITY_TRANSFORMS:
                break  # a transform between border and shade would move the border - leave it
            parent = parents[node]
            border = next((c for c in parent if stroked_border(c)), None)
            if border is not None:
                parent.remove(border)
                group.insert(list(group).index(shade[-1]) + 1, border)
                break
            node = parent


def _layer_axes_below_marks(root: ET.Element) -> None:
    """Re-order SVG children into fill -> grid -> axes and border -> data marks.

    Vega emits the view border before all content, so grid lines paint over the
    border edges when closed=True; it also interleaves axis groups with no regard
    for the mark stack. This fix moves non-grid axis groups (domain lines, ticks,
    labels) and any stroked border path to sit after the grid but before the data
    marks: the grid does not overlap the border, and a datum plotted exactly on
    an axis renders over the axis line instead of being cut by it. This differs
    from the matplotlib/ggplot frame-on-top convention.

    Grid axis groups (identified by containing a mark-rule role-axis-grid
    descendant) are left in place at the front of the stack.

    viewFill + closed interaction: when the background path carries both a fill
    (viewFill) and a stroke (closed border), moving the whole element would place
    the fill on top of the grid. Instead, the original element is stripped to
    fill-only (stroke="none") and a stroke-only clone is inserted at the axis
    position, so the fill stays at the very back and the border sits with the
    axes - above grid, below marks.
    """
    import copy

    def _is_grid_axis(el: ET.Element) -> bool:
        return any(g.get("class", "") == "mark-rule role-axis-grid" for g in el.iter(f"{{{_SVG_NS}}}g"))

    def reorder(el: ET.Element) -> None:
        to_place = []  # axis groups + border strokes, re-inserted after the grid block
        shade = []  # shade backgrounds, placed behind the grid (not over an axis or border)
        for child in list(el):
            cls = child.get("class", "")
            if _SHADE_PREFIX in cls:
                el.remove(child)
                shade.append(child)
            elif cls == "mark-group role-axis" and not _is_grid_axis(child):
                el.remove(child)
                to_place.append(child)
            elif (
                child.tag == f"{{{_SVG_NS}}}path"
                and cls == "background"
                and child.get("stroke") not in (None, "none")
                and child.get("display") != "none"
            ):
                fill = child.get("fill")
                has_fill = fill is not None and fill not in ("none", "")
                if has_fill:
                    # Background has both fill (viewFill) and stroke (closed border).
                    # Keep fill-only original in place; place a stroke-only clone.
                    border_clone = copy.deepcopy(child)
                    border_clone.set("fill", "none")
                    child.set("stroke", "none")
                    to_place.append(border_clone)
                else:
                    el.remove(child)
                    to_place.append(child)
        if to_place:
            # Insertion point: after the leading background + grid-axis block (the
            # only axis groups left are grids), before the first data-mark child.
            index = len(list(el))
            for i, child in enumerate(el):
                cls = child.get("class", "")
                if child.tag == f"{{{_SVG_NS}}}path" and cls == "background":
                    continue
                if cls == "mark-group role-axis":
                    continue
                index = i
                break
            for offset, item in enumerate(to_place):
                el.insert(index + offset, item)
        if shade:
            # Directly after the background fill, so shading remains below the grid, axes, and data
            # and does not cover the frame.
            at = 0
            for i, child in enumerate(el):
                if child.tag == f"{{{_SVG_NS}}}path" and child.get("class", "") == "background":
                    at = i + 1
                else:
                    break
            for offset, item in enumerate(shade):
                el.insert(at + offset, item)
        for child in el:
            reorder(child)

    reorder(root)


def _simplify_svg(root: ET.Element) -> None:
    """
    Reduce SVG grouping depth by inlining structurally redundant ``<g>`` elements.

    Altair/Vega generates deeply nested ``<g>`` wrappers for its internal mark
    grouping system (e.g. ``role-frame``, ``role-mark``, ``mark-symbol``). These
    groups carry only a ``class`` attribute and have no effect on visual output,
    but they require extra double-clicks to navigate in Adobe Illustrator and
    other SVG editors.

    This function removes those wrappers by inlining their children directly into
    the parent element. Two classes of ``<g>`` are flattened:

    1. Groups with no rendering-relevant attributes (only ``class`` or nothing).
    2. Groups whose only rendering attribute is ``transform="translate(0,0)"`` –
       a translation with no visual effect that Vega emits as a structural wrapper
       around chart content. Removing it eliminates one group level to remove in
       Illustrator without affecting visual output.

    Groups that carry any of the following attributes are preserved: ``clip-path``,
    ``opacity``, ``mask``, ``filter``, ``style``, ``id``, or any non-trivial
    ``transform``. Definition blocks (``<defs>``, ``<clipPath>``, ``<symbol>``)
    are left entirely untouched.

    The result is a flatter SVG with the same rendered appearance.
    """
    KEEP_ATTRS = {"transform", "clip-path", "opacity", "mask", "filter", "style", "id"}
    SKIP_TAGS = {f"{{{_SVG_NS}}}defs", f"{{{_SVG_NS}}}clipPath", f"{{{_SVG_NS}}}symbol"}

    _NOOP_TRANSLATE = re.compile(r"translate\(\s*0(?:\.0+)?\s*[,\s]\s*0(?:\.0+)?\s*\)$")

    def _is_noop(child) -> bool:
        effective = set(child.attrib) & KEEP_ATTRS
        if not effective:
            return True
        # translate(0,0) has no visual effect – safe to inline.
        if effective == {"transform"} and _NOOP_TRANSLATE.match(child.get("transform", "")):
            return True
        return False

    def _flatten(parent):
        if parent.tag in SKIP_TAGS:
            return
        i = 0
        while i < len(parent):
            child = parent[i]
            _flatten(child)
            if child.tag == f"{{{_SVG_NS}}}g" and _is_noop(child):
                grandchildren = list(child)
                parent.remove(child)
                for j, gc in enumerate(grandchildren):
                    parent.insert(i + j, gc)
                if not grandchildren:
                    i += 1
            else:
                i += 1

    _flatten(root)
