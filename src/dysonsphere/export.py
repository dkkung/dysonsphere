from __future__ import annotations

import json
import re
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, cast

import altair as alt

if TYPE_CHECKING:
    from IPython.display import HTML

from . import ext, metadata
from ._svg_geometry import (
    _align_figure_labels,
    _align_grid_to_content,
    _decorate_rule_segments,
    _flip_ticks_inward,
    _layer_axes_below_marks,
    _simplify_svg,
    _sink_border_below_shade,
)
from ._svg_typography import (
    _fix_font_for_illustrator,
    _italicize_stat_symbols,
    _switch_greek_font,
    _typeset_scripts,
)
from .theme import _opt
from .utils import _apply_spec_fixes, _json_safe

# Public names re-exported by dysonsphere.
__all__ = ["save", "show", "load"]

_AltairChart = ext.AltairChart


_VALID_FORMATS = ("svg", "png", "json", "html")
_VALID_BACKGROUNDS = ("light", "dark")


def _resolve_choice(value, default, valid: tuple[str, ...], name: str) -> list[str]:
    """Normalize a str-or-list ``save()`` choice (falling back to the theme ``default``) to a
    validated, non-empty list.  Raises ``ValueError`` on an empty list or unknown value.
    """
    from .theme import _resolve_choice as _validate_choice

    raw = value if value is not None else default
    return _validate_choice(raw, valid, name)


def _render_fixed_svg(base_obj, svg_path: str, *, resolved_spec: dict[str, Any] | None = None) -> str:
    """Render an Altair object to *svg_path* and return the corrected SVG string.

    The theme's ``tickRound: false`` and ``tickOffset: 0`` keep tick positions aligned with marks
    on all axes and panels. The remaining corrections are shared by :func:`save` and :func:`show`:
    SVG geometry, layering, and typography corrections. The SVG is parsed once here and each
    correction modifies the shared ElementTree, which is written once at the end. The authoritative
    ordering constraints are documented in DESIGN.md.
    The caller sets up the theme (e.g. ``transparent``) and manages the output file.

    Rendering goes through the resolved spec dict (``to_dict()`` + ``vlc.vegalite_to_svg`` -
    the same engine/spec ``base_obj.save()`` uses).
    """
    import vl_convert as vlc

    spec = resolved_spec if resolved_spec is not None else _apply_spec_fixes(base_obj.to_dict())
    root = ET.fromstring(vlc.vegalite_to_svg(spec))  # Parse once; every fixer mutates this tree.
    _decorate_rule_segments(root)  # marker classes and unsimplified line transforms are still intact
    axis_offset = 0 if _opt("closed") else _opt("axisOffset")
    if axis_offset:
        _align_grid_to_content(root, axis_offset)
    if _opt("tickDirection") == "in":
        _flip_ticks_inward(root)
    _align_figure_labels(root)  # before _simplify_svg, which flattens the transforms it reads
    _layer_axes_below_marks(root)
    _sink_border_below_shade(root)  # after the re-order, which moves the shade to its group's front
    _simplify_svg(root)
    _typeset_scripts(root)
    _italicize_stat_symbols(root)
    greek_font = _opt("fontGreek")
    if greek_font is not None:
        _switch_greek_font(root, greek_font)
    _fix_font_for_illustrator(root)
    svg = '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="unicode")
    Path(svg_path).write_text(svg, encoding="utf-8")
    return svg


def save(
    chart: _AltairChart | Callable[[], _AltairChart],
    filename: str | Path,
    *,
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

    Point labels are placed once per background against the complete composed panel before writing
    any format, so JSON, HTML, SVG, and PNG start with the same obstacle-aware layout.

    Labels are typeset on export (SVG/PNG): a ``^`` marks a superscript (``"x^2"``, ``"10^3"``)
    and a **double** underscore a subscript (``"C__t"`` -> C with a subscript t; single ``_`` is
    left alone so snake_case column names used as default titles are not mangled). Unicode
    super/subscripts you type (``"H₂O"``, ``"t₀"``) and log/p-value exponents are normalized to the
    same shrunk, shifted plain-ASCII glyphs, so they render correctly even in fonts missing the
    Unicode super/subscript characters.

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
        processing steps (superscript typesetting, Illustrator-friendly flattening).
        ``tickDirection="in"`` is deliberately **not** applied to HTML:
        the only way to make Vega draw ticks inward is a negative ``tickSize``, and while that
        works in vl-convert's Vega (the static SVG/PNG path), the browser bundles a different
        Vega build that lays out axis labels wrong with a negative ``tickSize`` (mangled label
        spacing), so it renders inconsistently and is left off. Use ``"svg"``/``"png"`` for the
        static figure with the SVG post-processing applied.
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

        - ``provenance`` — generation facts as fields: ``user``, ``script``, ``chart``
          (best-effort source text of the ``chart`` argument at this call site — the
          variable name or inline composition, e.g. ``"boxplot + points"``; omitted when
          the source is unavailable, e.g. in a plain REPL), ``timestamp`` (ISO-8601),
          ``environment`` (OS + toolchain versions), then the identity fields
          ``vegaliteChecksum``/``exportIdentifier``/``dataChecksum``. In Jupyter, ``script``
          is ``"<jupyter-notebook>"``; ``user`` falls back to ``"unknown_user"``.
        - ``statistics`` — the structured records queued by ``stats.comparisons`` (groups,
          omnibus result, comparisons with exact p-values and effect sizes); omitted when
          there are none.

        It lands in the **Vega-Lite JSON** under ``usermeta.dysonsphere`` (merged into any
        ``usermeta`` already on the chart), the **SVG** ``<metadata id="dysonsphere">``
        element (CDATA), and the **PNG** ``iTXt dysonsphere`` chunk.

        ``saveMetadata=False`` suppresses the structured block entirely; your
        ``description`` (if any) is still written.

        **Reproducible exports.** ``timestamp`` and ``exportIdentifier`` normally change on
        every call, so re-saving an unchanged figure rewrites its bytes.  Setting the
        ``SOURCE_DATE_EPOCH`` environment variable (the reproducible-builds convention: an
        integer count of UTC seconds) pins the timestamp to that instant and derives the
        identifier from the figure's own content, making repeated saves byte-identical —
        useful when figures are committed alongside a manuscript.  Distinct figures still
        get distinct identifiers, and the light/dark variants of one export still share one.
    embedReport:
        If ``True`` (default) and ``saveMetadata`` is on, also embeds the human-readable
        **report table** (the descriptive + effect-size text from ``stats.comparisons`` /
        ``stats.correlation``) as a ``report``
        member of ``usermeta.dysonsphere`` in the **JSON**, and as a dedicated readable
        channel (real newlines, not escaped JSON) in the **SVG**
        (``<metadata id="dysonsphere-report">``) and **PNG** (``iTXt dysonsphere-report``).
        It never touches ``description`` (your text only). Set ``False`` to keep just the
        structured block. (Also available standalone via ``stats.comparisons(report=True)``.)

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
    # Capture the chart expression from the caller when source is available.
    _chart_expression = metadata._call_expression(sys._getframe(1)) if saveMetadata else None

    if not alt.theme.options:
        raise RuntimeError("ds.theme() must be called before ds.save().")

    # Validate format and background before resolving charts.
    _formats = _resolve_choice(format, _opt("saveFormat"), _VALID_FORMATS, "format")
    _backgrounds = _resolve_choice(background, _opt("saveBackground"), _VALID_BACKGROUNDS, "background")

    # Select records by markers on the resolved chart without removing them from the registry.
    # Variants share a timestamp and export identifier but have separate checksums.
    # SOURCE_DATE_EPOCH fixes the timestamp and derives the identifier from the first variant's content.
    _reproducible = metadata._source_date_epoch() is not None
    export_id = "" if _reproducible else str(uuid.uuid4())
    timestamp = metadata._resolve_timestamp()

    # Reinvoke callables for each variant so construction-time colors rebuild. The description
    # stays user text; Dysonsphere metadata is added to the output formats below.
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

        # Resolve and validate all variants before writing. Build each variant once so the renderer
        # and saved spec use the same chart.
        _variants: list[tuple[str, _AltairChart, dict[str, Any]]] = []
        for bg in _backgrounds:
            alt.theme.options["darkmode"] = bg == "dark"
            alt.theme.options["transparent"] = original_transparent
            base_obj = _resolve_base()
            spec = _apply_spec_fixes(_json_safe(base_obj.to_dict()))
            # The guard also runs when metadata will be stripped; loaded results must never silently
            # survive a changed analytical panel in any output tier.
            metadata._prepare_statistics_owners(deepcopy(spec))
            _variants.append((bg, base_obj, spec))

        for bg, base_obj, original_spec in _variants:
            alt.theme.options["darkmode"] = bg == "dark"
            alt.theme.options["transparent"] = original_transparent
            spec = deepcopy(original_spec)
            # Scan extension wrappers before a wrapped live-statistics marker is replaced by its
            # persistent owner. Loaded persistent owners remain compatible with fresh extension tags.
            _exts = ext._used_extensions(spec) if saveMetadata else {}  # extensions that made it
            _records, _bindings = metadata._prepare_statistics_owners(spec) if saveMetadata else ([], {})
            metadata._strip_markers(spec, statistics_owners=not saveMetadata)
            _usermeta = _usermeta_json = _report_sections = None
            if saveMetadata:
                _checksum = metadata._spec_checksum(spec)
                _data_checksum = metadata._data_checksum(spec)
                if _reproducible and not export_id:
                    export_id = metadata._derive_export_id(timestamp, _checksum, _data_checksum)
                _usermeta, _usermeta_json, _report_sections = metadata._build_block(
                    _records,
                    embed_report=embedReport,
                    export_id=export_id,
                    timestamp=timestamp,
                    checksum=_checksum,
                    data_checksum=_data_checksum,
                    extensions=_exts,
                    chart_expression=_chart_expression,
                    description=description,
                    statistics_bindings=_bindings,
                )

            if "json" in _formats:
                jspec = dict(spec)
                if _usermeta is not None:
                    base_um = jspec["usermeta"] if isinstance(jspec.get("usermeta"), dict) else {}
                    jspec["usermeta"] = {**base_um, **_usermeta}
                Path(_path(bg, "json")).write_text(json.dumps(jspec, ensure_ascii=False, indent=2), encoding="utf-8")

            if "html" in _formats:
                # Interactive HTML bundles Vega and omits static SVG fixers. It remains themed and
                # carries metadata; inward ticks are omitted because negative tick sizes render
                # inconsistently across browser Vega builds.
                hspec = dict(spec)
                if _usermeta is not None:
                    base_um = hspec["usermeta"] if isinstance(hspec.get("usermeta"), dict) else {}
                    hspec["usermeta"] = {**base_um, **_usermeta}
                Path(_path(bg, "html")).write_text(vlc.vegalite_to_html(hspec, bundle=True), encoding="utf-8")

            if _want_render:
                alt.theme.options["transparent"] = transparent
                svg_path = _path(bg, "svg")
                # Reuse the computed layout for all formats; callable charts are built once per
                # background.
                render_spec = deepcopy(original_spec)
                # Apply export transparency while preserving custom chart backgrounds, without placing
                # labels again.
                physical_spec = _json_safe(base_obj.to_dict())
                if "background" in physical_spec:
                    render_spec["background"] = physical_spec["background"]
                else:
                    render_spec.pop("background", None)
                svg_content = _render_fixed_svg(base_obj, svg_path, resolved_spec=render_spec)
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


def show(
    chart: _AltairChart | Callable[[], _AltairChart], *, maxRows: int = 5000, overrideMaxRows: bool = False
) -> "HTML":
    """Render *chart* through the full ``ds.save()`` processing and return it for accurate
    inline display in a notebook.

    Altair's own inline renderer (used when you just display a chart) does NOT run
    dysonsphere's SVG processing, so its preview is approximate - superscript labels
    aren't typeset, the axisOffset grid gap remains, and with ``tickDirection="in"`` the
    ticks still point outward. ``ds.show(chart)`` renders the *same* corrected SVG that
    :func:`save` writes and returns it as an ``IPython.display.HTML`` for inline display, so
    the preview matches the saved figure. It renders at the theme's current ``darkmode`` and
    ``transparent`` and writes no file.

    This also places labels from the saved point coordinates and label settings; no extra placement
    call is needed.

    The SVG is returned as **HTML** rather than ``IPython.display.SVG`` so the preview lands on
    the notebook's own background, exactly like a bare Altair chart. An ``image/svg+xml`` output
    goes to the frontend's *image* renderer instead, which in VS Code composites onto a white
    canvas - so a transparent dark-mode figure came back as white ink on white.

    Like :func:`save`, the render is wrapped in the ``"default"`` data transformer capped at
    ``maxRows`` (``overrideMaxRows=True`` lifts the cap), so ``ds.show()`` works regardless of
    whichever transformer is active in the session — in particular ``vegafusion``, which
    otherwise makes Altair's ``to_dict()`` raise (dysonsphere's SVG processing needs the
    vega-lite spec, and a scatter's points must all inline anyway, so vegafusion cannot help
    here). Over the cap Altair raises, re-raised as a clear :class:`ValueError`.

    Accepts the same chart types as :func:`save`, including a zero-argument callable (called
    once). Requires IPython (present in any notebook); otherwise raises ``ImportError`` - use
    :func:`save` to write a file instead.

    Returns
    -------
    IPython.display.HTML
        The corrected SVG wrapped for inline notebook display.
    """
    try:
        from IPython.display import HTML
    except ImportError as e:
        raise ImportError(
            "ds.show() needs IPython (available in notebooks). Use ds.save() to write a file instead."
        ) from e

    base_obj = cast(_AltairChart, chart() if callable(chart) else chart)  # ty: ignore[call-top-callable]
    # Cap the inlined rows and pin the "default" transformer for the render
    _cap_stack = ExitStack()
    _row_cap = alt.data_transformers.enable("default", max_rows=None if overrideMaxRows else maxRows)
    _cap_stack.enter_context(_row_cap)  # ty: ignore[invalid-argument-type]  (Altair PluginEnabler lacks CM stub)
    try:
        with tempfile.TemporaryDirectory() as d:
            svg = _render_fixed_svg(base_obj, str(Path(d) / "preview.svg"))
    except alt.MaxRowsError as e:
        raise ValueError(
            f"the chart's data has more than maxRows={maxRows} rows. ds.show() inlines the data to "
            f"render it, so large data is blocked to avoid a huge SVG. Raise maxRows= to allow it, or "
            f"pass overrideMaxRows=True to remove the cap."
        ) from e
    finally:
        _cap_stack.close()
    # Drop the file's XML prolog - an HTML parser reads it as a bogus comment (SVG() stripped it)
    return HTML(svg[svg.index("<svg") :])


def load(path: str | Path, *, raw: bool = False, applyTheme: bool = True) -> "_AltairChart | dict[str, Any]":
    """Rebuild the chart from a dysonsphere-exported Vega-Lite JSON (the ``.json`` spec).

    JSON only — the PNG/SVG carry the metadata block but not the full spec. Statistical records
    saved by the current version are restored with their owning chart components, so composition,
    panel extraction, and a later :func:`save` preserve only the records still represented. The
    numerical results and their source-data checksums are preserved, not recomputed. Loaded records
    retain a guard over their saved analytical panel; changing data, mappings, transforms, parameters,
    or annotation values makes a later save fail closed and requires rebuilding the annotation from
    source data. Presentation edits and intact panel composition remain valid. Files from earlier
    versions receive no adapter. Lookup transforms, runtime parameters/selections, external data, and
    expressions beyond deterministic operations on ``datum`` cannot be preserved.

    Parameters
    ----------
    raw:
        ``False`` (default) returns a composable Altair object (of the right type). Its
        theme ``config`` is stripped (Altair's schema rejects a few of dysonsphere's
        config values), so it comes back unstyled — see ``applyTheme``. ``True`` returns
        the raw Vega-Lite spec ``dict`` instead, ``config`` intact, which re-renders
        pixel-identically (e.g. via ``vl_convert``) but is not a composable Altair object. Raw mode
        does not restore chart-owned statistical records into runtime state.
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
    spec, imported_records = metadata._restore_statistics_owners(spec)
    ds_metadata = (spec.get("usermeta") or {}).get("dysonsphere") or {}
    theme_args = ds_metadata.get("theme") if applyTheme else None
    automatic_theme_options = set(ds_metadata.get("themeAutomatic", []))
    # Inline named datasets before dropping their top-level container. Top-level export properties
    # otherwise make two loaded charts invalid as children of a new Altair composition.
    datasets = cast(dict[str, Any], spec.get("datasets")) if isinstance(spec.get("datasets"), dict) else {}

    def inline_named_data(node: dict[str, Any]) -> None:
        data = node.get("data")
        if isinstance(data, dict) and isinstance(data.get("name"), str) and data["name"] in datasets:
            node["data"] = {**data, "values": datasets[data["name"]]}
            del node["data"]["name"]
        for transform in node.get("transform", []) if isinstance(node.get("transform"), list) else []:
            source = transform.get("from", {}).get("data") if isinstance(transform, dict) else None
            if isinstance(source, dict) and isinstance(source.get("name"), str):
                name = source["name"]
                if name not in datasets:
                    raise ValueError(f"saved chart lookup references missing named dataset {name!r}")
                transform["from"]["data"] = {**source, "values": datasets[name]}
                del transform["from"]["data"]["name"]

    metadata._walk_chart_nodes(spec, inline_named_data)
    # Strip export-only top-level properties before parsing into a composable Altair object.
    stripped = {k: v for k, v in spec.items() if k not in ("$schema", "background", "config", "datasets", "usermeta")}
    chart = cast("_AltairChart", alt.Chart.from_dict(stripped))
    if theme_args:
        from .theme import _restore_theme

        _restore_theme(theme_args, automatic_theme_options)
    if imported_records:
        from ._statistics import _register_loaded_report

        for record, context_hash in imported_records:
            _register_loaded_report(record, context_hash)
    return chart
