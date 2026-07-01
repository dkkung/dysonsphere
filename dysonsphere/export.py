from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Union, cast

import altair as alt

from . import metadata

_AltairChart = Union[
    alt.Chart,
    alt.LayerChart,
    alt.FacetChart,
    alt.VConcatChart,
    alt.HConcatChart,
    alt.ConcatChart,
]

_VALID_FORMATS = ("svg", "png", "json")
_VALID_BACKGROUNDS = ("light", "dark")


def _resolve_choice(value, default, valid: tuple[str, ...], name: str) -> list[str]:
    """Normalize a str-or-list ``save()`` choice (falling back to the theme ``default``) to a
    validated, non-empty list.  Raises ``ValueError`` on an empty list or unknown value.
    """
    raw = value if value is not None else default
    items = [raw] if isinstance(raw, str) else list(raw)
    if not items:
        raise ValueError(f"{name} must be non-empty; got {raw!r}")
    invalid = [x for x in items if x not in valid]
    if invalid:
        raise ValueError(f"{name} must be one of {valid}, got {invalid!r}")
    return items


def save(
    chart: _AltairChart | Callable[[], _AltairChart],
    filename: str,
    ppi: int = 1200,
    description: str | None = None,
    saveMetadata: bool = True,
    embedReport: bool = True,
    format: str | list[str] | None = None,
    background: str | list[str] | None = None,
) -> None:
    """
    Save a chart in one or more formats and background variants.

    Which files are written is controlled by ``format`` (``"svg"``/``"png"``/``"json"``)
    and ``background`` (``"light"``/``"dark"``), each defaulting to the theme options
    ``saveFormat`` / ``saveBackground``. A background suffix (``_light`` / ``_dark``) is
    added **only when more than one background** is rendered — a single-background export
    keeps clean names::

        ds.save(chart, "fig")                      # fig.svg + fig.json   (defaults)
        ds.save(chart, "fig", format="png")        # fig.png
        ds.save(chart, "fig", background=["light", "dark"])
        #   → fig_light.svg / fig_dark.svg + fig_light.json / fig_dark.json

    Each background toggles ``darkmode`` for its render, restoring the original after.

    Parameters
    ----------
    chart:
        The Altair chart to save, or a zero-argument callable that returns
        one. Accepts any Altair compound chart type: ``Chart``,
        ``LayerChart``, ``FacetChart``, ``VConcatChart``, ``HConcatChart``,
        or ``ConcatChart``. When a callable is provided it is called fresh
        for each variant — after ``darkmode`` has been toggled — so any marks
        whose colours depend on ``ds.theme()`` (e.g. ``add_multilabel``) are
        rebuilt with the correct palette each time.
    filename:
        Extensionless path for the output files (e.g. ``"myplot"`` or
        ``"plots/myplot"``). A bare name saves to the current working
        directory, matching Altair's default behaviour.
    ppi:
        Pixel density for PNG output.
    description:
        Optional, purely your own text. Stored verbatim (nothing appended) in the
        Vega-Lite JSON spec's ``description`` field, the SVG ``<desc>`` element, and the
        PNG ``iTXt Description`` chunk. Independent of ``saveMetadata``.
    format:
        Which file format(s) to write: any of ``"svg"``, ``"png"``, ``"json"`` (the raw
        Vega-Lite spec), as a single string or a list. ``None`` (default) uses the theme
        option ``saveFormat`` (``["svg", "json"]``). An empty list or unknown value raises.
    background:
        Which background variant(s) to render: ``"light"`` and/or ``"dark"`` (each toggles
        ``darkmode``), as a single string or a list. ``None`` (default) uses the theme
        option ``saveBackground`` (``"light"``). An empty list or unknown value raises.
    saveMetadata:
        If ``True`` (default), embeds a **structured JSON** metadata block —
        ``{"provenance": {...}, "statistics": [...]}`` — in every output format so each
        is self-contained and machine-readable:

        - ``provenance`` — generation facts as fields: ``user``, ``script``,
          ``timestamp`` (ISO-8601), ``python``, ``altair``, ``dysonsphere``. In Jupyter,
          ``script`` is ``"<jupyter-notebook>"``; ``user`` falls back to ``"unknown_user"``.
        - ``statistics`` — the structured records queued by ``add_comparisons`` (groups,
          omnibus result, comparisons with exact p-values and effect sizes); omitted when
          there are none.

        It lands in the **Vega-Lite JSON** under ``usermeta.dysonsphere`` (merged into any
        ``usermeta`` already on the chart), the **SVG** ``<metadata id="dysonsphere">``
        element (CDATA), and the **PNG** ``iTXt dysonsphere`` chunk.

        ``saveMetadata=False`` suppresses the structured block entirely; your
        ``description`` (if any) is still written.
    embedReport:
        If ``True`` (default) and ``saveMetadata`` is on, also embeds the human-readable
        **report table** (the descriptive + effect-size text from ``add_comparisons`` /
        ``add_correlation``) so you can read it straight out of the file — as a ``report``
        member of ``usermeta.dysonsphere`` in the **JSON**, and as a dedicated readable
        channel (real newlines, not escaped JSON) in the **SVG**
        (``<metadata id="dysonsphere-report">``) and **PNG** (``iTXt dysonsphere-report``).
        It never touches ``description`` (your text only). Set ``False`` to keep just the
        structured block. (Also available standalone via ``add_comparisons(report=True)``.)

    Examples
    --------
    Static chart::

        ds.theme()
        chart = alt.Chart(df).mark_point().encode(...)
        ds.save(chart, "plots/myplot")

    Callable — rebuilt per variant so dark-mode colours are correct::

        ds.save(
            lambda: ds.add_multilabel(chart, CONDITIONS, style="symbol"),
            "plots/myplot",
            background=["light", "dark"],
        )
    """
    if not alt.theme.options:
        raise RuntimeError("ds.theme() must be called before ds.save().")

    # Resolve format/background (str or list) against the theme defaults, then validate up
    # front — before draining — so an invalid request errors cleanly and leaves the queue
    # for the next real save().
    _formats = _resolve_choice(format, alt.theme.options.get("saveFormat", ["svg", "json"]), _VALID_FORMATS, "format")
    _backgrounds = _resolve_choice(
        background, alt.theme.options.get("saveBackground", ["light"]), _VALID_BACKGROUNDS, "background"
    )

    # Records are NOT drained here.  Instead, each add_comparisons()/add_correlation() tagged
    # its annotation layer with a marker name; below we resolve the chart, find which markers
    # are actually present, and embed ONLY those records — so a record from a chart that was
    # built but never saved can't contaminate this save.  `exportIdentifier` + `timestamp` are
    # generated once (shared by every variant of this export); the checksum is per-variant.
    from .statistics import _select_reports

    export_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Resolve the base chart (callable re-invoked each variant so darkmode-sensitive colours
    # rebuild correctly).  The `description` property feeds the JSON spec's description key
    # (user text only); the dysonsphere block is attached to the JSON dict / injected into the
    # SVG+PNG below, never here.
    def _resolve_base() -> _AltairChart:
        c = cast(_AltairChart, chart() if callable(chart) else chart)  # ty: ignore[call-top-callable]
        if description is not None:
            c = c.properties(description=description)
        return c

    out = Path(filename)
    multi = len(_backgrounds) > 1

    def _path(bg: str, ext: str) -> str:
        return str(out.parent / f"{out.name}{'_' + bg if multi else ''}.{ext}")

    _want_render = "svg" in _formats or "png" in _formats
    original_darkmode = alt.theme.options.get("darkmode", False)
    original_transparent = alt.theme.options.get("transparentBackground", False)
    try:
        if _want_render:
            import vl_convert as vlc

        for bg in _backgrounds:
            alt.theme.options["darkmode"] = bg == "dark"
            # The spec is captured at the chart's logical transparency (for the JSON + the
            # checksum); the SVG/PNG re-render below with transparentBackground on.
            alt.theme.options["transparentBackground"] = original_transparent
            base_obj = _resolve_base()
            spec = base_obj.to_dict()
            _hashes = metadata._scan_marker_hashes(spec) if saveMetadata else set()
            _records = _select_reports(_hashes)
            metadata._strip_markers(spec)  # markers are internal — never in the written output
            _usermeta = _usermeta_json = _report_sections = None
            if saveMetadata:
                _usermeta, _usermeta_json, _report_sections = metadata._build_block(
                    _records,
                    embed_report=embedReport,
                    export_id=export_id,
                    timestamp=timestamp,
                    checksum=metadata._spec_checksum(spec),
                )

            if "json" in _formats:
                jspec = dict(spec)
                if _usermeta is not None:
                    base_um = jspec["usermeta"] if isinstance(jspec.get("usermeta"), dict) else {}
                    jspec["usermeta"] = {**base_um, **_usermeta}
                Path(_path(bg, "json")).write_text(json.dumps(jspec, ensure_ascii=False, indent=2), encoding="utf-8")

            if _want_render:
                alt.theme.options["transparentBackground"] = True
                svg_path = _path(bg, "svg")
                base_obj.save(svg_path)  # marker names are in the object but never render into SVG
                _fix_tick_alignment(
                    svg_path,
                    band_padding=alt.theme.options.get("bandPadding", 0.1),
                    chart_width=alt.theme.options.get("chartWidth", 100),
                    axis_offset=0
                    if alt.theme.options.get("closed")
                    else (alt.theme.options.get("axisOffset") or alt.theme.options.get("tickSize", 3)),
                )
                _fix_log_minor_ticks(svg_path)
                _layer_axes_to_front(svg_path)
                _simplify_svg(svg_path)
                _fix_superscript_labels(svg_path)
                with open(svg_path, encoding="utf-8") as f:
                    svg_content = f.read()
                # Inject the metadata channels + user <desc> after the opening <svg> tag.  A
                # lambda replacement keeps backslashes/braces in the JSON literal (not regex).
                _inserts = metadata._svg_inserts(_usermeta_json, _report_sections, description)
                if _inserts:
                    svg_content = re.sub(r"(<svg[^>]*>)", lambda m: m.group(1) + _inserts, svg_content, count=1)
                    Path(svg_path).write_text(svg_content, encoding="utf-8")
                if "png" in _formats:
                    png_bytes = vlc.svg_to_png(svg_content, ppi=ppi)
                    png_bytes = metadata._inject_png_block(png_bytes, _usermeta_json, _report_sections, description)
                    Path(_path(bg, "png")).write_bytes(png_bytes)
                if "svg" not in _formats:
                    Path(svg_path).unlink()  # transient — only rendered as the PNG source
    finally:
        alt.theme.options["darkmode"] = original_darkmode
        alt.theme.options["transparentBackground"] = original_transparent


def load(path: str, *, raw: bool = False, applyTheme: bool = True) -> "_AltairChart | dict":
    """Rebuild the chart from a dysonsphere-exported Vega-Lite JSON (the ``.json`` spec).

    JSON only — the PNG/SVG carry the metadata block but not the full spec.

    Parameters
    ----------
    raw:
        ``False`` (default) returns a composable Altair object (of the right type). Its
        theme ``config`` is stripped (Altair's schema rejects a few of dysonsphere's
        config values), so it comes back unstyled — see ``applyTheme``. ``True`` returns
        the raw Vega-Lite spec ``dict`` instead, ``config`` intact, which re-renders
        pixel-identically (e.g. via ``vl_convert``) but is not a composable Altair object.
    applyTheme:
        For ``raw=False``: ``True`` (default) re-applies the theme baked into the file via
        ``ds.theme(**saved_args)`` so the object renders exactly as saved. Like any
        ``ds.theme()`` call this **replaces the active theme globally**. ``False`` leaves
        the current theme untouched (the object is styled by whatever theme is active).
    """
    p = Path(path)
    if p.suffix.lower() != ".json":
        raise ValueError(f"load() needs the Vega-Lite JSON (the .json spec), got {p.suffix!r}")
    spec = json.loads(p.read_text(encoding="utf-8"))
    if raw:
        return spec
    if applyTheme:
        theme_args = ((spec.get("usermeta") or {}).get("dysonsphere") or {}).get("theme")
        if theme_args:
            from .theme import theme as _theme

            _theme(**theme_args)
    # Strip config (schema-incompatible) and usermeta before parsing into an Altair object.
    stripped = {k: v for k, v in spec.items() if k not in ("config", "usermeta")}
    return cast("_AltairChart", alt.Chart.from_dict(stripped))


def _fix_tick_alignment(
    path: str, band_padding: float = 0.1, chart_width: float = 100.0, axis_offset: float = 0.0
) -> None:
    """Move x-axis tick and grid lines from Vega's floor'd integer positions to exact mark centers.

    Vega snaps axis tick/grid group transforms to integers for crisp screen rendering but
    keeps mark coordinates as floats.  At high DPI (scale ≥ 4) this produces visible
    misalignment.

    Handles both mark-rule role-axis-tick and mark-rule role-axis-grid groups.  Tick lines
    use translate(x,0); grid lines use translate(x,-chartHeight) with y2=chartHeight.  Both
    formats are matched by the collection regex; grid lines are distinguished by |ty| > 50.

    For bar charts: tick centers are read from the bar path data (aria-roledescription="bar").
    For all other charts (strip, violin, etc.): band centers are computed analytically
    from the number of categories and theme scale parameters, then ticks and grid lines are
    moved to those float positions.  A validation step ensures the fix is only applied to
    nominal band scales — quantitative and time axes are left untouched.  When two band-scale
    formulas (Case pi and Case 0) floor to the same integers, box mark x-centers
    (aria-roledescription="box") are used to resolve the ambiguity.

    axis_offset: the theme's effective axis offset (tickSize when axisOffset is None, 0 when
    closed=True).  Grid lines' y-span is extended by this amount so they reach the top chart
    border despite the axis group being positioned axis_offset pixels below chartHeight.
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
        # Process each <g class="mark-rule role-axis-tick|grid"> independently.
        # hconcat panels with different mark types (strip=Case 0, violin=Case pi)
        # produce different integer tick positions; processing them as one set
        # yields 2n unique positions that match no formula. Per-group processing
        # lets each panel's axis be matched and corrected with its own formula.
        #
        # Three scale formulas per group:
        #   pi. Band, paddingInner=paddingOuter=band_padding (boxplot/violin)
        #      step = W / (n + bp);  center_i = step·(i + 0.5 + bp/2)
        #   0.  Band, paddingInner=0 (xOffset/strip), paddingOuter=band_padding
        #      step = W / (n + 2·bp);  center_i = step·(bp + i + 0.5)
        #   pt. Point scale, pointPadding=0.5 (default for scatter/strip marks)
        #      step = W / n;  position_i = step·(0.5 + i)
        # All use Vega's Math.floor (or Math.round for pt).

        # Global box mark centers for ambiguous-case disambiguation (pi and 0
        # floor to the same integers, e.g. n=6, W=100, bp=0.1).
        box_ctr: list[float] = []
        for el in root.iter(f"{{{NS}}}path"):
            if el.get("aria-roledescription") == "box":
                mb = re.match(r"M([\d.]+),[-\d.e+]+L([\d.]+),", el.get("d", ""))
                if mb:
                    box_ctr.append((float(mb.group(1)) + float(mb.group(2))) / 2)
        sorted_box = sorted(box_ctr)

        _AXIS_CLS = {"mark-rule role-axis-tick", "mark-rule role-axis-grid"}
        modified_any = False
        for g in root.iter(f"{{{NS}}}g"):
            if g.get("class") not in _AXIS_CLS:
                continue
            # Collect unique local x positions for this axis group.
            xs: list[float] = []
            for line in g:
                m = re.match(r"translate\((\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)\)$", line.get("transform", ""))
                if m:
                    v = float(m.group(1))
                    if v > 0:
                        xs.append(v)
            if not xs:
                continue
            xs = sorted(set(xs))
            n = len(xs)

            step0 = chart_width / (n + 2 * band_padding)
            expected0 = [int(step0 * (band_padding + i + 0.5)) for i in range(n)]

            step_pi = chart_width / (n + band_padding)
            expected_pi = [int(step_pi * (i + 0.5 + band_padding / 2)) for i in range(n)]

            step_pt = chart_width / n
            expected_pt = [round(step_pt * (0.5 + i)) for i in range(n)]

            actual_int = [int(v) for v in xs]
            if actual_int == expected_pi and actual_int == expected0:
                if not sorted_box:
                    continue
                pi_err = sum(abs(b - step_pi * (i + 0.5 + band_padding / 2)) for i, b in enumerate(sorted_box))
                z0_err = sum(abs(b - step0 * (band_padding + i + 0.5)) for i, b in enumerate(sorted_box))
                if pi_err < z0_err:
                    center_map = {v: round(step_pi * (i + 0.5 + band_padding / 2), 4) for i, v in enumerate(xs)}
                else:
                    center_map = {v: round(step0 * (band_padding + i + 0.5), 4) for i, v in enumerate(xs)}
            elif actual_int == expected_pi:
                center_map = {v: round(step_pi * (i + 0.5 + band_padding / 2), 4) for i, v in enumerate(xs)}
            elif actual_int == expected0:
                center_map = {v: round(step0 * (band_padding + i + 0.5), 4) for i, v in enumerate(xs)}
            elif actual_int == expected_pt:
                center_map = {v: round(step_pt * (0.5 + i), 4) for i, v in enumerate(xs)}
            else:
                continue

            is_grid = g.get("class") == "mark-rule role-axis-grid"
            for line in g:
                m = re.match(r"translate\(([\d.]+),([-\d.]+)\)$", line.get("transform", ""))
                if m:
                    c = center_map.get(float(m.group(1)))
                    if c is not None:
                        ty = float(m.group(2))
                        if is_grid and ty < -50 and axis_offset > 0:
                            y2 = line.get("y2")
                            if y2 is not None and float(y2) > 50:
                                line.set("y2", str(float(y2) + axis_offset))
                            ty -= axis_offset
                        line.set("transform", f"translate({c},{ty})")
                        modified_any = True

        if not modified_any:
            return

    with open(path, "w", encoding="utf-8") as f:
        f.write(ET.tostring(root, encoding="unicode"))


def _fix_log_minor_ticks(path: str) -> None:
    """Correct integer-rounded SVG positions for log- and power-scale minor ticks.

    Vega rounds all SVG tick transforms to integers. When the chart dimension
    is not divisible by the number of intervals, each interval gets a slightly
    different pixel span, making minor tick spacings visually inconsistent at
    high DPI. This function recomputes each minor tick's exact fractional
    position within its enclosing major-tick interval and writes it back.

    Handles both axes:
      Y-axis: translate(0,N) lines with x2 < 0. Corrects the N (y-coordinate).
      X-axis: translate(N,0) lines with 0 < y2 < 20 (excludes mark_rule
              elements whose y2 equals the full chart height).

    Spacing detection: two distinct tick sizes (major vs minor) must be present
    in a context group. Gap-uniformity test on the first interval distinguishes
    base-10 (non-uniform 2×–9× pattern, max_gap > 2 × min_gap) from uniform
    equal-visual-space (power-scale or non-base-10 log).

    Three design points worth noting:

    Per-panel grouping: ticks are collected with their accumulated (cx, cy)
    parent-transform context. Each unique (cx, cy) is a separate panel
    coordinate space (hconcat panels differ in cx, vconcat in cy). Processing
    per group prevents major ticks from a linear axis in one panel from
    corrupting interval detection in a log/power axis in another.

    Strict upper interval bound: the interval check uses lo - 1 <= pos <= hi
    (not hi + 1). Minor ticks are strictly between major ticks in data space,
    so Vega's integer rounding can only push a tick downward — never past hi.
    A hi + 1 tolerance caused the 9× tick (1 px above the next major tick) to
    match the wrong interval and be displaced.

    Independent if-branches for translate(0,0): the leftmost x-axis tick has
    this exact transform, which also matches the y-axis regex translate(0,...).
    Both pattern checks are independent if-branches so the x-axis branch still
    runs when the y-axis branch enters but fails x2 < 0, preventing the x=0
    major tick from being silently dropped and the first interval left
    uncorrectable.
    """
    import math
    import re
    import xml.etree.ElementTree as ET

    NS = "http://www.w3.org/2000/svg"
    ET.register_namespace("", NS)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

    tree = ET.parse(path)
    root = tree.getroot()
    changed = False

    _TRANSLATE = re.compile(r"translate\(\s*([0-9.-]+)\s*[,\s]\s*([0-9.-]+)\s*\)")

    def _correct_axis(major_positions: list[float], minor_els: list, is_x: bool) -> None:
        nonlocal changed
        n = len(major_positions) - 1
        if n < 1 or not minor_els:
            return
        # Detect uniform vs non-uniform from first interval.
        lo1, hi1 = major_positions[0], major_positions[1]
        interval1 = sorted(p for _, p in minor_els if lo1 - 1.0 <= p <= hi1)
        if not interval1:
            return
        n_minor = len(interval1)
        is_nonuniform = False
        if n_minor >= 2:
            gaps = [interval1[i + 1] - interval1[i] for i in range(n_minor - 1)]
            # Base-10 pattern: clustering makes max gap > 2× min gap.
            if min(gaps) > 0 and max(gaps) > 2 * min(gaps):
                is_nonuniform = True
        n_divs = n_minor + 1

        for el, pos_int in minor_els:
            for i in range(n):
                lo = major_positions[i]
                hi = major_positions[i + 1]
                if lo - 1.0 <= pos_int <= hi:
                    span = hi - lo
                    if span == 0:
                        break
                    rel = max(0.0, min(1.0, (pos_int - lo) / span))
                    if is_x:
                        # X-axis: lo = low-value end (left). rel increases rightward.
                        # base-10: fraction = log10(m), mval = 10^rel
                        # uniform:  fraction = k/n_divs, k = round(rel × n_divs)
                        if is_nonuniform:
                            mval = max(2, min(9, int(round(10**rel))))
                            pos_ex = lo + math.log10(mval) * span
                        else:
                            k = max(1, min(n_divs - 1, int(round(rel * n_divs))))
                            pos_ex = lo + (k / n_divs) * span
                        if abs(pos_ex - pos_int) > 0.001:
                            el.set("transform", f"translate({pos_ex:.6f},0)")
                            changed = True
                    else:
                        # Y-axis: lo = y_top (high-value end, top). rel increases downward.
                        # base-10: fraction = log10(m), mval = 10^(1-rel)
                        # uniform:  fraction = k/n_divs, k = round((1-rel) × n_divs)
                        if is_nonuniform:
                            mval = max(2, min(9, int(round(10 ** (1.0 - rel)))))
                            pos_ex = hi - math.log10(mval) * span
                        else:
                            k = max(1, min(n_divs - 1, int(round((1.0 - rel) * n_divs))))
                            pos_ex = hi - (k / n_divs) * span
                        if abs(pos_ex - pos_int) > 0.001:
                            el.set("transform", f"translate(0,{pos_ex:.6f})")
                            changed = True
                    break

    # Walk the SVG tree, accumulating parent <g> transforms to build a
    # (cx, cy) context key for each tick line. Panels in hconcat have
    # different accumulated cx values; panels in vconcat have different cy
    # values. Grouping by (cx, cy) prevents cross-panel contamination in
    # both layouts — e.g. a linear axis in one hconcat panel cannot pollute
    # the major-position list used to correct a log axis in another.
    #
    # y_groups[(cx,cy)] = [(el, local_y, tick_size), ...]
    # x_groups[(cx,cy)] = [(el, local_x, tick_size), ...]
    y_groups: dict[tuple[float, float], list] = {}
    x_groups: dict[tuple[float, float], list] = {}

    def _collect(el: ET.Element, cx: float = 0.0, cy: float = 0.0) -> None:
        for child in el:
            child_cx, child_cy = cx, cy
            t = child.get("transform", "")
            m = _TRANSLATE.match(t)
            if m:
                child_cx += float(m.group(1))
                child_cy += float(m.group(2))

            if child.tag == f"{{{NS}}}line":
                lt = child.get("transform", "")
                my = re.match(r"translate\(0,([0-9.-]+)\)$", lt)
                mx = re.match(r"translate\(([0-9.-]+),0\)$", lt)
                x2_str = child.get("x2", "")
                y2_str = child.get("y2", "")
                if my and x2_str:
                    try:
                        x2_val = float(x2_str)
                    except ValueError:
                        x2_val = 0.0
                    if x2_val < 0:
                        y_groups.setdefault((cx, cy), []).append((child, float(my.group(1)), abs(x2_val)))
                # Use 'if' not 'elif': a tick at translate(0,0) (leftmost x-axis
                # tick) matches both patterns; the y-axis branch may enter and exit
                # without adding anything, so the x-axis branch must run independently.
                if mx and y2_str:
                    try:
                        y2_val = float(y2_str)
                    except ValueError:
                        y2_val = 0.0
                    if 0 < y2_val < 20:
                        x_groups.setdefault((cx, cy), []).append((child, float(mx.group(1)), y2_val))
            else:
                _collect(child, child_cx, child_cy)

    _collect(root)

    # Process each panel's y-axis and x-axis ticks independently.
    for ticks in y_groups.values():
        sizes = sorted({s for _, _, s in ticks}, reverse=True)
        if len(sizes) >= 2:
            major_size, minor_size = sizes[0], sizes[-1]
            major_ys = sorted(y for _, y, s in ticks if s == major_size)
            minor_els = [(el, y) for el, y, s in ticks if s == minor_size]
            _correct_axis(major_ys, minor_els, is_x=False)

    for ticks in x_groups.values():
        sizes = sorted({s for _, _, s in ticks}, reverse=True)
        if len(sizes) >= 2:
            major_size, minor_size = sizes[0], sizes[-1]
            major_xs = sorted(x for _, x, s in ticks if s == major_size)
            minor_els = [(el, x) for el, x, s in ticks if s == minor_size]
            _correct_axis(major_xs, minor_els, is_x=True)

    if changed:
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

    viewFill + closed interaction: when the background path carries both a fill (viewFill)
    and a stroke (closed border), only moving the whole element would place the fill on
    top of marks. Instead, the original element is stripped to fill-only (stroke="none")
    and a stroke-only clone is appended at the end, so the fill stays behind marks and
    the border still renders in front.
    """
    import copy
    import xml.etree.ElementTree as ET

    NS = "http://www.w3.org/2000/svg"
    ET.register_namespace("", NS)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

    def _is_grid_axis(el: ET.Element) -> bool:
        return any(g.get("class", "") == "mark-rule role-axis-grid" for g in el.iter(f"{{{NS}}}g"))

    tree = ET.parse(path)
    root = tree.getroot()

    def reorder(el: ET.Element) -> None:
        to_move = []  # existing children to remove and re-append at end
        to_add = []  # stroke-only clones to append at end (originals stay in place)
        for child in list(el):
            cls = child.get("class", "")
            if cls == "mark-group role-axis" and not _is_grid_axis(child):
                to_move.append(child)
            elif (
                child.tag == f"{{{NS}}}path"
                and cls == "background"
                and child.get("stroke") not in (None, "none")
                and child.get("display") != "none"
            ):
                fill = child.get("fill")
                has_fill = fill is not None and fill not in ("none", "")
                if has_fill:
                    # Background has both fill (viewFill) and stroke (closed border).
                    # Keep fill-only original in place; move stroke-only clone to front.
                    border_clone = copy.deepcopy(child)
                    border_clone.set("fill", "none")
                    child.set("stroke", "none")
                    to_add.append(border_clone)
                else:
                    to_move.append(child)
        for item in to_move:
            el.remove(item)
            el.append(item)
        for item in to_add:
            el.append(item)
        for child in el:
            reorder(child)

    reorder(root)
    with open(path, "w", encoding="utf-8") as f:
        f.write(ET.tostring(root, encoding="unicode"))


_SUPERSCRIPT_MAP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789−")
_SUP_LABEL_PATTERN = re.compile(r"([×≈]\s*10)([⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+)")


def _fix_superscript_labels(path: str) -> None:
    """Fix misaligned Unicode superscripts in scientific/power notation labels.

    Unicode superscript digits 1-3 (U+00B9/B2/B3, Latin-1 Supplement) and 0/4-9
    (U+2070, U+2074-U+2079, Superscripts block) live in different font metric tables and
    render at inconsistent vertical positions in many fonts, causing visible misalignment
    in multi-digit exponents like 10^-14. Finds the pattern in SVG text/.text nodes only
    (not attribute values) and replaces the exponent portion with a <tspan dy="-2.5"
    font-size="4"> element using plain ASCII digits for consistent font metrics.

    Tuned for p-value label fontSize=6: exponent font-size=4 (~67%), dy=-2.5 (~42% shift).
    """
    import xml.etree.ElementTree as ET

    NS = "http://www.w3.org/2000/svg"
    ET.register_namespace("", NS)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

    tree = ET.parse(path)
    root = tree.getroot()
    changed = False

    # Collect matching text/tspan elements first to avoid modifying while iterating.
    targets = [
        el
        for el in root.iter()
        if el.tag in (f"{{{NS}}}text", f"{{{NS}}}tspan") and el.text and _SUP_LABEL_PATTERN.search(el.text)
    ]

    for el in targets:
        text = el.text or ""
        m = _SUP_LABEL_PATTERN.search(text)
        if not m:
            continue
        prefix = text[: m.end(1)]
        exp_ascii = m.group(2).translate(_SUPERSCRIPT_MAP)
        suffix = text[m.end() :]

        tspan = ET.Element(f"{{{NS}}}tspan")
        tspan.set("dy", "-2.5")
        tspan.set("font-size", "4")
        tspan.text = exp_ascii
        tspan.tail = suffix or None

        el.text = prefix
        el.insert(0, tspan)
        changed = True

    if changed:
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
    the parent element. Two classes of ``<g>`` are flattened:

    1. Groups with no rendering-relevant attributes (only ``class`` or nothing).
    2. Groups whose only rendering attribute is ``transform="translate(0,0)"`` —
       a no-op that Vega emits as a structural wrapper around chart content.
       Removing it reduces the ungroup depth in Illustrator by one level without
       affecting visual output.

    Groups that carry any of the following attributes are preserved: ``clip-path``,
    ``opacity``, ``mask``, ``filter``, ``style``, ``id``, or any non-trivial
    ``transform``. Definition blocks (``<defs>``, ``<clipPath>``, ``<symbol>``)
    are left entirely untouched.

    The result is a flatter, editor-friendly SVG that renders identically to the
    original.
    """
    import re
    import xml.etree.ElementTree as ET

    NS = "http://www.w3.org/2000/svg"
    ET.register_namespace("", NS)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

    KEEP_ATTRS = {"transform", "clip-path", "opacity", "mask", "filter", "style", "id"}
    SKIP_TAGS = {f"{{{NS}}}defs", f"{{{NS}}}clipPath", f"{{{NS}}}symbol"}

    _NOOP_TRANSLATE = re.compile(r"translate\(\s*0(?:\.0+)?\s*[,\s]\s*0(?:\.0+)?\s*\)$")

    def _is_noop(child) -> bool:
        effective = set(child.attrib) & KEEP_ATTRS
        if not effective:
            return True
        # translate(0,0) has no visual effect — safe to inline.
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
            if child.tag == f"{{{NS}}}g" and _is_noop(child):
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
