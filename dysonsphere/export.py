from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

import altair as alt

if TYPE_CHECKING:
    pass


def save(
    chart: alt.Chart | Callable[[], alt.Chart],
    filename: str,
    ppi: int = 1200,
    description: str | None = None,
    saveVegaSpec: bool = True,
    background: list[str] = ["light", "dark"],
) -> None:
    """
    Save a chart as light and dark PNG and SVG files.

    Produces up to four files from a single call:

    - ``<filename>_light.png`` and ``<filename>_light.svg``
    - ``<filename>_dark.png`` and ``<filename>_dark.svg``

    Dark and light versions are rendered by temporarily toggling
    ``darkmode`` in the theme options, leaving all other options intact.

    Parameters
    ----------
    chart:
        The Altair chart to save, or a zero-argument callable that returns
        one. When a callable is provided it is called fresh for each
        light/dark variant — after ``darkmode`` has been toggled — so any
        marks whose colours depend on ``ds.theme()`` (e.g.
        ``add_multilabel``) are rebuilt with the correct palette each
        time.
    filename:
        Extensionless path for the output files (e.g. ``"myplot"`` or
        ``"plots/myplot"``). A bare name saves to the current working
        directory, matching Altair's default behaviour.
    ppi:
        Pixel density for PNG output.
    description:
        Optional description embedded in the chart via ``chart.properties(description=...)``.
        Appears as a ``<desc>`` element in SVG output.
    saveVegaSpec:
        If ``True``, also writes ``<filename>.json`` containing the full Vega-Lite spec.
    background:
        Which background variants to render. Defaults to ``["light", "dark"]``. Pass
        ``["light"]`` or ``["dark"]`` to render only one variant.

    Examples
    --------
    Static chart (existing behaviour)::

        ds.theme()
        chart = alt.Chart(df).mark_point().encode(...)
        ds.save(chart, "plots/myplot")

    Callable — rebuilt per variant so dark-mode colours are correct::

        ds.save(
            lambda: ds.add_multilabel(chart, CONDITIONS, style="symbol"),
            "plots/myplot",
        )
    """
    if not alt.theme.options:
        raise RuntimeError("ds.theme() must be called before ds.save().")

    # _resolve() is called once per variant (or once for the spec).
    # When chart is a callable it is re-invoked each time so that any
    # marks whose colours read from alt.theme.options at construction time
    # (e.g. add_multilabel dot colours) pick up the correct
    # darkmode value that was just toggled above.
    def _resolve() -> alt.Chart:
        c = chart() if callable(chart) else chart
        return c.properties(description=description) if description is not None else c

    base = Path(filename)
    original_darkmode = alt.theme.options.get("darkmode", False)
    original_transparent = alt.theme.options.get("transparentBackground", False)

    if saveVegaSpec:
        _resolve().save(str(base.parent / f"{base.name}_vegalite.json"))

    try:
        import vl_convert as vlc

        _background_map = {"light": (False, "_light"), "dark": (True, "_dark")}
        invalid = [b for b in background if b not in _background_map]
        if invalid:
            raise ValueError(f"background must contain 'light' and/or 'dark', got {invalid!r}")

        alt.theme.options["transparentBackground"] = True
        for mode, suffix in [_background_map[b] for b in background]:
            alt.theme.options["darkmode"] = mode
            # _resolve() re-calls chart() here so darkmode-sensitive colours are baked correctly
            svg_path = str(base.parent / f"{base.name}{suffix}.svg")
            _resolve().save(svg_path)
            _fix_tick_alignment(
                svg_path,
                band_padding=alt.theme.options.get("bandPadding", 0.1),
                chart_width=alt.theme.options.get("chartWidth", 100),
            )
            _layer_axes_to_front(svg_path)
            _simplify_svg(svg_path)
            with open(svg_path, encoding="utf-8") as f:
                svg_content = f.read()
            png_path = str(base.parent / f"{base.name}{suffix}.png")
            Path(png_path).write_bytes(vlc.svg_to_png(svg_content, ppi=ppi))
    finally:
        alt.theme.options["darkmode"] = original_darkmode
        alt.theme.options["transparentBackground"] = original_transparent


def _fix_tick_alignment(path: str, band_padding: float = 0.1, chart_width: float = 100.0) -> None:
    """Move x-axis tick lines from Vega's floor'd integer positions to exact mark centers.

    Vega snaps axis tick group transforms to integers for crisp screen rendering but
    keeps mark coordinates as floats.  At high DPI (scale ≥ 4) this produces visible
    misalignment.

    For bar charts: tick centers are read from the bar path data (aria-roledescription="bar").
    For all other charts (strip, violin, etc.): band centers are computed analytically
    from the number of categories and theme scale parameters, then ticks are moved to
    those float positions.  A validation step ensures the fix is only applied to nominal
    band scales — quantitative and time axes are left untouched.
    """
    import re
    import xml.etree.ElementTree as ET

    NS = "http://www.w3.org/2000/svg"
    ET.register_namespace("", NS)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

    tree = ET.parse(path)
    root = tree.getroot()

    # --- bar charts: read centers from path data ---
    bar_centers: list[float] = []
    for el in root.iter(f"{{{NS}}}path"):
        if el.get("aria-roledescription") != "bar":
            continue
        d = el.get("d", "")
        m = re.match(r"M([\d.]+),[-\d.e+]+h([\d.]+)", d)
        if m:
            bar_centers.append(round(float(m.group(1)) + float(m.group(2)) / 2, 4))

    if bar_centers:
        unique_centers = sorted(set(bar_centers))

        def nearest(tick_x: float) -> float | None:
            c = min(unique_centers, key=lambda v: abs(v - tick_x))
            return c if abs(c - tick_x) < 2.0 else None

        def apply_bar_fix(el: ET.Element) -> None:
            for child in el:
                cls = child.get("class", "")
                if cls in ("mark-rule role-axis-tick", "mark-rule role-axis-grid"):
                    for line in child:
                        t = line.get("transform", "")
                        m = re.match(r"translate\((\d+(?:\.\d+)?),([-\d.]+)\)$", t)
                        if m:
                            c = nearest(float(m.group(1)))
                            if c is not None:
                                line.set("transform", f"translate({c},{m.group(2)})")
                else:
                    apply_bar_fix(child)

        apply_bar_fix(root)

    else:
        # --- non-bar charts: compute band centers analytically ---
        # Collect integer tick x positions from all x-axis tick groups.
        tick_xs: list[float] = []

        def collect_ticks(el: ET.Element) -> None:
            for child in el:
                if child.get("class", "") == "mark-rule role-axis-tick":
                    for line in child:
                        t = line.get("transform", "")
                        m = re.match(r"translate\((\d+(?:\.\d+)?),0\)$", t)
                        if m:
                            v = float(m.group(1))
                            if v > 0:
                                tick_xs.append(v)
                else:
                    collect_ticks(child)

        collect_ticks(root)
        if not tick_xs:
            return

        # Deduplicate: hconcat panels repeat the same tick positions for each view.
        # Keep unique positions; the center_map lookup handles all occurrences uniformly.
        tick_xs = list(set(tick_xs))

        # Three scale formulas tried in order. Validation matches actual SVG integer positions
        # to the expected floor/round of each formula — only the matching formula is applied,
        # ensuring we don't touch quantitative or time axes.
        #
        #   0. Band, paddingInner=0 (xOffset charts), paddingOuter=band_padding
        #      step = W / (n + 2·bp);  center_i = step·(bp + i + 0.5)
        #      Vega uses Math.floor
        #
        #   pi. Band, paddingInner=paddingOuter=band_padding (bar/violin without xOffset)
        #      step = W / (n + bp);  center_i = step·(i + 0.5 + bp/2)
        #      Vega uses Math.floor
        #
        #   pt. Point scale, pointPadding=0.5 (Vega-Lite default for scatter/strip marks)
        #      step = W / n;  position_i = step·(0.5 + i)
        #      Vega uses Math.round
        n = len(tick_xs)
        sorted_ticks = sorted(tick_xs)

        step0 = chart_width / (n + 2 * band_padding)
        expected0 = [int(step0 * (band_padding + i + 0.5)) for i in range(n)]

        step_pi = chart_width / (n + band_padding)
        expected_pi = [int(step_pi * (i + 0.5 + band_padding / 2)) for i in range(n)]

        step_pt = chart_width / n
        expected_pt = [round(step_pt * (0.5 + i)) for i in range(n)]

        actual_int = [int(t) for t in sorted_ticks]
        if actual_int == expected0:
            center_map = {
                t: round(step0 * (band_padding + i + 0.5), 4) for i, t in enumerate(sorted_ticks)
            }
        elif actual_int == expected_pi:
            center_map = {
                t: round(step_pi * (i + 0.5 + band_padding / 2), 4)
                for i, t in enumerate(sorted_ticks)
            }
        elif actual_int == expected_pt:
            center_map = {t: round(step_pt * (0.5 + i), 4) for i, t in enumerate(sorted_ticks)}
        else:
            return

        def apply_analytic_fix(el: ET.Element) -> None:
            for child in el:
                cls = child.get("class", "")
                if cls in ("mark-rule role-axis-tick", "mark-rule role-axis-grid"):
                    for line in child:
                        t = line.get("transform", "")
                        m = re.match(r"translate\((\d+(?:\.\d+)?),([-\d.]+)\)$", t)
                        if m:
                            c = center_map.get(float(m.group(1)))
                            if c is not None:
                                line.set("transform", f"translate({c},{m.group(2)})")
                else:
                    apply_analytic_fix(child)

        apply_analytic_fix(root)

    with open(path, "w", encoding="utf-8") as f:
        f.write(ET.tostring(root, encoding="unicode"))


def _layer_axes_to_front(path: str) -> None:
    """Re-order SVG children so axis domain/tick elements and the view border render last.

    Vega emits axis groups (domain lines, ticks, labels) before data marks, so marks
    can visually overlap axis lines. It also emits the view border before all content,
    so grid lines overlap the border edges when closed=True. This fix moves non-grid
    axis groups and any stroked border path to render after data marks, ensuring axes
    always visually bound the view on all sides regardless of closed.

    Grid axis groups (identified by containing a mark-rule role-axis-grid descendant)
    are left in place so data marks continue to render on top of grid lines.
    """
    import xml.etree.ElementTree as ET

    NS = "http://www.w3.org/2000/svg"
    ET.register_namespace("", NS)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

    def _is_grid_axis(el: ET.Element) -> bool:
        return any(g.get("class", "") == "mark-rule role-axis-grid" for g in el.iter(f"{{{NS}}}g"))

    tree = ET.parse(path)
    root = tree.getroot()

    def reorder(el: ET.Element) -> None:
        axis_groups = []
        border_paths = []
        for child in list(el):
            cls = child.get("class", "")
            if cls == "mark-group role-axis" and not _is_grid_axis(child):
                axis_groups.append(child)
            elif (
                child.tag == f"{{{NS}}}path"
                and cls == "background"
                and child.get("stroke") not in (None, "none")
                and child.get("display") != "none"
            ):
                border_paths.append(child)
        for item in axis_groups + border_paths:
            el.remove(item)
            el.append(item)
        for child in el:
            reorder(child)

    reorder(root)
    with open(path, "w", encoding="utf-8") as f:
        f.write(ET.tostring(root, encoding="unicode"))


def _simplify_svg(path: str) -> None:
    """
    Reduce SVG grouping depth by inlining structurally redundant ``<g>`` elements.

    Altair/Vega generates deeply nested ``<g>`` wrappers for its internal mark
    grouping system (e.g. ``role-frame``, ``role-mark``, ``mark-symbol``). These
    groups carry only a ``class`` attribute and have no effect on visual output,
    but they require extra double-clicks to navigate in Adobe Illustrator and
    other SVG editors.

    This function removes those wrappers by inlining their children directly into
    the parent element. Groups that carry any of the following attributes are
    preserved because they affect rendering or layout: ``transform``,
    ``clip-path``, ``opacity``, ``mask``, ``filter``, ``style``, ``id``.
    Definition blocks (``<defs>``, ``<clipPath>``, ``<symbol>``) are left
    entirely untouched.

    The result is a flatter, editor-friendly SVG that renders identically to the
    original.
    """
    import xml.etree.ElementTree as ET

    NS = "http://www.w3.org/2000/svg"
    ET.register_namespace("", NS)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

    KEEP_ATTRS = {"transform", "clip-path", "opacity", "mask", "filter", "style", "id"}
    SKIP_TAGS = {f"{{{NS}}}defs", f"{{{NS}}}clipPath", f"{{{NS}}}symbol"}

    def _flatten(parent):
        if parent.tag in SKIP_TAGS:
            return
        i = 0
        while i < len(parent):
            child = parent[i]
            _flatten(child)
            if child.tag == f"{{{NS}}}g" and not (set(child.attrib) & KEEP_ATTRS):
                grandchildren = list(child)
                parent.remove(child)
                for j, gc in enumerate(grandchildren):
                    parent.insert(i + j, gc)
                if not grandchildren:
                    i += 1
            else:
                i += 1

    tree = ET.parse(path)
    _flatten(tree.getroot())
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write(ET.tostring(tree.getroot(), encoding="unicode"))
