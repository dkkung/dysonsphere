import json
import math
import re
import struct
import textwrap
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

import altair as alt
import polars as pl
import pytest

from dysonsphere.export import (
    _fix_log_minor_ticks,
    _fix_superscript_labels,
    _fix_tick_alignment,
    _inject_png_metadata,
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


def _tick_xs(path):
    """Collect x-axis tick translate-x values from a test SVG."""
    root = ET.parse(path).getroot()
    xs = []

    def collect(el):
        for child in el:
            if child.get("class", "") == "mark-rule role-axis-tick":
                for line in child:
                    m = re.match(r"translate\(([\d.]+),", line.get("transform", ""))
                    if m:
                        xs.append(float(m.group(1)))
            else:
                collect(child)

    collect(root)
    return xs


def _y_minor_positions(path, minor_size):
    """Y-axis minor tick y values, identified by x2 == -minor_size."""
    root = ET.parse(path).getroot()
    ys = []
    for line in root.iter(f"{{{NS}}}line"):
        m = re.match(r"translate\(0,([\d.]+)\)$", line.get("transform", ""))
        if m and line.get("x2") == f"-{minor_size}":
            ys.append(float(m.group(1)))
    return sorted(ys)


def _x_minor_positions(path, minor_size):
    """X-axis minor tick x values, identified by y2 == minor_size."""
    root = ET.parse(path).getroot()
    xs = []
    for line in root.iter(f"{{{NS}}}line"):
        m = re.match(r"translate\(([\d.]+),0\)$", line.get("transform", ""))
        if m and line.get("y2") == str(minor_size):
            xs.append(float(m.group(1)))
    return sorted(xs)


def _y_tick_svg(major_ys, minor_ys, major_size=5, minor_size=3):
    lines = [f'  <line transform="translate(0,{y})" x1="0" y1="0" x2="-{major_size}" y2="0"/>' for y in major_ys]
    lines += [f'  <line transform="translate(0,{y})" x1="0" y1="0" x2="-{minor_size}" y2="0"/>' for y in minor_ys]
    return f'<svg xmlns="{NS}">\n' + "\n".join(lines) + "\n</svg>"


def _x_tick_svg(major_xs, minor_xs, major_size=5, minor_size=3):
    lines = [f'  <line transform="translate({x},0)" x1="0" y1="0" x2="0" y2="{major_size}"/>' for x in major_xs]
    lines += [f'  <line transform="translate({x},0)" x1="0" y1="0" x2="0" y2="{minor_size}"/>' for x in minor_xs]
    return f'<svg xmlns="{NS}">\n' + "\n".join(lines) + "\n</svg>"


_TICK_SVG = (
    f'<svg xmlns="{NS}">'
    '<g class="mark-rule role-axis-tick">'
    '<line transform="translate({x0},0)" x1="0" y1="0" x2="0" y2="-3"/>'
    '<line transform="translate({x1},0)" x1="0" y1="0" x2="0" y2="-3"/>'
    '<line transform="translate({x2},0)" x1="0" y1="0" x2="0" y2="-3"/>'
    "</g></svg>"
)


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
        save(simple_chart, str(tmp_path / "out"), background=["light"])
        assert (tmp_path / "out_light.png").exists()
        assert (tmp_path / "out_light.svg").exists()

    def test_dark_files_created(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), background=["dark"])
        assert (tmp_path / "out_dark.png").exists()
        assert (tmp_path / "out_dark.svg").exists()

    def test_both_variants_by_default(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"))
        for suffix in ["_light", "_dark"]:
            assert (tmp_path / f"out{suffix}.png").exists()
            assert (tmp_path / f"out{suffix}.svg").exists()

    def test_vega_spec_saved(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), background=["light"])
        assert (tmp_path / "out_vegalite.json").exists()

    def test_vega_spec_skipped(self, simple_chart, tmp_path):
        save(
            simple_chart,
            str(tmp_path / "out"),
            saveVegaSpec=False,
            background=["light"],
        )
        assert not (tmp_path / "out_vegalite.json").exists()

    def test_layer_chart(self, tmp_path):
        from typing import cast

        df = pl.DataFrame({"x": ["A", "B"], "y": [1.0, 2.0]})
        base = alt.Chart(df).mark_point().encode(x="x:N", y="y:Q")
        layer = cast(alt.LayerChart, alt.layer(base))
        save(layer, str(tmp_path / "out"), background=["light"])
        assert (tmp_path / "out_light.png").exists()

    def test_hconcat_chart(self, tmp_path):
        df = pl.DataFrame({"x": ["A", "B"], "y": [1.0, 2.0]})
        panel = alt.Chart(df).mark_point().encode(x="x:N", y="y:Q")
        hcat = alt.hconcat(panel, panel)
        save(hcat, str(tmp_path / "out"), background=["light"])
        assert (tmp_path / "out_light.png").exists()

    def test_vconcat_chart(self, tmp_path):
        df = pl.DataFrame({"x": ["A", "B"], "y": [1.0, 2.0]})
        panel = alt.Chart(df).mark_point().encode(x="x:N", y="y:Q")
        vcat = alt.vconcat(panel, panel)
        save(vcat, str(tmp_path / "out"), background=["light"])
        assert (tmp_path / "out_light.png").exists()

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
        assert (tmp_path / "out_light.png").exists()

    def test_callable_chart(self, tmp_path):
        df = pl.DataFrame({"x": ["A", "B"], "y": [1.0, 2.0]})
        save(
            lambda: alt.Chart(df).mark_point().encode(x="x:N", y="y:Q"),
            str(tmp_path / "out"),
            background=["light"],
        )
        assert (tmp_path / "out_light.png").exists()

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
        save(simple_chart, str(tmp_path / "out"), background=["light"])
        assert (tmp_path / "out_light.png").stat().st_size > 100

    def test_description_in_spec(self, simple_chart, tmp_path):
        save(
            simple_chart,
            str(tmp_path / "out"),
            description="my chart",
            background=["light"],
        )
        assert "my chart" in (tmp_path / "out_vegalite.json").read_text()

    def test_description_in_svg(self, simple_chart, tmp_path):
        save(
            simple_chart,
            str(tmp_path / "out"),
            description="my chart",
            saveMetadata=False,
            background=["light"],
        )
        assert "<desc>my chart</desc>" in (tmp_path / "out_light.svg").read_text()

    def test_save_metadata_on_by_default(self, simple_chart, tmp_path):
        # The structured dysonsphere block is embedded by default; no prose provenance.
        save(simple_chart, str(tmp_path / "out"), background=["light"])
        svg = (tmp_path / "out_light.svg").read_text()
        assert 'metadata id="dysonsphere"' in svg
        assert "Generated by" not in svg  # provenance is structured-only, not prose

    def test_save_metadata_can_be_disabled(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), saveMetadata=False, background=["light"])
        assert 'metadata id="dysonsphere"' not in (tmp_path / "out_light.svg").read_text()
        assert "usermeta" not in (tmp_path / "out_vegalite.json").read_text()

    def test_save_metadata_versions_in_provenance(self, simple_chart, tmp_path):
        import importlib.metadata

        import altair as alt

        save(simple_chart, str(tmp_path / "out"), saveMetadata=True, background=["light"])
        prov = json.loads((tmp_path / "out_vegalite.json").read_text())["usermeta"]["dysonsphere"]["provenance"]
        assert prov["altair"] == alt.__version__
        assert prov["dysonsphere"] == importlib.metadata.version("dysonsphere")

    def test_no_desc_when_no_user_description(self, simple_chart, tmp_path):
        # Without an explicit description=, there is no prose <desc> at all — only structured.
        save(simple_chart, str(tmp_path / "out"), background=["light"])
        assert "<desc>" not in (tmp_path / "out_light.svg").read_text()

    def test_json_description_is_raw_user_description_only(self, simple_chart, tmp_path):
        # The JSON description carries the user's text only — provenance and report text
        # are NOT duplicated there (they live structured under usermeta).
        save(simple_chart, str(tmp_path / "out"), description="Figure 1", background=["light"])
        desc = json.loads((tmp_path / "out_vegalite.json").read_text())["description"]
        assert desc == "Figure 1"
        assert "Generated by" not in desc

    def test_svg_desc_is_raw_user_description_only(self, simple_chart, tmp_path):
        # The SVG <desc> holds exactly the user's description — nothing auto-appended.
        save(simple_chart, str(tmp_path / "out"), description="Figure 1", background=["light"])
        svg = (tmp_path / "out_light.svg").read_text()
        assert "<desc>Figure 1</desc>" in svg
        assert "Generated by" not in svg


class TestSaveUsermeta:
    @pytest.fixture
    def stats_chart(self):
        import numpy as np

        import dysonsphere as ds

        cats = ["A", "B", "C"]
        rng = np.random.default_rng(0)
        df = pl.DataFrame(
            {"g": [c for c in cats for _ in range(20)], "v": np.concatenate([rng.normal(m, 1, 20) for m in (1, 2, 3)])}
        )
        return ds.mark_strip(df, "g", "v", cats) + ds.add_comparisons(df, "g", "v", test="anova", categories=cats)

    def _usermeta(self, tmp_path, name="out"):
        return json.loads((tmp_path / f"{name}_vegalite.json").read_text())["usermeta"]

    def _svg_metadata(self, tmp_path, name="out_light"):
        svg = (tmp_path / f"{name}.svg").read_text(encoding="utf-8")
        m = re.search(r'<metadata id="dysonsphere"><!\[CDATA\[(.*?)\]\]></metadata>', svg, re.DOTALL)
        return json.loads(m.group(1)) if m else None

    def _png_dysonsphere_chunk(self, tmp_path, name="out_light"):
        data = (tmp_path / f"{name}.png").read_bytes()
        i = 8
        while i < len(data):
            length = struct.unpack(">I", data[i + 4 - 4 : i + 4])[0]
            ctype = data[i + 4 : i + 8]
            chunk = data[i + 8 : i + 8 + length]
            if ctype == b"iTXt" and chunk.split(b"\x00", 1)[0] == b"dysonsphere":
                # after the keyword null come 4 more nulls (compflag/method/lang/transkw), then text
                text = chunk.split(b"\x00", 1)[1].lstrip(b"\x00")
                return json.loads(text.decode("utf-8"))
            i += 12 + length
            if ctype == b"IEND":
                break
        return None

    def test_provenance_block_present(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), background=["light"])
        prov = self._usermeta(tmp_path)["dysonsphere"]["provenance"]
        assert list(prov) == ["user", "script", "timestamp", "python", "altair", "dysonsphere"]  # order matches text
        assert prov["timestamp"].endswith("Z") and "T" in prov["timestamp"]  # ISO-8601

    def test_statistics_records_embedded(self, stats_chart, tmp_path):
        save(stats_chart, str(tmp_path / "out"), background=["light"])
        stats = self._usermeta(tmp_path)["dysonsphere"]["statistics"]
        assert len(stats) == 1
        rec = stats[0]
        assert rec["kind"] == "omnibus" and rec["omnibus"]["name"] == "ANOVA"
        assert isinstance(rec["omnibus"]["pvalue"], float)  # real number, not text
        assert len(rec["comparisons"]["pairs"]) == 3

    def test_correlation_record_embedded(self, tmp_path):
        import numpy as np

        import dysonsphere as ds

        rng = np.random.default_rng(0)
        x = rng.uniform(0, 10, 40)
        df = pl.DataFrame({"x": x, "y": 0.9 * x + rng.normal(0, 1, 40)})
        chart = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q") + ds.add_correlation(df, "x", "y")
        save(chart, str(tmp_path / "out"), background=["light"])
        rec = self._usermeta(tmp_path)["dysonsphere"]["statistics"][0]
        assert rec["kind"] == "correlation" and rec["method"] == "pearson"
        assert isinstance(rec["coefficient"]["value"], float) and rec["fit"]["slope"] is not None

    def test_no_statistics_key_without_add_comparisons(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), background=["light"])
        assert "statistics" not in self._usermeta(tmp_path)["dysonsphere"]

    def test_merges_with_user_usermeta(self, tmp_path):
        df = pl.DataFrame({"x": [1, 2, 3], "y": [1.0, 2.0, 3.0]})
        chart = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q").properties(usermeta={"project": "Apollo"})
        save(chart, str(tmp_path / "out"), background=["light"])
        um = self._usermeta(tmp_path)
        assert um["project"] == "Apollo"  # user's key preserved
        assert "provenance" in um["dysonsphere"]

    def test_no_usermeta_when_metadata_disabled(self, stats_chart, tmp_path):
        save(stats_chart, str(tmp_path / "out"), saveMetadata=False, background=["light"])
        assert "usermeta" not in (tmp_path / "out_vegalite.json").read_text()

    def test_svg_embeds_structured_metadata(self, stats_chart, tmp_path):
        save(stats_chart, str(tmp_path / "out"), background=["light"])
        block = self._svg_metadata(tmp_path)
        assert block is not None
        assert list(block["provenance"]) == ["user", "script", "timestamp", "python", "altair", "dysonsphere"]
        assert block["statistics"][0]["omnibus"]["name"] == "ANOVA"

    def test_svg_metadata_preserves_unicode(self, stats_chart, tmp_path):
        # η² must survive as literal UTF-8 in the SVG (ensure_ascii=False), not ²
        save(stats_chart, str(tmp_path / "out"), background=["light"])
        assert self._svg_metadata(tmp_path)["statistics"][0]["omnibus"]["effect"]["symbol"] == "η²"

    def test_png_embeds_structured_metadata(self, stats_chart, tmp_path):
        save(stats_chart, str(tmp_path / "out"), background=["light"])
        block = self._png_dysonsphere_chunk(tmp_path)
        assert block is not None
        assert block["statistics"][0]["omnibus"]["name"] == "ANOVA"
        assert "provenance" in block

    def test_no_svg_png_metadata_when_disabled(self, stats_chart, tmp_path):
        save(stats_chart, str(tmp_path / "out"), saveMetadata=False, background=["light"])
        assert self._svg_metadata(tmp_path) is None
        assert self._png_dysonsphere_chunk(tmp_path) is None

    def _svg_report(self, tmp_path, name="out_light"):
        svg = (tmp_path / f"{name}.svg").read_text(encoding="utf-8")
        m = re.search(r'<metadata id="dysonsphere-report">(.*?)</metadata>', svg, re.DOTALL)
        return m.group(1) if m else None

    def _png_report_text(self, tmp_path, name="out_light"):
        data = (tmp_path / f"{name}.png").read_bytes()
        i = 8
        while i < len(data):
            length = struct.unpack(">I", data[i : i + 4])[0]
            ctype = data[i + 4 : i + 8]
            chunk = data[i + 8 : i + 8 + length]
            if ctype == b"iTXt" and chunk.split(b"\x00", 1)[0] == b"dysonsphere-report":
                return chunk.split(b"\x00", 1)[1].lstrip(b"\x00").decode("utf-8")
            i += 12 + length
            if ctype == b"IEND":
                break
        return None

    def test_report_embedded_by_default(self, stats_chart, tmp_path):
        save(stats_chart, str(tmp_path / "out"), background=["light"])
        report = self._usermeta(tmp_path)["dysonsphere"]["report"]  # JSON member
        assert report.startswith("Statistics")
        assert "\n" in self._svg_report(tmp_path)  # SVG readable channel, real newlines
        assert self._png_report_text(tmp_path).startswith("Statistics")  # PNG readable chunk

    def test_report_not_in_description(self, stats_chart, tmp_path):
        save(stats_chart, str(tmp_path / "out"), description="my caption", background=["light"])
        spec = json.loads((tmp_path / "out_vegalite.json").read_text())
        assert spec["description"] == "my caption"  # description is the user's text only

    def test_report_not_duplicated_in_structured_blob(self, stats_chart, tmp_path):
        # the report is its own JSON member / readable channel, not baked into the structured blob
        save(stats_chart, str(tmp_path / "out"), background=["light"])
        assert "report" not in self._svg_metadata(tmp_path)
        assert "report" not in self._png_dysonsphere_chunk(tmp_path)

    def test_embed_report_false_suppresses_it(self, stats_chart, tmp_path):
        save(stats_chart, str(tmp_path / "out"), embedReport=False, background=["light"])
        block = self._usermeta(tmp_path)["dysonsphere"]
        assert "statistics" in block and "report" not in block  # structured kept, report dropped
        assert self._svg_report(tmp_path) is None and self._png_report_text(tmp_path) is None


# ── _fix_tick_alignment() ─────────────────────────────────────────────────────


class TestFixTickAlignment:
    def test_point_scale_corrected(self, tmp_path):
        # 3 categories, W=200, point scale: step=W/n, position=round(step*(0.5+i))
        step = 200 / 3
        path = _write(tmp_path, "t.svg", _TICK_SVG.format(x0=33, x1=100, x2=167))
        _fix_tick_alignment(path, band_padding=0.1, chart_width=200)
        xs = _tick_xs(path)
        assert xs == pytest.approx([step * 0.5, step * 1.5, step * 2.5], abs=0.001)

    def test_band_inner_scale_corrected(self, tmp_path):
        # paddingInner=paddingOuter=band_padding, W=200: step=W/(n+bp)
        step = 200 / (3 + 0.1)
        x0, x1, x2 = int(step * 0.55), int(step * 1.55), int(step * 2.55)
        path = _write(tmp_path, "t.svg", _TICK_SVG.format(x0=x0, x1=x1, x2=x2))
        _fix_tick_alignment(path, band_padding=0.1, chart_width=200)
        xs = _tick_xs(path)
        assert xs == pytest.approx([step * 0.55, step * 1.55, step * 2.55], abs=0.001)

    def test_xoffset_scale_corrected(self, tmp_path):
        # paddingInner=0, paddingOuter=band_padding, W=200: step=W/(n+2*bp)
        step = 200 / (3 + 2 * 0.1)  # 62.5
        x0, x1, x2 = int(step * 0.6), int(step * 1.6), int(step * 2.6)
        path = _write(tmp_path, "t.svg", _TICK_SVG.format(x0=x0, x1=x1, x2=x2))
        _fix_tick_alignment(path, band_padding=0.1, chart_width=200)
        xs = _tick_xs(path)
        assert xs == pytest.approx([step * 0.6, step * 1.6, step * 2.6], abs=0.001)

    def test_no_match_leaves_file_unchanged(self, tmp_path):
        # Positions that don't match any formula → early return, file untouched
        content = _TICK_SVG.format(x0=25, x1=75, x2=125)
        path = _write(tmp_path, "t.svg", content)
        _fix_tick_alignment(path, band_padding=0.1, chart_width=200)
        assert Path(path).read_text() == content

    def test_ambiguous_no_box_marks_returns_unfixed(self, tmp_path):
        # With W=100, n=6, band_padding=0.1, Case 0 and Case pi floor to the same
        # integers. Without box marks to disambiguate, ticks are left unchanged.
        bp = 0.1
        W = 100
        n = 6
        step0 = W / (n + 2 * bp)
        step_pi = W / (n + bp)
        ints0 = [int(step0 * (bp + i + 0.5)) for i in range(n)]
        ints_pi = [int(step_pi * (i + 0.5 + bp / 2)) for i in range(n)]
        assert ints0 == ints_pi, "precondition: both cases must floor to same ints for this test"

        lines = "".join(f'<line transform="translate({x},0)" x1="0" y1="0" x2="0" y2="-3"/>' for x in ints0)
        svg = f'<svg xmlns="{NS}"><g class="mark-rule role-axis-tick">{lines}</g></svg>'
        path = _write(tmp_path, "t.svg", svg)
        _fix_tick_alignment(path, band_padding=bp, chart_width=W)
        xs = _tick_xs(path)
        # No box marks → can't resolve; ticks stay at integer positions
        assert xs == pytest.approx([float(x) for x in ints0], abs=0.001)

    def test_ambiguous_box_marks_at_case0_picks_case0(self, tmp_path):
        # When ambiguous, box marks at Case 0 positions should cause Case 0 to be applied.
        bp = 0.1
        W = 100
        n = 6
        step0 = W / (n + 2 * bp)
        ints = [int(step0 * (bp + i + 0.5)) for i in range(n)]  # same for both formulas

        lines = "".join(f'<line transform="translate({x},0)" x1="0" y1="0" x2="0" y2="-3"/>' for x in ints)
        # Box marks at Case 0 centers: M(center-3),y L(center+3),y ...
        box_marks = "".join(
            f'<path aria-roledescription="box" d="M{step0 * (bp + i + 0.5) - 3},10L{step0 * (bp + i + 0.5) + 3},10"/>'
            for i in range(n)
        )
        svg = f'<svg xmlns="{NS}"><g class="mark-rule role-axis-tick">{lines}</g>{box_marks}</svg>'
        path = _write(tmp_path, "t.svg", svg)
        _fix_tick_alignment(path, band_padding=bp, chart_width=W)
        xs = _tick_xs(path)
        expected = [round(step0 * (bp + i + 0.5), 4) for i in range(n)]
        assert xs == pytest.approx(expected, abs=0.001)

    def test_ambiguous_box_marks_at_case_pi_picks_case_pi(self, tmp_path):
        # When ambiguous, box marks at Case pi positions should cause Case pi to be applied.
        bp = 0.1
        W = 100
        n = 6
        step_pi = W / (n + bp)
        ints = [int(step_pi * (i + 0.5 + bp / 2)) for i in range(n)]

        lines = "".join(f'<line transform="translate({x},0)" x1="0" y1="0" x2="0" y2="-3"/>' for x in ints)
        box_marks = "".join(
            f'<path aria-roledescription="box"'
            f' d="M{step_pi * (i + 0.5 + bp / 2) - 3},10'
            f'L{step_pi * (i + 0.5 + bp / 2) + 3},10"/>'
            for i in range(n)
        )
        svg = f'<svg xmlns="{NS}"><g class="mark-rule role-axis-tick">{lines}</g>{box_marks}</svg>'
        path = _write(tmp_path, "t.svg", svg)
        _fix_tick_alignment(path, band_padding=bp, chart_width=W)
        xs = _tick_xs(path)
        expected = [round(step_pi * (i + 0.5 + bp / 2), 4) for i in range(n)]
        assert xs == pytest.approx(expected, abs=0.001)

    def test_grid_lines_x_corrected(self, tmp_path):
        # Grid lines use translate(x,-chartHeight) not translate(x,0); both must be fixed.
        step = 200 / (3 + 0.1)
        x0, x1, x2 = int(step * 0.55), int(step * 1.55), int(step * 2.55)
        lines = "".join(f'<line transform="translate({x},-100)" x1="0" y1="0" x2="0" y2="100"/>' for x in [x0, x1, x2])
        svg = f'<svg xmlns="{NS}"><g class="mark-rule role-axis-grid">{lines}</g></svg>'
        path = _write(tmp_path, "t.svg", svg)
        _fix_tick_alignment(path, band_padding=0.1, chart_width=200)
        root = ET.parse(path).getroot()
        xs = sorted(
            float(m.group(1))
            for line in root.iter(f"{{{NS}}}line")
            if (m := re.match(r"translate\(([\d.]+),", line.get("transform", "")))
        )
        expected = [round(step * (0.55 + i), 4) for i in range(3)]
        assert xs == pytest.approx(expected, abs=0.001)

    def test_grid_lines_y_span_extended_by_axis_offset(self, tmp_path):
        # axis_offset extends grid line y-span upward to eliminate the top-border gap.
        step = 200 / (3 + 0.1)
        x0, x1, x2 = int(step * 0.55), int(step * 1.55), int(step * 2.55)
        lines = "".join(f'<line transform="translate({x},-100)" x1="0" y1="0" x2="0" y2="100"/>' for x in [x0, x1, x2])
        svg = f'<svg xmlns="{NS}"><g class="mark-rule role-axis-grid">{lines}</g></svg>'
        path = _write(tmp_path, "t.svg", svg)
        _fix_tick_alignment(path, band_padding=0.1, chart_width=200, axis_offset=3)
        root = ET.parse(path).getroot()
        ty_vals, y2_vals = [], []
        for line in root.iter(f"{{{NS}}}line"):
            m = re.match(r"translate\([\d.]+,([-\d.]+)\)", line.get("transform", ""))
            if m:
                ty_vals.append(float(m.group(1)))
                y2_vals.append(float(line.get("y2", "0")))
        assert all(t == pytest.approx(-103.0, abs=0.001) for t in ty_vals)
        assert all(y == pytest.approx(103.0, abs=0.001) for y in y2_vals)


# ── _fix_log_minor_ticks() ───────────────────────────────────────────────────


class TestFixLogMinorTicks:
    def test_y_log10_corrected(self, tmp_path):
        # 1 decade: major at y=0 (value=10) and y=100 (value=1), span=100
        # m=2 → integer 70, exact 69.897;  m=5 → integer 30, exact 30.103
        minor_ints = [5, 10, 22, 30, 40, 52, 70]
        path = _write(tmp_path, "t.svg", _y_tick_svg([0, 100], minor_ints))
        _fix_log_minor_ticks(path)
        ys = _y_minor_positions(path, minor_size=3)
        m2 = [y for y in ys if abs(y - 69.897) < 1.0]
        assert len(m2) == 1
        assert m2[0] == pytest.approx(100 - math.log10(2) * 100, abs=0.01)
        m5 = [y for y in ys if abs(y - 30.103) < 1.0]
        assert len(m5) == 1
        assert m5[0] == pytest.approx(100 - math.log10(5) * 100, abs=0.01)

    def test_y_uniform_corrected(self, tmp_path):
        # Power-scale: major at y=0 and y=97 (non-divisible span), 4 equal-space minors
        # Exact: k/5*97 for k=1..4 → 19.4, 38.8, 58.2, 77.6; ints → 19, 39, 58, 78
        path = _write(tmp_path, "t.svg", _y_tick_svg([0, 97], [19, 39, 58, 78]))
        _fix_log_minor_ticks(path)
        ys = _y_minor_positions(path, minor_size=3)
        assert sorted(ys) == pytest.approx([97 * k / 5 for k in range(1, 5)], abs=0.01)

    def test_y_single_tick_size_no_change(self, tmp_path):
        # Only one tick size → no minor ticks identified → file not rewritten
        content = _y_tick_svg([0, 100], [])
        path = _write(tmp_path, "t.svg", content)
        _fix_log_minor_ticks(path)
        assert Path(path).read_text() == content

    def test_x_log10_corrected(self, tmp_path):
        # 1 decade: major at x=0 and x=100, minor at integer-rounded log positions
        # m=2 → integer 30, exact 30.103;  m=5 → integer 70, exact 69.897
        minor_ints = [30, 48, 60, 70, 78, 85, 90, 95]
        path = _write(tmp_path, "t.svg", _x_tick_svg([0, 100], minor_ints))
        _fix_log_minor_ticks(path)
        xs = _x_minor_positions(path, minor_size=3)
        m2 = [x for x in xs if abs(x - 30.103) < 1.0]
        assert len(m2) == 1
        assert m2[0] == pytest.approx(math.log10(2) * 100, abs=0.01)

    def test_x_uniform_corrected(self, tmp_path):
        # Power-scale x-axis: major at x=0 and x=97, 4 equal-space minors
        path = _write(tmp_path, "t.svg", _x_tick_svg([0, 97], [19, 39, 58, 78]))
        _fix_log_minor_ticks(path)
        xs = _x_minor_positions(path, minor_size=3)
        assert sorted(xs) == pytest.approx([97 * k / 5 for k in range(1, 5)], abs=0.01)


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


# ── _inject_png_metadata() ───────────────────────────────────────────────────


def _make_minimal_png() -> bytes:
    """1×1 white RGB PNG for use in metadata tests."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff"))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _read_png_chunks(png: bytes) -> list[tuple[bytes, bytes]]:
    """Return (type, data) for every chunk in the PNG."""
    chunks = []
    pos = 8  # skip signature
    while pos < len(png):
        length = struct.unpack(">I", png[pos : pos + 4])[0]
        tag = png[pos + 4 : pos + 8]
        data = png[pos + 8 : pos + 8 + length]
        chunks.append((tag, data))
        pos += 4 + 4 + length + 4
    return chunks


class TestInjectPngMetadata:
    def test_itxt_chunk_present(self):
        png = _inject_png_metadata(_make_minimal_png(), "hello")
        types = [t for t, _ in _read_png_chunks(png)]
        assert b"iTXt" in types

    def test_itxt_placed_after_ihdr(self):
        png = _inject_png_metadata(_make_minimal_png(), "hello")
        types = [t for t, _ in _read_png_chunks(png)]
        assert types[0] == b"IHDR"
        assert types[1] == b"iTXt"

    def test_description_keyword_and_text(self):
        desc = "Generated with test.py by user on 20260630."
        png = _inject_png_metadata(_make_minimal_png(), desc)
        for tag, data in _read_png_chunks(png):
            if tag == b"iTXt":
                null = data.index(b"\x00")
                keyword = data[:null].decode("utf-8")
                # skip keyword\0 + compression_flag + compression_method + lang\0 + translated\0
                text = data[null + 5 :].decode("utf-8")
                assert keyword == "Description"
                assert text == desc
                return
        pytest.fail("no iTXt chunk found")

    def test_unicode_description_roundtrips(self):
        desc = "café — by dkung 2026"
        png = _inject_png_metadata(_make_minimal_png(), desc)
        for tag, data in _read_png_chunks(png):
            if tag == b"iTXt":
                null = data.index(b"\x00")
                text = data[null + 5 :].decode("utf-8")
                assert text == desc
                return
        pytest.fail("no iTXt chunk found")

    def test_all_chunk_crcs_valid(self):
        png = _inject_png_metadata(_make_minimal_png(), "crc check")
        pos = 8
        while pos < len(png):
            length = struct.unpack(">I", png[pos : pos + 4])[0]
            tag = png[pos + 4 : pos + 8]
            data = png[pos + 8 : pos + 8 + length]
            stored = struct.unpack(">I", png[pos + 8 + length : pos + 12 + length])[0]
            assert (zlib.crc32(tag + data) & 0xFFFFFFFF) == stored, f"bad CRC in {tag}"
            pos += 4 + 4 + length + 4

    def test_existing_chunks_unchanged(self):
        original = _make_minimal_png()
        result = _inject_png_metadata(original, "test")
        orig_chunks = _read_png_chunks(original)
        result_chunks = _read_png_chunks(result)
        # result has one extra chunk (iTXt); all original chunks must be present and unchanged
        non_itxt = [(t, d) for t, d in result_chunks if t != b"iTXt"]
        assert non_itxt == orig_chunks
