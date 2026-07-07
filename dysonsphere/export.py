from __future__ import annotations

import json
import re
import tempfile
import uuid
import xml.etree.ElementTree as ET
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Union, cast

import altair as alt

from . import discovery, metadata
from .theme import _opt

# The module's public API - star-imported into the dysonsphere namespace. Everything
# else here is internal (underscore or not); keep this list in sync with __init__.__all__.
__all__ = ["save", "show", "load"]

_AltairChart = Union[
    alt.Chart,
    alt.LayerChart,
    alt.FacetChart,
    alt.VConcatChart,
    alt.HConcatChart,
    alt.ConcatChart,
]

_SVG_NS = "http://www.w3.org/2000/svg"
# Registered once so ET serializes SVG without ns0: prefixes, from any fixer or test.
ET.register_namespace("", _SVG_NS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

_VALID_FORMATS = ("svg", "png", "json", "html")
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


def _render_fixed_svg(base_obj, svg_path: str) -> str:
    """Render an Altair object to SVG at *svg_path*, run every dysonsphere SVG post-processor,
    and return the corrected SVG string.

    Tick and grid POSITIONS need no post-processing: the theme renders with Vega's
    ``tickRound: false`` (``config.axis``) and ``tickOffset: 0`` (``config.axisBand``), so
    every tick lands on the exact fractional scale position - i.e. exactly on its mark - at
    render time, on every axis type (band, linear, log/power minors) and in every panel.
    The remaining post-processors are shared by :func:`save` and :func:`show` so the pipeline
    stays identical: grid alignment (seat both grid directions onto the plot content, off the
    detached axes), inward-tick flip (when ``inwardTicks``), axis layering, ``<g>``
    simplification, superscript-label typesetting, and statistical-symbol italicization
    (``P``/``n``/``F``/``r``/… - after the superscript fixer, which only scans element
    ``.text``). The SVG is parsed once here and each
    fixer mutates the shared ElementTree;
    the corrected tree is serialized once at the end (a single parse/write round trip, not
    one per fixer). The caller sets up the theme (e.g. ``transparent``) and owns the file's
    lifecycle.
    """
    base_obj.save(svg_path)  # marker names are in the object but never render into SVG
    root = ET.parse(svg_path).getroot()  # parsed ONCE; every fixer mutates this tree
    axis_offset = 0 if _opt("closed") else _opt("axisOffset")
    if axis_offset:
        _align_grid_to_content(root, axis_offset)
    if _opt("inwardTicks"):
        _flip_ticks_inward(root)
    _layer_axes_to_front(root)
    _simplify_svg(root)
    _fix_superscript_labels(root)
    _italicize_stat_symbols(root)
    svg = '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="unicode")
    Path(svg_path).write_text(svg, encoding="utf-8")
    return svg


def save(
    chart: _AltairChart | Callable[[], _AltairChart],
    filename: str,
    ppi: int = 1200,
    description: str | None = None,
    saveMetadata: bool = True,
    embedReport: bool = True,
    format: str | list[str] | None = None,
    background: str | list[str] | None = None,
    transparent: bool = True,
    maxRows: int = 5000,
    overrideMaxRows: bool = False,
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
        Vega-Lite spec), or ``"html"`` (a self-contained interactive page, Vega JS bundled
        in), as a single string or a list. ``None`` (default) uses the theme option
        ``saveFormat`` (``["svg", "json"]``). An empty list or unknown value raises.

        ``"html"`` is the **interactive** tier: it renders live in the browser via Vega, so
        it is fully themed, carries the metadata block, and gets exact tick positions (that
        fix lives in the theme config), but it does NOT get dysonsphere's static SVG
        post-processors (superscript typesetting, Illustrator-friendly flattening). In
        particular ``inwardTicks`` is deliberately **not** applied to HTML:
        the only way to make Vega draw ticks inward is a negative ``tickSize``, and while that
        works in vl-convert's Vega (the static SVG/PNG path), the browser bundles a different
        Vega build that lays out axis labels wrong with a negative ``tickSize`` (mangled label
        spacing), so it renders inconsistently and is left off. Use ``"svg"``/``"png"`` for the
        publication-accurate static figure.
    background:
        Which background variant(s) to render: ``"light"`` and/or ``"dark"`` (each toggles
        ``darkmode``), as a single string or a list. ``None`` (default) uses the theme
        option ``saveBackground`` (``"light"``). An empty list or unknown value raises.
    transparent:
        Whether the rendered SVG/PNG have a transparent background. ``True`` (default):
        exported figures composite onto any page or slide. ``False``: the background is
        filled with the theme's ``chartFill`` (white in light mode, black in dark mode,
        unless set explicitly) - for outputs viewed on their own, e.g. images embedded in
        a README. Applies to the SVG/PNG render only; the JSON and HTML keep the chart's
        logical background (the theme option ``transparent``).
    maxRows:
        Row cap for the data inlined into the output (default ``5000``, matching Altair).
        Every format renders via ``chart.to_dict()``, which inlines the data, and the JSON
        embeds it for :func:`read` — so data over this many rows would make the files huge
        and is **blocked with a clear error**. Raise it to allow larger data.
    overrideMaxRows:
        If ``True``, removes the row cap entirely for this save (inlines all rows, however
        many). The deliberate opt-in for large data.
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
    _formats = _resolve_choice(format, _opt("saveFormat"), _VALID_FORMATS, "format")
    _backgrounds = _resolve_choice(background, _opt("saveBackground"), _VALID_BACKGROUNDS, "background")

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
    original_darkmode = _opt("darkmode")
    original_transparent = _opt("transparent")
    # Cap the rows inlined for this save (every format renders via to_dict(), which enforces
    # it; overrideMaxRows lifts it) — restored on the way out via the ExitStack.  Over the cap,
    # Altair raises MaxRowsError, which we catch and re-raise with a clearer message.
    _cap_stack = ExitStack()
    _row_cap = alt.data_transformers.enable("default", max_rows=None if overrideMaxRows else maxRows)
    _cap_stack.enter_context(_row_cap)  # ty: ignore[invalid-argument-type]  (Altair PluginEnabler lacks CM stub)
    try:
        if _want_render or "html" in _formats:
            import vl_convert as vlc

        for bg in _backgrounds:
            alt.theme.options["darkmode"] = bg == "dark"
            # The spec is captured at the chart's logical transparency (for the JSON + the
            # checksum); the SVG/PNG re-render below at the `transparent` param's value.
            alt.theme.options["transparent"] = original_transparent
            base_obj = _resolve_base()
            spec = base_obj.to_dict()
            _hashes = metadata._scan_marker_hashes(spec) if saveMetadata else set()
            _records = _select_reports(_hashes)
            _exts = discovery._used_extensions(spec) if saveMetadata else {}  # extensions that made it
            metadata._strip_markers(spec)  # markers are internal — never in the written output
            _usermeta = _usermeta_json = _report_sections = None
            if saveMetadata:
                _usermeta, _usermeta_json, _report_sections = metadata._build_block(
                    _records,
                    embed_report=embedReport,
                    export_id=export_id,
                    timestamp=timestamp,
                    checksum=metadata._spec_checksum(spec),
                    data_checksum=metadata._data_checksum(spec),
                    extensions=_exts,
                    description=description,
                )

            if "json" in _formats:
                jspec = dict(spec)
                if _usermeta is not None:
                    base_um = jspec["usermeta"] if isinstance(jspec.get("usermeta"), dict) else {}
                    jspec["usermeta"] = {**base_um, **_usermeta}
                Path(_path(bg, "json")).write_text(json.dumps(jspec, ensure_ascii=False, indent=2), encoding="utf-8")

            if "html" in _formats:
                # Interactive, self-contained HTML (Vega JS bundled in). It renders live in the
                # browser via Vega, so it does NOT get dysonsphere's static SVG fixers (tick
                # alignment, inward ticks, superscript typesetting) - the interactive/approximate
                # tier. It IS fully themed and carries the metadata block; use svg/png for the
                # publication-accurate static figure. (inwardTicks is intentionally not applied: the
                # negative-tickSize trick renders inconsistently across the browser's Vega build.)
                hspec = dict(spec)
                if _usermeta is not None:
                    base_um = hspec["usermeta"] if isinstance(hspec.get("usermeta"), dict) else {}
                    hspec["usermeta"] = {**base_um, **_usermeta}
                Path(_path(bg, "html")).write_text(vlc.vegalite_to_html(hspec, bundle=True), encoding="utf-8")

            if _want_render:
                alt.theme.options["transparent"] = transparent
                svg_path = _path(bg, "svg")
                svg_content = _render_fixed_svg(base_obj, svg_path)
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
    except alt.MaxRowsError as e:
        raise ValueError(
            f"the chart's data has more than maxRows={maxRows} rows. Every output format inlines "
            f"the data to render it (and the .json embeds it for read(what='data')), so large data "
            f"is blocked to avoid huge files. Raise maxRows= to allow it, or pass overrideMaxRows=True "
            f"to remove the cap."
        ) from e
    finally:
        _cap_stack.close()
        alt.theme.options["darkmode"] = original_darkmode
        alt.theme.options["transparent"] = original_transparent


def show(chart: _AltairChart | Callable[[], _AltairChart]):
    """Render *chart* through the full ``ds.save()`` pipeline and return it for accurate
    inline display in a notebook.

    Altair's own inline renderer (used when you just display a chart) does NOT run
    dysonsphere's SVG post-processors, so its preview is approximate - superscript labels
    aren't typeset, the axisOffset grid gap remains, and with ``inwardTicks=True`` the
    ticks still point outward. ``ds.show(chart)`` renders the *same* corrected SVG that
    :func:`save` writes and returns it as an ``IPython.display.SVG`` for inline display, so
    the preview matches the saved figure. It renders at the theme's current ``darkmode`` and
    writes no file.

    Accepts the same chart types as :func:`save`, including a zero-argument callable (called
    once). Requires IPython (present in any notebook); otherwise raises ``ImportError`` - use
    :func:`save` to write a file instead.
    """
    try:
        from IPython.display import SVG
    except ImportError as e:
        raise ImportError(
            "ds.show() needs IPython (available in notebooks). Use ds.save() to write a file instead."
        ) from e

    base_obj = cast(_AltairChart, chart() if callable(chart) else chart)  # ty: ignore[call-top-callable]
    _prev_transp = alt.theme.options.get("transparent")
    alt.theme.options["transparent"] = True
    try:
        with tempfile.TemporaryDirectory() as d:
            svg = _render_fixed_svg(base_obj, str(Path(d) / "preview.svg"))
    finally:
        alt.theme.options["transparent"] = _prev_transp
    return SVG(svg)


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


def _align_grid_to_content(root: ET.Element, axis_offset: float) -> None:
    """Seat every grid line onto the plot content rectangle, off the detached axes.

    On an open plot each axis is drawn ``axis_offset`` px away from the plot (the detached-axis
    gap): the x-axis sits below, the y-axis sits left.  Vega renders each grid line inside its
    axis group, so the grid inherits that offset and renders dragged toward its axis - the
    vertical (x-axis) grid lines shifted DOWN (top short of the highest tick, bottom overshooting
    onto the x-axis) and the horizontal (y-axis) grid lines shifted LEFT (touching the y-axis,
    short of the right edge).  This translates each line back by ``axis_offset`` (span unchanged):
    vertical lines up, horizontal lines right, so both span the plot content exactly and float
    symmetrically off both detached axes - matching each other and the closed-plot grid (where
    the axes are already flush, so this fixer is skipped entirely).

    A vertical grid line is a ``translate(x,-H)`` (``ty<0``) with ``y2=H``; a horizontal one is a
    ``translate(0,y)`` with ``x2=W``.  Both live inside a ``role-axis-grid`` group.

    Mutates the parsed SVG tree in place (like every fixer in ``_render_fixed_svg``).
    (Formerly part of ``_fix_tick_alignment``.  Tick/grid *positions* need no fixing any
    more - the theme renders with ``tickRound: false`` / ``axisBand.tickOffset: 0``, so they
    already sit on the exact fractional scale positions.)
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
    """Negate axis-tick line geometry so ticks point into the plot (theme(inwardTicks=True)).

    Vega/Vega-Lite always render ticks outward and reject a negative ``tickSize``, so inward
    ticks are produced here as an SVG post-process that negates the non-zero ``x2``/``y2`` of
    every ``<line>`` inside an axis-tick group. x-axis ticks carry their length in ``y2``
    (``x2="0"``), y-axis ticks in ``x2``
    (``y2="0"``), so negating the non-zero coordinate flips the direction. Covers primary,
    secondary (right/top), major, and minor (log/power) ticks uniformly, since all are
    ``role-axis-tick`` groups.
    """
    for g in root.iter(f"{{{_SVG_NS}}}g"):
        if "role-axis-tick" not in g.get("class", ""):
            continue
        for line in g.iter(f"{{{_SVG_NS}}}line"):
            for attr in ("x2", "y2"):
                v = line.get(attr)
                if v is not None and float(v) != 0.0:
                    line.set(attr, v[1:] if v.startswith("-") else "-" + v)


def _layer_axes_to_front(root: ET.Element) -> None:
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

    def _is_grid_axis(el: ET.Element) -> bool:
        return any(g.get("class", "") == "mark-rule role-axis-grid" for g in el.iter(f"{{{_SVG_NS}}}g"))

    def reorder(el: ET.Element) -> None:
        to_move = []  # existing children to remove and re-append at end
        to_add = []  # stroke-only clones to append at end (originals stay in place)
        for child in list(el):
            cls = child.get("class", "")
            if cls == "mark-group role-axis" and not _is_grid_axis(child):
                to_move.append(child)
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


_SUPERSCRIPT_MAP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789−")
_SUP_LABEL_PATTERN = re.compile(r"([×≈]\s*10)([⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+)")


def _fix_superscript_labels(root: ET.Element) -> None:
    """Fix misaligned Unicode superscripts in scientific/power notation labels.

    Unicode superscript digits 1-3 (U+00B9/B2/B3, Latin-1 Supplement) and 0/4-9
    (U+2070, U+2074-U+2079, Superscripts block) live in different font metric tables and
    render at inconsistent vertical positions in many fonts, causing visible misalignment
    in multi-digit exponents like 10^-14. Operates on element .text values in the parsed
    tree only (never attribute values, which carry the same label text in aria-label/title)
    and replaces the exponent portion with a <tspan dy="-2.5" font-size="4"> element using
    plain ASCII digits for consistent font metrics.

    Tuned for p-value label fontSize=6: exponent font-size=4 (~67%), dy=-2.5 (~42% shift).
    """
    # Collect matching text/tspan elements first to avoid modifying while iterating.
    targets = [
        el
        for el in root.iter()
        if el.tag in (f"{{{_SVG_NS}}}text", f"{{{_SVG_NS}}}tspan") and el.text and _SUP_LABEL_PATTERN.search(el.text)
    ]

    for el in targets:
        text = el.text or ""
        m = _SUP_LABEL_PATTERN.search(text)
        if not m:
            continue
        prefix = text[: m.end(1)]
        exp_ascii = m.group(2).translate(_SUPERSCRIPT_MAP)
        suffix = text[m.end() :]

        tspan = ET.Element(f"{{{_SVG_NS}}}tspan")
        tspan.set("dy", "-2.5")
        tspan.set("font-size", "4")
        tspan.text = exp_ascii
        tspan.tail = suffix or None

        el.text = prefix
        el.insert(0, tspan)


# Latin statistical symbols that scientific convention (APA/CSE) sets in italic; Greek
# symbols (ρ, τ, η², ε², χ²) stay upright and are deliberately absent. Matched globally
# on rendered text - dysonsphere-generated labels and user annotations alike - because
# the typography is correct regardless of who wrote the text (same policy as
# _SUP_LABEL_PATTERN above). Each alternative is anchored to the exact context our
# labels generate, so accidental matches in prose are rare (and typographically right
# when they do occur).
_ITALIC_STAT_PATTERN = re.compile(
    r"(?<![A-Za-z])(?:"
    r"P(?=\s*[=<≈])"  # p-value: P = 0.012 / P < 0.001 / P ≈ 10⁻⁵
    r"|[FHA](?=\()"  # omnibus statistic: F(2, 57) / H(2) / A(2)
    r"|W(?=\s*=)"  # Kendall's W = 0.18
    r"|r(?=²?\s*=)"  # correlation r = / r² =  (the ² digit stays upright)
    r"|n(?=\s*=)"  # sample size: n =
    r"|y(?=\s*=)"  # fit equation: y = 0.84x + 0.27
    r"|t(?=-test)"  # Student's t-test / Paired t-test
    r")"
    r"|(?<=Mann-Whitney )U(?![A-Za-z])"  # Mann-Whitney U test label
    r"|(?<=[\d.])x(?=\s*[+\-−]\s*\d)"  # fit equation slope term: 0.84x + 0.27
)


def _italicize_text_element(el: ET.Element) -> None:
    """Wrap every statistical-symbol match in *el*'s text content in an italic ``<tspan>``.

    Only the string nodes *el* owns are processed - ``el.text`` and each existing child's
    ``tail``, in document order - so symbols survive in text the superscript fixer has
    already split around an exponent ``<tspan>``. A child's own ``.text`` is NOT touched
    here: every ``<tspan>`` is itself a target of :func:`_italicize_stat_symbols` (Vega
    sometimes wraps a whole label in one), so each string node is processed exactly once,
    by the element that owns it.
    """
    items = [(None, el.text or "")] + [(child, child.tail or "") for child in list(el)]
    if not any(_ITALIC_STAT_PATTERN.search(s) for _, s in items):
        return

    for child in list(el):
        el.remove(child)
    el.text = None
    last: ET.Element | None = None  # last re-appended node; None → plain text goes to el.text

    def _append_plain(s: str) -> None:
        nonlocal last
        if not s:
            return
        if last is None:
            el.text = (el.text or "") + s
        else:
            last.tail = (last.tail or "") + s

    for child, trailing in items:
        if child is not None:
            child.tail = None
            el.append(child)
            last = child
        pos = 0
        for m in _ITALIC_STAT_PATTERN.finditer(trailing):
            _append_plain(trailing[pos : m.start()])
            tspan = ET.Element(f"{{{_SVG_NS}}}tspan")
            tspan.set("font-style", "italic")
            tspan.text = m.group(0)
            el.append(tspan)
            last = tspan
            pos = m.end()
        _append_plain(trailing[pos:])


def _italicize_stat_symbols(root: ET.Element) -> None:
    """Italicize Latin statistical symbols (``P n F H A W r y x t U``) in rendered text.

    Scientific typesetting convention sets single-letter Latin statistical symbols in
    italic while numbers, operators, Greek symbols (η², ε², χ², ρ, τ), and multi-letter
    abbreviations (``ns`` - an abbreviation, not a symbol) stay upright. Vega-Lite
    text marks have no rich text (``fontStyle`` styles a whole string), so this is applied
    as an SVG post-process: each matched symbol is wrapped in a
    ``<tspan font-style="italic">``, rendering with the label font's italic face.

    Covers the dysonsphere-generated labels - ``add_comparisons`` bracket p-values and the
    omnibus/test label (``ANOVA F(2, 57) = 6.34, P = 0.003, η² = 0.18``), the
    ``add_correlation`` readout (``r = 0.85, r² = 0.72, P < 0.001, y = 0.84x + 0.27``), and
    ``add_multilabel``'s ``n =`` sample-size row - and, by the same global-pattern policy as
    :func:`_fix_superscript_labels`, any user text matching the same forms (a hand-written
    ``P = 0.03`` via ``add_text`` gets the identical treatment, keeping typography
    consistent across a figure).

    Must run AFTER :func:`_fix_superscript_labels`: that fixer only scans element ``.text``,
    so wrapping a leading ``P`` into a ``<tspan>`` first would move the ``×10⁻⁵`` portion
    into a tail it cannot see. This fixer scans both ``.text`` and child tails, so the
    reverse order is safe. Operates on element text in the parsed tree only, never attribute
    values (``aria-label``/``title`` carry the same label text).
    """
    # Both tags, like the superscript fixer: Vega sometimes wraps a label in an outer
    # <tspan>. Materialize before mutating - the italic tspans inserted during the loop
    # must not become targets themselves (and mutating while root.iter() walks is
    # undefined anyway).
    targets = [el for el in root.iter() if el.tag in (f"{{{_SVG_NS}}}text", f"{{{_SVG_NS}}}tspan")]
    for el in targets:
        _italicize_text_element(el)


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
    KEEP_ATTRS = {"transform", "clip-path", "opacity", "mask", "filter", "style", "id"}
    SKIP_TAGS = {f"{{{_SVG_NS}}}defs", f"{{{_SVG_NS}}}clipPath", f"{{{_SVG_NS}}}symbol"}

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
