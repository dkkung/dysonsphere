import json
import math
import re
import textwrap
import xml.etree.ElementTree as ET

import altair as alt
import polars as pl
import pytest

from dysonsphere.export import (
    _extend_grid_span,
    _fix_superscript_labels,
    _flip_ticks_inward,
    _layer_axes_to_front,
    _simplify_svg,
    save,
)
from dysonsphere.theme import theme

NS = "http://www.w3.org/2000/svg"


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


@pytest.fixture(autouse=True)
def default_theme():
    theme()


@pytest.fixture
def simple_chart():
    df = pl.DataFrame({"x": ["A", "B", "C"], "y": [1.0, 2.0, 3.0]})
    return alt.Chart(df).mark_point().encode(x="x:N", y="y:Q")


# ── save() ───────────────────────────────────────────────────────────────────


class TestSave:
    def test_light_files_created(self, simple_chart, tmp_path):
        # single background → no suffix; request png explicitly (default is svg+json)
        save(simple_chart, str(tmp_path / "out"), format=["svg", "png"], background=["light"])
        assert (tmp_path / "out.png").exists()
        assert (tmp_path / "out.svg").exists()

    def test_dark_files_created(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), format=["svg", "png"], background=["dark"])
        assert (tmp_path / "out.png").exists()  # single dark background → no suffix
        assert (tmp_path / "out.svg").exists()

    def test_multi_background_suffixes(self, simple_chart, tmp_path):
        # >1 background → _light/_dark suffixes on every format
        save(simple_chart, str(tmp_path / "out"), format=["svg", "png", "json"], background=["light", "dark"])
        for suffix in ["_light", "_dark"]:
            for ext in ["png", "svg", "json"]:
                assert (tmp_path / f"out{suffix}.{ext}").exists()

    def test_default_format_is_svg_and_json(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"))
        assert (tmp_path / "out.svg").exists() and (tmp_path / "out.json").exists()
        assert not (tmp_path / "out.png").exists()  # png is opt-in now

    def test_vega_spec_saved(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), background=["light"])
        assert (tmp_path / "out.json").exists()

    def test_format_without_json_skips_spec(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), format="svg", background=["light"])
        assert not (tmp_path / "out.json").exists()

    def test_format_png_only_writes_no_svg(self, simple_chart, tmp_path):
        # the SVG is a transient PNG source and must not be left behind
        save(simple_chart, str(tmp_path / "out"), format="png", background=["light"])
        assert (tmp_path / "out.png").exists()
        assert not (tmp_path / "out.svg").exists()

    @pytest.fixture
    def big_chart(self):
        n = 6000
        df = pl.DataFrame({"g": ["A", "B"] * (n // 2), "v": [float(i) for i in range(n)]})
        return alt.Chart(df).mark_point().encode(x="g:N", y="v:Q")

    def test_max_rows_blocks_large_data(self, big_chart, tmp_path):
        # every format hits the cap (rendering inlines the data), with a clear error
        for fmt in ("json", "png", "svg"):
            with pytest.raises(ValueError, match="maxRows"):
                save(big_chart, str(tmp_path / "big"), format=fmt, background=["light"])

    def test_max_rows_raised_allows_large_data(self, big_chart, tmp_path):
        save(big_chart, str(tmp_path / "big"), format="json", maxRows=10000, background=["light"])
        assert (tmp_path / "big.json").exists()

    def test_override_max_rows_allows_large_data(self, big_chart, tmp_path):
        save(big_chart, str(tmp_path / "big"), format="json", overrideMaxRows=True, background=["light"])
        assert (tmp_path / "big.json").exists()

    def test_max_rows_restores_transformer(self, big_chart, tmp_path):
        before = alt.data_transformers.active
        with pytest.raises(ValueError):
            save(big_chart, str(tmp_path / "big"), format="json", background=["light"])  # errors mid-save
        assert alt.data_transformers.active == before  # transformer restored even on error

    def test_layer_chart(self, tmp_path):
        from typing import cast

        df = pl.DataFrame({"x": ["A", "B"], "y": [1.0, 2.0]})
        base = alt.Chart(df).mark_point().encode(x="x:N", y="y:Q")
        layer = cast(alt.LayerChart, alt.layer(base))
        save(layer, str(tmp_path / "out"), background=["light"])
        assert (tmp_path / "out.svg").exists()

    def test_hconcat_chart(self, tmp_path):
        df = pl.DataFrame({"x": ["A", "B"], "y": [1.0, 2.0]})
        panel = alt.Chart(df).mark_point().encode(x="x:N", y="y:Q")
        hcat = alt.hconcat(panel, panel)
        save(hcat, str(tmp_path / "out"), background=["light"])
        assert (tmp_path / "out.svg").exists()

    def test_vconcat_chart(self, tmp_path):
        df = pl.DataFrame({"x": ["A", "B"], "y": [1.0, 2.0]})
        panel = alt.Chart(df).mark_point().encode(x="x:N", y="y:Q")
        vcat = alt.vconcat(panel, panel)
        save(vcat, str(tmp_path / "out"), background=["light"])
        assert (tmp_path / "out.svg").exists()

    def test_facet_chart(self, tmp_path):
        df = pl.DataFrame(
            {
                "x": [1.0, 2.0, 3.0, 4.0],
                "y": [1.0, 2.0, 3.0, 4.0],
                "facet": ["A", "A", "B", "B"],
            }
        )
        facet = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q").facet("facet:N")
        save(facet, str(tmp_path / "out"), background=["light"])
        assert (tmp_path / "out.svg").exists()

    def test_callable_chart(self, tmp_path):
        df = pl.DataFrame({"x": ["A", "B"], "y": [1.0, 2.0]})
        save(
            lambda: alt.Chart(df).mark_point().encode(x="x:N", y="y:Q"),
            str(tmp_path / "out"),
            background=["light"],
        )
        assert (tmp_path / "out.svg").exists()

    def test_darkmode_restored_after_full_save(self, simple_chart, tmp_path):
        theme(darkmode=False)
        save(simple_chart, str(tmp_path / "out"))
        assert alt.theme.options["darkmode"] is False

    def test_darkmode_restored_after_light_only(self, simple_chart, tmp_path):
        theme(darkmode=True)
        save(simple_chart, str(tmp_path / "out"), background=["light"])
        assert alt.theme.options["darkmode"] is True

    def test_invalid_background_raises(self, simple_chart, tmp_path):
        with pytest.raises(ValueError, match="background"):
            save(simple_chart, str(tmp_path / "out"), background=["invalid"])

    def test_no_theme_raises(self, simple_chart, tmp_path):
        alt.theme.options = {}
        try:
            with pytest.raises(RuntimeError, match="ds.theme"):
                save(simple_chart, str(tmp_path / "out"))
        finally:
            theme()

    def test_png_nonempty(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), format="png", background=["light"])
        assert (tmp_path / "out.png").stat().st_size > 100

    def test_description_in_spec(self, simple_chart, tmp_path):
        save(
            simple_chart,
            str(tmp_path / "out"),
            description="my chart",
            background=["light"],
        )
        assert "my chart" in (tmp_path / "out.json").read_text()

    def test_description_in_svg(self, simple_chart, tmp_path):
        save(
            simple_chart,
            str(tmp_path / "out"),
            description="my chart",
            saveMetadata=False,
            background=["light"],
        )
        assert "<desc>my chart</desc>" in (tmp_path / "out.svg").read_text()

    def test_save_metadata_on_by_default(self, simple_chart, tmp_path):
        # The structured dysonsphere block AND the human-readable report are embedded by default.
        save(simple_chart, str(tmp_path / "out"), background=["light"])
        svg = (tmp_path / "out.svg").read_text()
        assert 'metadata id="dysonsphere"' in svg  # structured block
        assert 'metadata id="dysonsphere-report-provenance"' in svg  # prose provenance report section

    def test_save_metadata_can_be_disabled(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), saveMetadata=False, background=["light"])
        assert 'metadata id="dysonsphere"' not in (tmp_path / "out.svg").read_text()
        assert "usermeta" not in (tmp_path / "out.json").read_text()

    def test_save_metadata_versions_in_provenance(self, simple_chart, tmp_path):
        import importlib.metadata

        import altair as alt

        save(simple_chart, str(tmp_path / "out"), saveMetadata=True, background=["light"])
        prov = json.loads((tmp_path / "out.json").read_text())["usermeta"]["dysonsphere"]["provenance"]
        assert prov["environment"]["altair"] == alt.__version__
        assert prov["environment"]["dysonsphere"] == importlib.metadata.version("dysonsphere")

    def test_no_desc_when_no_user_description(self, simple_chart, tmp_path):
        # Without an explicit description=, there is no prose <desc> at all — only structured.
        save(simple_chart, str(tmp_path / "out"), background=["light"])
        assert "<desc>" not in (tmp_path / "out.svg").read_text()

    def test_json_description_is_raw_user_description_only(self, simple_chart, tmp_path):
        # The JSON description carries the user's text only — provenance and report text
        # are NOT duplicated there (they live structured under usermeta).
        save(simple_chart, str(tmp_path / "out"), description="Figure 1", background=["light"])
        desc = json.loads((tmp_path / "out.json").read_text())["description"]
        assert desc == "Figure 1"
        assert "Generated by" not in desc

    def test_svg_desc_is_raw_user_description_only(self, simple_chart, tmp_path):
        # The SVG <desc> holds exactly the user's description — nothing auto-appended.
        save(simple_chart, str(tmp_path / "out"), description="Figure 1", background=["light"])
        svg = (tmp_path / "out.svg").read_text()
        match = re.search(r"<desc>(.*?)</desc>", svg, re.DOTALL)
        assert match is not None
        desc = match.group(1)
        assert desc == "Figure 1"  # exactly the user's text, nothing appended
        assert "Generated by" not in desc  # provenance prose rides in the report channel, not <desc>


# ── save(format="html") ──────────────────────────────────────────────────────


class TestHtmlExport:
    def test_html_file_written(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), format="html", background=["light"])
        assert (tmp_path / "out.html").exists()

    def test_html_is_self_contained(self, simple_chart, tmp_path):
        # bundle=True inlines the Vega JS - no CDN dependency
        save(simple_chart, str(tmp_path / "out"), format="html", background=["light"])
        html = (tmp_path / "out.html").read_text(encoding="utf-8")
        assert "<html" in html.lower()
        assert "cdn.jsdelivr.net" not in html and "https://cdn" not in html

    def test_html_is_themed(self, simple_chart, tmp_path):
        # the theme config is baked into the embedded spec (e.g. the house font)
        save(simple_chart, str(tmp_path / "out"), format="html", background=["light"])
        assert "HelveticaNeue" in (tmp_path / "out.html").read_text(encoding="utf-8")

    def test_html_embeds_metadata(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), format="html", background=["light"])
        assert '"dysonsphere"' in (tmp_path / "out.html").read_text(encoding="utf-8")

    def test_html_no_metadata_when_disabled(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), format="html", background=["light"], saveMetadata=False)
        assert '"dysonsphere"' not in (tmp_path / "out.html").read_text(encoding="utf-8")

    def test_html_combines_with_other_formats(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), format=["html", "json"], background=["light"])
        assert (tmp_path / "out.html").exists() and (tmp_path / "out.json").exists()

    def test_html_does_not_apply_inward_ticks(self, tmp_path):
        # inwardTicks is a static-SVG feature; the HTML must NOT carry a negative tickSize
        # (the negative-tickSize trick renders inconsistently in the browser's Vega build).
        theme(inwardTicks=True)
        df = pl.DataFrame({"x": [1.0, 2.0, 3.0], "y": [1.0, 2.0, 3.0]})
        chart = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q")
        save(chart, str(tmp_path / "out"), format="html", background=["light"])
        html = (tmp_path / "out.html").read_text(encoding="utf-8").replace(" ", "")
        assert '"tickSize":-' not in html


# ── show() ───────────────────────────────────────────────────────────────────


class TestShow:
    def test_returns_ipython_svg(self, simple_chart):
        from dysonsphere.export import show

        obj = show(simple_chart)
        assert type(obj).__name__ == "SVG"  # IPython.display.SVG
        assert "<svg" in obj.data

    def test_runs_full_pipeline_inward_ticks(self):
        # show()'s whole point: the preview matches save() output. With inwardTicks the preview
        # SVG must have inward ticks (proving _flip_ticks_inward ran) - Altair's raw render wouldn't.
        from dysonsphere.export import show

        theme(inwardTicks=True)
        df = pl.DataFrame({"x": [1.0, 2.0, 3.0], "y": [1.0, 2.0, 3.0]})
        chart = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q")
        svg = show(chart).data
        y2s = [float(m) for m in re.findall(r'y2="(-?[\d.]+)"', svg) if 0 < abs(float(m)) < 20]
        assert y2s and all(v < 0 for v in y2s)  # inward

    def test_accepts_callable(self):
        from dysonsphere.export import show

        df = pl.DataFrame({"x": [1.0, 2.0], "y": [1.0, 2.0]})
        obj = show(lambda: alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q"))
        assert "<svg" in obj.data

    def test_writes_no_file(self, simple_chart, tmp_path, monkeypatch):
        from dysonsphere.export import show

        monkeypatch.chdir(tmp_path)
        show(simple_chart)
        assert not list(tmp_path.iterdir())  # preview renders to a temp dir, nothing in cwd

    def test_without_ipython_raises(self, simple_chart, monkeypatch):
        import sys

        from dysonsphere.export import show

        monkeypatch.setitem(sys.modules, "IPython.display", None)  # make the import fail
        with pytest.raises(ImportError, match="ds.show"):
            show(simple_chart)


# ── exact tick positions ─────────────────────────────────────────────────────


class TestExactTickPositions:
    """Ticks land exactly on their marks at render time - no SVG position fixing.

    The theme renders with Vega's ``tickRound: false`` (config.axis) and ``tickOffset: 0``
    (config.axisBand), so tick and grid positions are the exact fractional scale positions
    on every axis type (band, linear, log/power minors) and in every panel. These tests
    guard that config by asserting tick == mark equality in real rendered output.
    """

    def test_boxplot_ticks_on_box_centres(self, tmp_path):
        df = pl.DataFrame({"g": ["A", "B", "C"] * 10, "v": [float(i % 7) + 1 for i in range(30)]})
        chart = alt.Chart(df).mark_boxplot().encode(x="g:N", y="v:Q")
        save(chart, str(tmp_path / "b"), format="svg", background="light")
        svg = (tmp_path / "b.svg").read_text(encoding="utf-8")
        # x-axis tick lines carry their length in y2 (= the theme tickSize, 3)
        ticks = sorted(
            float(m.group(1)) for m in re.finditer(r'<line transform="translate\(([\d.]+),0\)"[^/]*y2="3"', svg)
        )
        boxes = sorted(
            float(x) + float(w) / 2
            for x, w in re.findall(r'aria-roledescription="box"[^>]*d="M([-\d.]+),[-\d.]+h([-\d.]+)', svg)
        )
        assert len(ticks) == 3 and len(boxes) == 3
        assert ticks == pytest.approx(boxes, abs=1e-6)  # exact, not merely within a pixel

    def test_linear_axis_ticks_at_exact_scale_positions(self, tmp_path):
        # A [0, 7] domain over 100px puts ticks at fractional positions (100/7 apart);
        # with tickRound=False they must not be integer-rounded.
        df = pl.DataFrame({"x": [1.0, 2.0, 3.0], "y": [0.0, 3.5, 7.0]})
        chart = alt.Chart(df).mark_point().encode(x="x:Q", y=alt.Y("y:Q", scale=alt.Scale(domain=[0, 7])))
        save(chart, str(tmp_path / "l"), format="svg", background="light")
        svg = (tmp_path / "l.svg").read_text(encoding="utf-8")
        ys = sorted(
            float(m.group(1)) for m in re.finditer(r'<line transform="translate\(0,([\d.]+)\)"[^/]*x2="-3"', svg)
        )
        assert len(ys) >= 3, "no y-axis ticks found"
        # Vega picks the tick count; whatever it picks, each tick must sit on the exact
        # (fractional) scale position of an integer data value - not an integer pixel.
        exact = [100 - v / 7 * 100 for v in range(8)]
        for y in ys:
            assert min(abs(y - e) for e in exact) < 1e-6, f"tick {y} integer-rounded off the scale position"

    def test_log_minor_ticks_exact(self, tmp_path):
        from dysonsphere.nonlinear import add_log_ticks

        df = pl.DataFrame({"x": [1.0, 10.0, 100.0], "y": [1.0, 2.0, 3.0]})
        base = (
            alt.Chart(df)
            .mark_point()
            .encode(
                # decade-only major ticks, as in the add_log_ticks demos
                x=alt.X("x:Q", scale=alt.Scale(type="log"), axis=alt.Axis(values=[1, 10, 100])),
                y="y:Q",
            )
        )
        chart = add_log_ticks(base, df, field="x", axis="x")
        save(chart, str(tmp_path / "lg"), format="svg", background="light")
        svg = (tmp_path / "lg.svg").read_text(encoding="utf-8")
        # minor ticks are half the theme tickSize (1.5); majors are 3
        minors = sorted(
            float(m.group(1)) for m in re.finditer(r'<line transform="translate\(([\d.]+),0\)"[^/]*y2="1.5"', svg)
        )
        majors = sorted(
            {float(m.group(1)) for m in re.finditer(r'<line transform="translate\(([\d.]+),0\)"[^/]*y2="3"', svg)}
        )
        assert len(majors) >= 2 and minors
        expected = sorted(lo + math.log10(mv) * (hi - lo) for lo, hi in zip(majors, majors[1:]) for mv in range(2, 10))
        assert minors == pytest.approx(expected, abs=1e-6)

    def test_strip_violin_hconcat_ticks_exact(self, tmp_path):
        # Capstone: strip (Case 0 band positions) beside violin (Case pi) in one hconcat -
        # every tick must land exactly on a box centre in its own panel.
        import numpy as np

        import dysonsphere as ds

        rng = np.random.default_rng(0)
        cats = ["a", "b", "c", "d"]
        df = pl.DataFrame({"g": [c for c in cats for _ in range(20)], "y": rng.normal(0, 1, 80).tolist()})
        theme()
        mixed = alt.hconcat(ds.mark_strip(df, "g", "y", cats), ds.mark_violin(df, "g", "y", cats))
        save(mixed, str(tmp_path / "m"), format="svg", background="light")
        root = ET.parse(tmp_path / "m.svg").getroot()
        boxes: list[float] = []
        ticks: list[float] = []

        def walk(el, cx):
            for ch in el:
                ccx = cx
                mt = re.search(r"translate\(([-\d.]+)[,\s]", ch.get("transform", ""))
                if mt:
                    ccx += float(mt.group(1))
                if ch.get("aria-roledescription") == "box":
                    m = re.match(r"M([-\d.]+),[-\d.eE+]+h([-\d.eE+]+)", ch.get("d", ""))
                    if m:
                        boxes.append(ccx + float(m.group(1)) + float(m.group(2)) / 2)
                y2 = ch.get("y2")
                if ch.tag == f"{{{NS}}}line" and ch.get("x2") == "0" and y2 and 0 < abs(float(y2)) < 20:
                    if re.match(r"translate\(([-\d.]+),", ch.get("transform", "")):
                        ticks.append(ccx)
                walk(ch, ccx)

        walk(root, 0.0)
        assert boxes and ticks
        for t in ticks:
            assert min(abs(b - t) for b in boxes) < 1e-6, f"tick {t} not exactly on a box centre"


# ── _extend_grid_span() ──────────────────────────────────────────────────────


class TestExtendGridSpan:
    def test_grid_lines_y_span_extended_by_axis_offset(self, tmp_path):
        # axis_offset stretches vertical grid lines at both ends: the translate keeps the
        # bottom on the axis, the y2 restores the span up to the top border.
        lines = "".join(f'<line transform="translate({x},-100)" x1="0" y1="0" x2="0" y2="100"/>' for x in [10, 50, 90])
        svg = f'<svg xmlns="{NS}"><g class="mark-rule role-axis-grid">{lines}</g></svg>'
        path = _write(tmp_path, "t.svg", svg)
        _extend_grid_span(path, 3)
        root = ET.parse(path).getroot()
        ty_vals, y2_vals = [], []
        for line in root.iter(f"{{{NS}}}line"):
            m = re.match(r"translate\([\d.]+,([-\d.]+)\)", line.get("transform", ""))
            if m:
                ty_vals.append(float(m.group(1)))
                y2_vals.append(float(line.get("y2", "0")))
        assert all(t == pytest.approx(-103.0, abs=0.001) for t in ty_vals)
        assert all(y == pytest.approx(103.0, abs=0.001) for y in y2_vals)

    def test_horizontal_grid_lines_untouched(self, tmp_path):
        # y-axis grid lines (horizontal: x2 > 0, y2 = 0) are not extended.
        svg = (
            f'<svg xmlns="{NS}"><g class="mark-rule role-axis-grid">'
            '<line transform="translate(0,40)" x1="0" y1="0" x2="100" y2="0"/>'
            "</g></svg>"
        )
        path = _write(tmp_path, "t.svg", svg)
        _extend_grid_span(path, 3)
        line = next(ET.parse(path).getroot().iter(f"{{{NS}}}line"))
        assert line.get("transform") == "translate(0,40)"
        assert line.get("y2") == "0"


# ── _flip_ticks_inward() ─────────────────────────────────────────────────────


class TestFlipTicksInward:
    def test_flips_x_and_y_tick_geometry(self, tmp_path):
        svg = (
            f'<svg xmlns="{NS}">'
            '<g class="mark-rule role-axis-tick">'
            '<line transform="translate(10,0)" x1="0" y1="0" x2="0" y2="3"/>'  # x-axis tick (down/out)
            '<line transform="translate(0,20)" x1="0" y1="0" x2="-3" y2="0"/>'  # y-axis tick (left/out)
            "</g></svg>"
        )
        path = _write(tmp_path, "t.svg", svg)
        _flip_ticks_inward(path)
        lines = list(ET.parse(path).getroot().iter(f"{{{NS}}}line"))
        # x-axis tick: y2 negated (now up/inward), x2 untouched (was 0)
        assert lines[0].get("y2") == "-3" and lines[0].get("x2") == "0"
        # y-axis tick: x2 negated (now right/inward), y2 untouched (was 0)
        assert lines[1].get("x2") == "3" and lines[1].get("y2") == "0"

    def test_leaves_non_tick_lines_untouched(self, tmp_path):
        svg = (
            f'<svg xmlns="{NS}">'
            '<g class="mark-rule role-axis-domain">'
            '<line transform="translate(0,0)" x1="0" y1="0" x2="0" y2="100"/>'  # domain line, not a tick
            "</g></svg>"
        )
        path = _write(tmp_path, "t.svg", svg)
        _flip_ticks_inward(path)
        assert next(ET.parse(path).getroot().iter(f"{{{NS}}}line")).get("y2") == "100"

    def test_save_with_inward_ticks_points_ticks_in(self, tmp_path):
        theme(inwardTicks=True)
        df = pl.DataFrame({"x": [1.0, 2.0, 3.0], "y": [1.0, 2.0, 3.0]})
        chart = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q")
        save(chart, str(tmp_path / "out"), format=["svg"], background=["light"])
        root = ET.parse(str(tmp_path / "out.svg")).getroot()
        # x-axis tick marks are <line transform="translate(N,0)" x2="0" y2="±tickSize">; inward => y2
        # negative. (_simplify_svg has flattened the role-axis-tick group by now, so detect by
        # geometry.) Filter small |y2| to exclude the full-height domain/border rule lines.
        y2s = []
        for line in root.iter(f"{{{NS}}}line"):
            v = line.get("y2")
            if v is None or not re.match(r"translate\([\d.]+,0\)$", line.get("transform", "")):
                continue
            fv = float(v)
            if 0 < abs(fv) < 20:
                y2s.append(fv)
        assert y2s and all(v < 0 for v in y2s)  # x-axis ticks point up (into the plot)


# ── _layer_axes_to_front() ───────────────────────────────────────────────────


class TestLayerAxesToFront:
    def test_non_grid_axis_moved_to_end(self, tmp_path):
        svg = textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <g class="mark-group role-axis">
                <g><line x1="0" y1="0" x2="10" y2="0"/></g>
              </g>
              <g class="data-layer"/>
            </svg>
        """)
        path = _write(tmp_path, "t.svg", svg)
        _layer_axes_to_front(path)
        children = list(ET.parse(path).getroot())
        assert children[-1].get("class") == "mark-group role-axis"

    def test_grid_axis_stays_in_place(self, tmp_path):
        svg = textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <g class="mark-group role-axis">
                <g><g class="mark-rule role-axis-grid">
                  <line x1="0" y1="0" x2="100" y2="0"/>
                </g></g>
              </g>
              <g class="data-layer"/>
            </svg>
        """)
        path = _write(tmp_path, "t.svg", svg)
        _layer_axes_to_front(path)
        children = list(ET.parse(path).getroot())
        assert children[0].get("class") == "mark-group role-axis"

    def test_background_fill_and_stroke_split(self, tmp_path):
        # viewFill + closed: fill stays behind marks, stroke clone appended in front
        svg = textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <path class="background" fill="#eeeeee" stroke="black"/>
              <g class="data-layer"/>
            </svg>
        """)
        path = _write(tmp_path, "t.svg", svg)
        _layer_axes_to_front(path)
        root = ET.parse(path).getroot()
        paths = list(root.iter(f"{{{NS}}}path"))
        assert any(p.get("stroke") == "none" for p in paths)  # original → stroke removed
        assert any(p.get("fill") == "none" for p in paths)  # clone → fill=none


# ── _simplify_svg() ──────────────────────────────────────────────────────────


class TestSimplifySvg:
    def test_class_only_group_inlined(self, tmp_path):
        svg = textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <g class="wrapper">
                <rect x="0" y="0" width="10" height="10"/>
              </g>
            </svg>
        """)
        path = _write(tmp_path, "t.svg", svg)
        _simplify_svg(path)
        root = ET.parse(path).getroot()
        assert root.find(f"{{{NS}}}g") is None
        assert root.find(f"{{{NS}}}rect") is not None

    def test_transform_group_preserved(self, tmp_path):
        svg = textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <g transform="translate(10,20)">
                <rect x="0" y="0" width="10" height="10"/>
              </g>
            </svg>
        """)
        path = _write(tmp_path, "t.svg", svg)
        _simplify_svg(path)
        root = ET.parse(path).getroot()
        g = root.find(f"{{{NS}}}g")
        assert g is not None and g.get("transform") == "translate(10,20)"

    def test_noop_translate_inlined(self, tmp_path):
        svg = textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <g transform="translate(0,0)">
                <rect x="0" y="0" width="10" height="10"/>
              </g>
            </svg>
        """)
        path = _write(tmp_path, "t.svg", svg)
        _simplify_svg(path)
        root = ET.parse(path).getroot()
        assert root.find(f"{{{NS}}}g") is None
        assert root.find(f"{{{NS}}}rect") is not None

    def test_clip_path_group_preserved(self, tmp_path):
        svg = textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <g clip-path="url(#clip1)">
                <rect x="0" y="0" width="10" height="10"/>
              </g>
            </svg>
        """)
        path = _write(tmp_path, "t.svg", svg)
        _simplify_svg(path)
        root = ET.parse(path).getroot()
        assert root.find(f"{{{NS}}}g") is not None

    def test_nested_redundant_groups_flattened(self, tmp_path):
        svg = textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <g class="outer">
                <g class="inner">
                  <rect x="0" y="0" width="5" height="5"/>
                </g>
              </g>
            </svg>
        """)
        path = _write(tmp_path, "t.svg", svg)
        _simplify_svg(path)
        root = ET.parse(path).getroot()
        assert root.find(f"{{{NS}}}g") is None
        assert root.find(f"{{{NS}}}rect") is not None


class TestFixSuperscriptLabels:
    def _svg_with_text(self, content: str) -> str:
        return textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <text>{content}</text>
            </svg>
        """)

    def test_scientific_two_digit_exponent(self, tmp_path):
        # ¹ (U+00B9, Latin-1) mixed with ⁴ (U+2074, Superscripts block) — the misalignment case
        path = _write(tmp_path, "t.svg", self._svg_with_text("P = 1.94×10⁻¹⁴"))
        _fix_superscript_labels(path)
        root = ET.parse(path).getroot()
        text_el = root.find(f"{{{NS}}}text")
        assert text_el is not None
        assert text_el.text == "P = 1.94×10"
        tspan = text_el.find(f"{{{NS}}}tspan")
        assert tspan is not None
        assert tspan.get("dy") == "-2.5"
        assert tspan.get("font-size") == "4"
        assert tspan.text == "−14"

    def test_power_notation_single_digit(self, tmp_path):
        path = _write(tmp_path, "t.svg", self._svg_with_text("P ≈ 10⁻⁵"))
        _fix_superscript_labels(path)
        root = ET.parse(path).getroot()
        text_el = root.find(f"{{{NS}}}text")
        assert text_el is not None
        tspan = text_el.find(f"{{{NS}}}tspan")
        assert tspan is not None
        assert tspan.text == "−5"

    def test_no_match_leaves_svg_unchanged(self, tmp_path):
        original = self._svg_with_text("P = 0.023")
        path = _write(tmp_path, "t.svg", original)
        mtime_before = (tmp_path / "t.svg").stat().st_mtime
        _fix_superscript_labels(path)
        # File not rewritten when there is nothing to fix
        assert (tmp_path / "t.svg").stat().st_mtime == mtime_before

    def test_aria_label_attribute_not_modified(self, tmp_path):
        # Vega adds aria-label attributes with the same text — must not inject <tspan> there
        svg = textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <text aria-label="P = 1.94×10⁻¹⁴">P = 1.94×10⁻¹⁴</text>
            </svg>
        """)
        path = _write(tmp_path, "t.svg", svg)
        _fix_superscript_labels(path)
        root = ET.parse(path).getroot()
        text_el = root.find(f"{{{NS}}}text")
        assert text_el is not None
        # aria-label attribute must remain a plain string (no injected markup)
        assert text_el.get("aria-label") == "P = 1.94×10⁻¹⁴"
        # But the text content should be fixed
        assert text_el.find(f"{{{NS}}}tspan") is not None

    def test_nested_tspan_fixed(self, tmp_path):
        # Vega often wraps text content in a <tspan> inside <text>
        svg = textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <text><tspan dy="0">P = 3.03×10⁻¹⁴</tspan></text>
            </svg>
        """)
        path = _write(tmp_path, "t.svg", svg)
        _fix_superscript_labels(path)
        root = ET.parse(path).getroot()
        outer_tspan = root.find(f".//{{{NS}}}tspan[@dy='0']")
        assert outer_tspan is not None
        assert outer_tspan.text == "P = 3.03×10"
        inner_tspan = outer_tspan.find(f"{{{NS}}}tspan")
        assert inner_tspan is not None
        assert inner_tspan.text == "−14"
