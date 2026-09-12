import json
import math
import re
import struct
import textwrap
import xml.etree.ElementTree as ET
from typing import Any, cast

import altair as alt
import polars as pl
import pytest

from dysonsphere.annotations import _rule_cap_marker
from dysonsphere.export import (
    _TRANSLATE,
    _align_grid_to_content,
    _decorate_rule_segments,
    _fix_font_for_illustrator,
    _fix_subscript_labels,
    _fix_superscript_labels,
    _flip_ticks_inward,
    _illustrator_font_family,
    _italicize_stat_symbols,
    _layer_axes_below_marks,
    _rule_cap_options,
    _simplify_svg,
    _sink_border_below_shade,
    _typeset_scripts,
    save,
)
from dysonsphere.theme import theme
from dysonsphere.utils import _apply_spec_fixes, _suppress_nice

NS = "http://www.w3.org/2000/svg"


class TestRuleCaps:
    @staticmethod
    def _arrow_tip(path):
        match = re.match(r"M([\d.e+-]+),([\d.e+-]+)L", path)
        assert match is not None
        return tuple(map(float, match.groups()))

    @staticmethod
    def _arrow_dimensions(path):
        points = [tuple(map(float, point)) for point in re.findall(r"(?:M|L)([\d.e+-]+),([\d.e+-]+)", path)]
        assert len(points) == 3
        tip, left, right = points
        base_midpoint = ((left[0] + right[0]) / 2, (left[1] + right[1]) / 2)
        return math.dist(tip, base_midpoint), math.dist(left, right)

    @staticmethod
    def _tree(start_cap=None, end_cap=None, start_gap=0, end_gap=0, *, length=100, stroke_width=1):
        marker = _rule_cap_marker(start_cap, end_cap, start_gap, end_gap)
        root = ET.fromstring(
            f'<svg xmlns="{NS}"><g><g class="mark-rule role-mark">'
            f'<line aria-label="{marker}" transform="translate(0,0)" x2="{length}" y2="0" stroke="#123456" '
            f'stroke-width="{stroke_width}" opacity="0.4"/></g></g></svg>'
        )
        _decorate_rule_segments(root)
        return root

    def test_both_arrows_apply_tip_gap_and_shorten_shaft(self):
        root = self._tree("arrow", "arrow", 3, 3)
        line = next(root.iter(f"{{{NS}}}line"))
        assert line.get("transform") == "translate(7,0)"  # 3 px daylight + 4 px arrow depth
        assert line.get("x2") == "86"
        caps = list(root.iter(f"{{{NS}}}path"))
        assert len(caps) == 2
        assert all(cap.get("fill") == "#123456" and cap.get("opacity") == "0.4" for cap in caps)
        paths = {cap.get("d", "") for cap in caps}
        assert any(path.startswith("M3,0L") for path in paths)
        assert any(path.startswith("M97,0L") for path in paths)
        assert all(self._arrow_dimensions(path) == pytest.approx((4.0, 4.8)) for path in paths)

    @pytest.mark.parametrize(("stroke_width", "depth"), [(0.25, 2.0), (0.5, math.sqrt(8)), (1, 4.0), (4, 8.0)])
    def test_arrow_dimensions_follow_square_root_stroke_scaling(self, stroke_width, depth):
        root = self._tree("arrow", None, stroke_width=stroke_width)
        cap = next(element for element in root.iter(f"{{{NS}}}path") if element.get("class") == "ds-rule-cap")
        assert self._arrow_dimensions(cap.get("d", "")) == pytest.approx((depth, 1.2 * depth))

    def test_zero_width_arrow_has_no_cap_artifact(self):
        root = self._tree("arrow", None, stroke_width=0)
        assert not [element for element in root.iter() if element.get("class") == "ds-rule-cap"]

    @pytest.mark.parametrize("cls", ["__dsrulecap_", "__dsrulecap_bad", "__dsrulecap_1_zz", "__dsrulecap_1_ff"])
    def test_malformed_user_class_is_ignored(self, cls):
        assert _rule_cap_options(cls) is None

    def test_capless_custom_gaps_shorten_to_exact_clearance(self):
        root = self._tree(start_gap=5, end_gap=10)
        line = next(root.iter(f"{{{NS}}}line"))
        assert line.get("transform") == "translate(5,0)"
        assert line.get("x2") == "85"
        assert not list(root.iter(f"{{{NS}}}path"))

    @pytest.mark.parametrize(("cap", "tag"), [("circle", "circle"), ("square", "path")])
    @pytest.mark.parametrize(("stroke_width", "size"), [(0.25, 4), (1, 4), (4, 16)])
    def test_circle_and_square_outer_edge_and_style(self, cap, tag, stroke_width, size):
        root = self._tree(cap, None, 3, 0, stroke_width=stroke_width)
        shape = next(root.iter(f"{{{NS}}}{tag}"))
        assert shape.get("class") == "ds-rule-cap"
        line = next(root.iter(f"{{{NS}}}line"))
        assert line.get("transform") == f"translate({3 + size},0)"

    def test_mixed_caps_use_each_shapes_extent(self):
        root = self._tree("arrow", "circle", 3, 3)
        line = next(root.iter(f"{{{NS}}}line"))
        assert line.get("transform") == "translate(7,0)"
        assert line.get("x2") == "86"

    def test_short_segment_hides_shaft_and_keeps_caps(self):
        root = self._tree("arrow", "arrow", 3, 3, length=9)
        assert next(root.iter(f"{{{NS}}}line")).get("display") == "none"
        assert not list(root.iter(f"{{{NS}}}path"))

    def test_huge_gap_omits_whole_segment_without_retreating_past_target(self):
        root = self._tree("arrow", "arrow", 100, 3, length=20)
        assert next(root.iter(f"{{{NS}}}line")).get("display") == "none"
        assert not list(root.iter(f"{{{NS}}}path"))

    def test_coincident_segment_is_unchanged(self):
        root = self._tree("arrow", "arrow", 3, 3, length=0)
        line = next(root.iter(f"{{{NS}}}line"))
        assert line.get("display") == "none"
        assert not list(root.iter(f"{{{NS}}}path"))

    def test_export_reversed_nonsquare_independent_facets(self, tmp_path):
        import dysonsphere as ds
        from dysonsphere.annotations import _automatic_marker_gap

        theme(width=180, height=90, viewPadding=False)
        df = pl.DataFrame({"g": ["a", "a", "b", "b"], "x": [2, 8, 2, 8], "y": [3, 9, 3, 9]})
        base = (
            alt.Chart(df)
            .mark_point()
            .encode(
                x=alt.X("x:Q", scale=alt.Scale(domain=[0, 10], reverse=True)),
                y=alt.Y("y:Q", scale=alt.Scale(domain=[0, 10])),
            )
        )
        decorated = ds.rule(x=2, y=3, x2=8, y2=9, startCap="arrow", endCap="arrow", data=df)
        chart = (base + decorated).facet(column="g:N").resolve_scale(x="independent", y="independent")
        save(chart, tmp_path / "facets", format="svg", saveMetadata=False)
        svg = (tmp_path / "facets.svg").read_text()
        assert svg.count('class="ds-rule-cap"') == 4
        # Local rendered coordinates: reversed x maps 2->144 and 8->36 in 180 px; y maps
        # 3->63 and 9->9 in 90 px. Every start tip is exactly the shared automatic gap inward along
        # that screen vector, proving direction/aspect come from rendered SVG geometry, not data slope.
        rendered_root = ET.fromstring(svg)
        tips = [
            self._arrow_tip(el.get("d", ""))
            for el in rendered_root.iter()
            if el.get("class") == "ds-rule-cap" and el.tag.endswith("path")
        ]
        ux, uy = -108 / math.hypot(108, 54), -54 / math.hypot(108, 54)
        gap = _automatic_marker_gap()
        expected = [(144 + ux * gap, 63 + uy * gap), (36 - ux * gap, 9 - uy * gap)]
        assert all(any(math.dist(tip, want) < 1e-6 for tip in tips) for want in expected)

        zero = ds.rule(x=2, y=3, x2=8, y2=9, startCap="arrow", endCap="arrow", startGap=0, endGap=0)
        zero_chart = (
            alt.Chart(df.head(2))
            .mark_point()
            .encode(
                x=alt.X("x:Q", scale=alt.Scale(domain=[0, 10], reverse=True)),
                y=alt.Y("y:Q", scale=alt.Scale(domain=[0, 10])),
            )
            + zero
        )
        save(zero_chart, tmp_path / "zero", format="svg", saveMetadata=False)
        zero_svg = (tmp_path / "zero.svg").read_text()
        zero_root = ET.fromstring(zero_svg)
        zero_tips = [
            self._arrow_tip(el.get("d", ""))
            for el in zero_root.iter()
            if el.get("class") == "ds-rule-cap" and el.tag.endswith("path")
        ]
        assert any(math.dist(tip, (144, 63)) < 1e-6 for tip in zero_tips)
        assert any(math.dist(tip, (36, 9)) < 1e-6 for tip in zero_tips)

    def test_markers_scope_only_their_rule_marks(self, tmp_path):
        import dysonsphere as ds

        theme()
        df = pl.DataFrame({"x": [0.0, 10.0], "y": [0.0, 10.0]})
        native_rule = alt.Chart(df).mark_rule(color="green").encode(x="x:Q", y="y:Q", x2="y:Q", y2="x:Q")
        native_line = alt.Chart(df).mark_line(color="blue").encode(x="x:Q", y="y:Q")
        arrows = ds.rule(y=[2, 4], label=["a", "b"], startCap="arrow")
        circle = ds.rule(x=6, startCap="circle")
        repeated = ds.rule(x=1, y=8, x2=3, y2=9, endCap="square")
        chart = native_rule + native_line + arrows + circle + repeated + repeated
        save(chart, tmp_path / "scoped", format="svg", saveMetadata=False)
        root = ET.fromstring((tmp_path / "scoped.svg").read_text())
        caps = [el for el in root.iter() if el.get("class") == "ds-rule-cap"]
        assert len(caps) == 5  # two list rules, one circle, and the same square-rule object twice
        # Native neighboring marks retain their renderer geometry and colors.
        assert any(el.get("stroke") == "green" and el.get("display") is None for el in root.iter())
        assert any(el.get("stroke") == "blue" and el.get("display") is None for el in root.iter())

    def test_json_load_roundtrip_reapplies_caps(self, tmp_path):
        import dysonsphere as ds

        theme()
        chart = ds.rule(x=1, y=1, x2=9, y2=8, startCap="arrow", endCap="square")
        save(chart, tmp_path / "original", format=["json", "svg"], saveMetadata=False)
        loaded = ds.load(tmp_path / "original.json")
        save(cast(Any, loaded), tmp_path / "loaded", format="svg", saveMetadata=False)
        assert (tmp_path / "loaded.svg").read_text().count('class="ds-rule-cap"') == 2

    def test_cap_marker_does_not_leak_internal_data(self, tmp_path):
        import dysonsphere as ds

        theme()
        df = pl.DataFrame({"x": [1.0, 9.0], "y": [2.0, 8.0]})
        base = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q")
        chart = base + ds.rule(x=1, y=2, x2=9, y2=8, startCap="arrow", endGap=4)
        save(chart, tmp_path / "data", format="json")
        recovered = ds.metadata.read(tmp_path / "data.json", what="data")
        assert recovered.equals(df)

    def test_fresh_equivalent_cap_builds_have_stable_spec_checksum(self):
        import dysonsphere as ds
        from dysonsphere.metadata import _spec_checksum

        first = ds.rule(x=1, y=2, x2=8, y2=9, startCap="arrow", endGap=4).to_dict()
        second = ds.rule(x=1, y=2, x2=8, y2=9, startCap="arrow", endGap=4).to_dict()
        assert first == second
        assert _spec_checksum(first) == _spec_checksum(second)

    def test_export_caps_preserve_rule_opacity_and_stroke_opacity(self, tmp_path):
        import dysonsphere as ds

        theme()
        chart = ds.rule(x=1, y=1, x2=9, y2=8, startCap="circle", opacity=0).configure_rule(strokeOpacity=0.25)
        save(chart, tmp_path / "opacity", format="svg", saveMetadata=False)
        root = ET.fromstring((tmp_path / "opacity.svg").read_text())
        cap = next(el for el in root.iter() if el.get("class") == "ds-rule-cap")
        assert cap.get("opacity") == "0"
        assert cap.get("fill-opacity") == "0.25"


class TestLabelConnectorCaps:
    @staticmethod
    def _translate(transform):
        match = _TRANSLATE.match(transform)
        assert match is not None
        return tuple(map(float, match.groups()))

    @staticmethod
    def _dense_labels(connector_cap=None, *, connector_gap=None, connector_opacity=None):
        import dysonsphere as ds

        df = pl.DataFrame(
            {
                "x": [5.0, 5.05, 4.95, 5.0, 5.1, 4.9],
                "y": [5.0, 5.0, 5.0, 5.05, 4.95, 5.1],
                "label": ["alpha", "beta", "gamma", "delta", "epsilon", "zeta"],
            }
        )
        kwargs = {
            "xDomain": (0.0, 10.0),
            "yDomain": (0.0, 10.0),
            "alwaysShowConnectors": True,
            "connectorCap": connector_cap,
            "connectorGap": connector_gap,
            "connectorOpacity": connector_opacity,
        }
        return df, ds.labels(df, "x", "y", "label", **kwargs)  # ty: ignore[invalid-argument-type]

    def test_export_arrow_tip_is_existing_connector_start_no_double_gap(self, tmp_path):
        theme(width=140, height=100, viewPadding=False, axisWidth=0.5)
        _, plain = self._dense_labels(connector_gap=0)
        _, arrow = self._dense_labels("arrow", connector_gap=0)
        save(plain, tmp_path / "plain", format="svg", saveMetadata=False)
        save(arrow, tmp_path / "arrow", format="svg", saveMetadata=False)
        plain_root = ET.fromstring((tmp_path / "plain.svg").read_text())
        arrow_root = ET.fromstring((tmp_path / "arrow.svg").read_text())
        plain_starts = {
            self._translate(line.get("transform", ""))
            for line in plain_root.iter(f"{{{NS}}}line")
            if line.get("stroke") == "black" and _TRANSLATE.match(line.get("transform", ""))
        }
        tips = [
            TestRuleCaps._arrow_tip(cap.get("d", "")) for cap in arrow_root.iter() if cap.get("class") == "ds-rule-cap"
        ]
        assert tips
        assert all(any(math.dist(tip, start) < 1e-9 for start in plain_starts) for tip in tips)
        dimensions = [
            TestRuleCaps._arrow_dimensions(cap.get("d", ""))
            for cap in arrow_root.iter()
            if cap.get("class") == "ds-rule-cap"
        ]
        assert all(dimension == pytest.approx((math.sqrt(8), 1.2 * math.sqrt(8))) for dimension in dimensions)

    def test_connector_arrow_preserves_color_opacity_and_roundtrip_data(self, tmp_path):
        import dysonsphere as ds

        theme(width=140, height=100)
        df, arrows = self._dense_labels("arrow", connector_opacity=0.35)
        base = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q")
        chart = (base + arrows).configure_rule(strokeOpacity=0.4)
        save(chart, tmp_path / "labels", format=["svg", "json"])
        root = ET.fromstring((tmp_path / "labels.svg").read_text())
        caps = [element for element in root.iter() if element.get("class") == "ds-rule-cap"]
        assert caps and all(cap.get("opacity") == "0.35" and cap.get("fill-opacity") == "0.4" for cap in caps)
        loaded = ds.load(tmp_path / "labels.json")
        save(cast(Any, loaded), tmp_path / "loaded", format="svg", saveMetadata=False)
        assert 'class="ds-rule-cap"' in (tmp_path / "loaded.svg").read_text()
        assert ds.metadata.read(tmp_path / "labels.json", what="data").equals(df)

    def test_too_short_arrow_connector_is_omitted_but_label_remains(self, tmp_path):
        theme(width=100, height=100)
        df = pl.DataFrame({"x": [5.0], "y": [5.0], "label": ["a"]})
        import dysonsphere as ds

        chart = ds.labels(df, "x", "y", "label", connectorCap="arrow", alwaysShowConnectors=True)
        save(chart, tmp_path / "short", format="svg", saveMetadata=False)
        svg = (tmp_path / "short.svg").read_text()
        assert ">a</text>" in svg
        # A sub-arrow-depth connector is omitted as a whole; no intersecting/shrunken arrow is emitted.
        assert 'class="ds-rule-cap"' not in svg


def test_png_ppi_scales_from_svg_72_units_per_inch(tmp_path):
    theme()
    chart = alt.Chart({"values": [{"x": 0, "y": 0}, {"x": 1, "y": 1}]}).mark_point().encode(x="x:Q", y="y:Q")
    stem = tmp_path / "font_scale"
    save(chart, stem, format=["svg", "png"], ppi=1200, saveMetadata=False)

    svg = (tmp_path / "font_scale.svg").read_text(encoding="utf-8")
    width_match = re.search(r'<svg[^>]+width="([\d.]+)"', svg)
    assert width_match is not None
    svg_width = float(width_match.group(1))
    png = (tmp_path / "font_scale.png").read_bytes()
    png_width = struct.unpack(">I", png[16:20])[0]
    assert png_width == int(svg_width * 1200 / 72)
    assert 'font-size="6px"' in svg


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
        assert "Helvetica Neue" in (tmp_path / "out.html").read_text(encoding="utf-8")

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
        # Inward tick direction is a static-SVG feature; HTML must NOT carry a negative tickSize
        # (the negative-tickSize trick renders inconsistently in the browser's Vega build).
        theme(tickDirection="in")
        df = pl.DataFrame({"x": [1.0, 2.0, 3.0], "y": [1.0, 2.0, 3.0]})
        chart = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q")
        save(chart, str(tmp_path / "out"), format="html", background=["light"])
        html = (tmp_path / "out.html").read_text(encoding="utf-8").replace(" ", "")
        assert '"tickSize":-' not in html


# ── show() ───────────────────────────────────────────────────────────────────


class TestShow:
    def test_returns_ipython_html(self, simple_chart):
        # HTML, not SVG: an image/svg+xml output goes to the frontend's image renderer, which in
        # VS Code composites onto white - a transparent dark-mode figure came back white on white.
        from dysonsphere.export import show

        obj = show(simple_chart)
        assert type(obj).__name__ == "HTML"  # IPython.display.HTML
        assert cast(str, obj.data).startswith("<svg")  # bare markup, no XML prolog to confuse the HTML parser

    def test_runs_full_pipeline_inward_ticks(self):
        # show()'s whole point: the preview matches save() output. With inward ticks the preview
        # SVG must have inward ticks (proving _flip_ticks_inward ran) - Altair's raw render wouldn't.
        from dysonsphere.export import show

        theme(tickDirection="in")
        df = pl.DataFrame({"x": [1.0, 2.0, 3.0], "y": [1.0, 2.0, 3.0]})
        chart = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q")
        svg = cast(str, show(chart).data)
        y2s = [float(m) for m in re.findall(r'y2="(-?[\d.]+)"', svg) if 0 < abs(float(m)) < 20]
        assert y2s and all(v < 0 for v in y2s)  # inward

    def test_accepts_callable(self):
        from dysonsphere.export import show

        df = pl.DataFrame({"x": [1.0, 2.0], "y": [1.0, 2.0]})
        obj = show(lambda: alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q"))
        assert "<svg" in cast(str, obj.data)

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

    def test_works_under_vegafusion_transformer(self, simple_chart):
        # A session-wide vegafusion transformer makes Altair's to_dict() raise unless
        # format="vega"; show() must pin the "default" transformer for its render (like save())
        # so the preview still works, and restore vegafusion afterward.
        from dysonsphere.export import show

        prev = alt.data_transformers.active
        alt.data_transformers.enable("vegafusion")
        try:
            svg = cast(str, show(simple_chart).data)
            assert "<svg" in svg
            assert alt.data_transformers.active == "vegafusion"  # restored
        finally:
            alt.data_transformers.enable(prev)

    def test_max_rows_blocks_large_data(self):
        from dysonsphere.export import show

        df = pl.DataFrame({"x": [float(i) for i in range(20)], "y": [float(i) for i in range(20)]})
        chart = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q")
        with pytest.raises(ValueError, match="maxRows=5"):
            show(chart, maxRows=5)

    def test_override_max_rows_allows_large_data(self):
        from dysonsphere.export import show

        df = pl.DataFrame({"x": [float(i) for i in range(20)], "y": [float(i) for i in range(20)]})
        chart = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q")
        assert "<svg" in cast(str, show(chart, maxRows=5, overrideMaxRows=True).data)

    def test_inherits_theme_transparent(self, simple_chart):
        # show() used to force transparent=True, so a darkmode theme previewed white-on-nothing
        # (invisible ink in a light notebook). The theme's own value must govern the preview.
        from dysonsphere.export import show

        theme(darkmode=True, transparent=False)
        assert re.search(r'<rect width="\d+" height="\d+" fill="black"', cast(str, show(simple_chart).data))

    def test_theme_transparent_true_has_no_background(self, simple_chart):
        from dysonsphere.export import show

        theme(darkmode=True, transparent=True)
        assert not re.search(r'<rect width="\d+" height="\d+" fill=', cast(str, show(simple_chart).data))

    def test_does_not_mutate_theme_options(self, simple_chart):
        # show() renders straight at the theme's values - it must set nothing to restore
        from dysonsphere.export import show

        theme(darkmode=True, transparent=False)
        before = dict(alt.theme.options)
        show(simple_chart)
        assert alt.theme.options == before

    def test_restores_transformer_on_error(self):
        # Even when the render raises (over-cap), the "default" transformer state must be
        # restored to whatever was active before.
        from dysonsphere.export import show

        df = pl.DataFrame({"x": [float(i) for i in range(20)], "y": [float(i) for i in range(20)]})
        chart = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q")
        prev = alt.data_transformers.active
        with pytest.raises(ValueError):
            show(chart, maxRows=5)
        assert alt.data_transformers.active == prev


# ── gradient legend titles ───────────────────────────────────────────────────


class TestGradientLegendTitles:
    """Gradient-legend titles stay at Vega's default (horizontal, on top)."""

    def test_save_does_not_inject_title_orient(self, tmp_path):
        df = pl.DataFrame({"x": [1.0, 2.0, 3.0], "y": [1.0, 2.0, 3.0], "v": [0.1, 0.5, 0.9]})
        chart = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q", color="v:Q")
        save(chart, str(tmp_path / "grad"), format=["svg", "json"], background="light")
        spec = json.loads((tmp_path / "grad.json").read_text(encoding="utf-8"))
        assert spec["encoding"]["color"]["legend"]["gradientLength"] == 40
        assert "titleOrient" not in spec["encoding"]["color"]["legend"]
        svg = (tmp_path / "grad.svg").read_text(encoding="utf-8")
        title = re.search(r"<text[^>]*>v</text>", svg)  # gradient legend title stays horizontal
        assert title and "rotate" not in title.group(0)

    def test_lengths_follow_actual_view_dimensions_and_direction(self):
        df = pl.DataFrame({"x": [1.0, 2.0], "y": [1.0, 2.0], "v": [0.1, 0.9]})
        vertical = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q", color="v:Q").properties(width=160, height=80)
        horizontal = vertical.encode(color=alt.Color("v:Q", legend=alt.Legend(orient="bottom")))
        v_spec = _apply_spec_fixes(vertical.to_dict())
        h_spec = _apply_spec_fixes(horizontal.to_dict())
        assert v_spec["encoding"]["color"]["legend"]["gradientLength"] == 30
        assert h_spec["encoding"]["color"]["legend"]["gradientLength"] == 160

    def test_default_vertical_allocation_includes_title(self):
        df = pl.DataFrame({"x": [1.0, 2.0], "y": [1.0, 2.0], "v": [0.1, 0.9]})
        chart = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q", color="v:Q").properties(height=180)
        spec = _apply_spec_fixes(chart.to_dict())
        assert spec["encoding"]["color"]["legend"]["gradientLength"] == 80

    def test_native_gradient_direction_precedence(self):
        df = pl.DataFrame({"x": [1.0, 2.0], "y": [1.0, 2.0], "v": [0.1, 0.9]})
        unit = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q", color="v:Q").properties(width=160, height=80)
        configured = unit.configure_legend(direction="vertical", gradientDirection="horizontal")
        spec = _apply_spec_fixes(configured.to_dict())
        assert spec["encoding"]["color"]["legend"]["gradientLength"] == 160

    @pytest.mark.parametrize(
        ("title", "expected"),
        [(None, 40), ("Override", 30), (["First", "Second"], 24)],
    )
    def test_native_legend_title_controls_reserved_space(self, title, expected):
        df = pl.DataFrame({"x": [1.0, 2.0], "y": [1.0, 2.0], "v": [0.1, 0.9]})
        chart = (
            alt.Chart(df)
            .mark_point()
            .encode(x="x:Q", y="y:Q", color=alt.Color("v:Q", title="Encoding", legend=alt.Legend(title=title)))
            .properties(width=160, height=80)
        )
        spec = _apply_spec_fixes(chart.to_dict())
        assert spec["encoding"]["color"]["legend"]["gradientLength"] == expected

    def test_configured_symbol_legend_is_not_sized_as_gradient(self):
        df = pl.DataFrame({"x": [1.0, 2.0], "y": [1.0, 2.0], "v": [0.1, 0.9]})
        chart = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q", color="v:Q")
        raw_spec = chart.to_dict()
        raw_spec["config"]["legend"]["type"] = "symbol"
        spec = _apply_spec_fixes(raw_spec)
        assert "legend" not in spec["encoding"]["color"]
        assert "gradientLength" not in spec["config"]["legend"]

    def test_factor_facets_and_explicit_overrides(self):
        theme(legendGradientLength=0.5)
        df = pl.DataFrame({"x": [1.0, 2.0], "y": [1.0, 2.0], "v": [0.1, 0.9], "g": ["a", "b"]})
        unit = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q", color="v:Q").properties(width=120, height=100)
        facet_spec = _apply_spec_fixes(unit.facet(column="g:N").to_dict())
        assert facet_spec["spec"]["encoding"]["color"]["legend"]["gradientLength"] == 40

        field = unit.encode(color=alt.Color("v:Q", legend=alt.Legend(gradientLength=37)))
        assert _apply_spec_fixes(field.to_dict())["encoding"]["color"]["legend"]["gradientLength"] == 37
        configured = unit.configure_legend(gradientLength=41)
        configured_spec = _apply_spec_fixes(configured.to_dict())
        assert configured_spec["config"]["legend"]["gradientLength"] == 41
        assert "legend" not in configured_spec["encoding"]["color"]

    def test_native_gradient_thickness_overrides_theme(self):
        df = pl.DataFrame({"x": [1.0, 2.0], "y": [1.0, 2.0], "v": [0.1, 0.9]})
        unit = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q", color="v:Q")
        field = unit.encode(color=alt.Color("v:Q", legend=alt.Legend(gradientThickness=8)))
        assert field.to_dict()["encoding"]["color"]["legend"]["gradientThickness"] == 8
        assert unit.configure_legend(gradientThickness=9).to_dict()["config"]["legend"]["gradientThickness"] == 9


# ── save() transparency ──────────────────────────────────────────────────────


class TestSaveTransparency:
    def test_svg_transparent_by_default(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "t"), format="svg", background="light")
        svg = (tmp_path / "t.svg").read_text(encoding="utf-8")
        assert 'fill="white" />' not in svg.split("<metadata")[0]  # no full-size background rect
        assert not re.search(r'<rect width="\d+" height="\d+" fill=', svg)

    def test_transparent_false_fills_white_in_light(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "w"), format="svg", background="light", transparent=False)
        svg = (tmp_path / "w.svg").read_text(encoding="utf-8")
        assert re.search(r'<rect width="\d+" height="\d+" fill="white"', svg)

    def test_transparent_false_fills_black_in_dark(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "b"), format="svg", background="dark", transparent=False)
        svg = (tmp_path / "b.svg").read_text(encoding="utf-8")
        assert re.search(r'<rect width="\d+" height="\d+" fill="black"', svg)

    def test_json_keeps_logical_background(self, simple_chart, tmp_path):
        # the JSON records the chart's logical background (theme transparent=False default
        # -> chartFill), regardless of the render-time transparent= param
        save(simple_chart, str(tmp_path / "j"), format="json", background="light", transparent=False)
        spec = json.loads((tmp_path / "j.json").read_text(encoding="utf-8"))
        assert spec.get("background") == "white"

    def test_theme_option_restored_after_save(self, simple_chart, tmp_path):
        theme(transparent=True)
        save(simple_chart, str(tmp_path / "r"), format="svg", background="light", transparent=False)
        assert alt.theme.options["transparent"] is True


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
        # The scale mapping is recovered from the rendered marks rather than assumed, so this
        # holds whatever inset viewPadding applies. Marks are the y=0 and y=7 rows of the data.
        marks = sorted(
            float(m.group(2))
            for m in re.finditer(r'aria-roledescription="point"[^>]*transform="translate\(([-\d.]+),([-\d.]+)\)"', svg)
        )
        px_hi, px_lo = marks[0], marks[-1]  # y=7 renders highest (smallest pixel), y=0 lowest
        # Whatever tick count Vega picks, each tick must land on the exact fractional scale
        # position of an integer data value - never snapped to a whole pixel.
        for y in ys:
            value = 7.0 * (px_lo - y) / (px_lo - px_hi)
            assert abs(value - round(value)) < 1e-6, f"tick {y} integer-rounded off the scale position"
        assert any(abs(y - round(y)) > 1e-9 for y in ys), "every tick landed on a whole pixel"

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
            float(m.group(1)) for m in re.finditer(r'<line transform="translate\(([\d.]+),0\)"[^/]*y2="1\.5"', svg)
        )
        majors = sorted(
            {float(m.group(1)) for m in re.finditer(r'<line transform="translate\(([\d.]+),0\)"[^/]*y2="3"', svg)}
        )
        assert len(majors) >= 2 and minors
        expected = sorted(lo + math.log10(mv) * (hi - lo) for lo, hi in zip(majors, majors[1:]) for mv in range(2, 10))
        assert minors == pytest.approx(expected, abs=1e-6)

    def test_strip_violin_hconcat_ticks_exact(self, tmp_path):
        # Capstone: strip (Case 0 band positions) beside violin (Case pi) in one hconcat -
        # every axis tick must land exactly on a band-centred mark in its own panel (the
        # strip's mean tick; the violin's boxplot box). inner="box" because this test
        # exercises the boxplot band-scale lowering; the quartiles-mode bar host's
        # band-scale alignment is covered in tests/test_marks.py.
        import numpy as np

        import dysonsphere as ds

        rng = np.random.default_rng(0)
        cats = ["a", "b", "c", "d"]
        df = pl.DataFrame({"g": [c for c in cats for _ in range(20)], "y": rng.normal(0, 1, 80).tolist()})
        theme()
        mixed = alt.hconcat(ds.mark_strip(df, "g", "y", cats), ds.mark_violin(df, "g", "y", cats, inner="box"))
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
                if ch.get("aria-roledescription") in ("box", "tick"):
                    d = ch.get("d", "")
                    # square corners: "M<x>,<y>h<w>…"; rounded (the strip's mean tick,
                    # cornerRadius): "M<x1>,<y>L<x2>,<y>C…" - centre from the top edge's ends
                    m = re.match(r"M([-\d.]+),[-\d.eE+]+h([-\d.eE+]+)", d)
                    if m:
                        boxes.append(ccx + float(m.group(1)) + float(m.group(2)) / 2)
                    else:
                        m = re.match(r"M([-\d.]+),[-\d.eE+]+L([-\d.]+),", d)
                        if m:
                            boxes.append(ccx + (float(m.group(1)) + float(m.group(2))) / 2)
                y2 = ch.get("y2")
                if ch.tag == f"{{{NS}}}line" and ch.get("x2") == "0" and y2 and 0 < abs(float(y2)) < 20:
                    if re.match(r"translate\(([-\d.]+),", ch.get("transform", "")):
                        ticks.append(ccx)
                walk(ch, ccx)

        walk(root, 0.0)
        assert boxes and ticks
        for t in ticks:
            assert min(abs(b - t) for b in boxes) < 1e-6, f"tick {t} not exactly on a box centre"


# ── _align_grid_to_content() ─────────────────────────────────────────────────


class TestAlignGridToContent:
    def test_vertical_grid_lines_shifted_up_by_axis_offset(self, tmp_path):
        # A vertical grid line (x-axis group, offset down) shifts UP by axis_offset (translate
        # only, span unchanged), so its top lands on the highest tick and its bottom lifts off
        # the detached x-axis onto the lowest tick - spanning the plot content, not the axis gap.
        lines = "".join(f'<line transform="translate({x},-100)" x1="0" y1="0" x2="0" y2="100"/>' for x in [10, 50, 90])
        svg = f'<svg xmlns="{NS}"><g class="mark-rule role-axis-grid">{lines}</g></svg>'
        root = ET.fromstring(svg)
        _align_grid_to_content(root, 3)
        for line in root.iter(f"{{{NS}}}line"):
            m = re.match(r"translate\(([\d.]+),(-?[\d.]+)\)", line.get("transform", ""))
            assert m and float(m.group(2)) == pytest.approx(-103.0, abs=0.001)  # up by axis_offset
            assert float(line.get("y2", "0")) == pytest.approx(100.0, abs=0.001)  # span unchanged

    def test_horizontal_grid_lines_shifted_right_by_axis_offset(self, tmp_path):
        # A horizontal grid line (y-axis group, offset left) shifts RIGHT by axis_offset (translate
        # only, span unchanged), so it floats off the detached y-axis and reaches the content's
        # right edge - the mirror of the vertical case, so both grid directions span the content.
        svg = (
            f'<svg xmlns="{NS}"><g class="mark-rule role-axis-grid">'
            '<line transform="translate(0,40)" x1="0" y1="0" x2="100" y2="0"/>'
            "</g></svg>"
        )
        root = ET.fromstring(svg)
        _align_grid_to_content(root, 3)
        line = next(root.iter(f"{{{NS}}}line"))
        assert line.get("transform") == "translate(3.0,40.0)"  # right by axis_offset
        assert line.get("x2") == "100"  # span unchanged
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
        root = ET.fromstring(svg)
        _flip_ticks_inward(root)
        lines = list(root.iter(f"{{{NS}}}line"))
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
        root = ET.fromstring(svg)
        _flip_ticks_inward(root)
        assert next(root.iter(f"{{{NS}}}line")).get("y2") == "100"

    def test_save_with_inward_ticks_points_ticks_in(self, tmp_path):
        theme(tickDirection="in")
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

    def test_labels_and_title_pulled_in_by_tick_length(self):
        # The gap the outward tick occupied must not survive the flip: labels + title shift
        # toward the view by the axis's own tick vector, each text's translate rewritten
        # (a group transform would be dropped by _simplify_svg). Rotation tails preserved.
        svg = (
            f'<svg xmlns="{NS}">'
            '<g class="mark-group role-axis"><g><g>'
            '<g class="mark-rule role-axis-tick">'
            '<line transform="translate(10,0)" x1="0" y1="0" x2="0" y2="3"/>'
            "</g>"
            '<g class="mark-text role-axis-label">'
            '<text transform="translate(10,11)">0</text>'
            '<text transform="translate(50,2) rotate(315) translate(0,6)">5</text>'
            "</g>"
            '<g class="mark-text role-axis-title">'
            '<text transform="translate(50,20)">x</text>'
            "</g>"
            "</g></g></g></svg>"
        )
        root = ET.fromstring(svg)
        _flip_ticks_inward(root)
        texts = list(root.iter(f"{{{NS}}}text"))
        assert texts[0].get("transform") == "translate(10,8)"  # up by the 3px tick
        assert texts[1].get("transform") == "translate(50,-1) rotate(315) translate(0,6)"
        assert texts[2].get("transform") == "translate(50,17)"  # title follows the labels

    def test_axis_without_ticks_leaves_labels_alone(self):
        svg = (
            f'<svg xmlns="{NS}">'
            '<g class="mark-group role-axis"><g>'
            '<g class="mark-text role-axis-label">'
            '<text transform="translate(10,11)">0</text>'
            "</g>"
            "</g></g></svg>"
        )
        root = ET.fromstring(svg)
        _flip_ticks_inward(root)
        assert next(root.iter(f"{{{NS}}}text")).get("transform") == "translate(10,11)"

    def test_save_with_inward_ticks_pulls_labels_in(self, tmp_path):
        # Rendered end-to-end: x-axis labels sit tickSize closer to the domain than the
        # outward-tick render of the same chart.
        df = pl.DataFrame({"x": [1.0, 2.0, 3.0], "y": [1.0, 2.0, 3.0]})
        chart = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q")

        def x_label_y(path):
            root = ET.parse(path).getroot()
            for text in root.iter(f"{{{NS}}}text"):
                m = re.match(r"translate\([\d.]+,([\d.]+)\)$", text.get("transform", ""))
                if m and text.get("text-anchor") == "middle":
                    return float(m.group(1))
            raise AssertionError("no x-axis label found")

        theme(tickDirection="in", closed=True)
        save(chart, str(tmp_path / "inward"), format=["svg"], background=["light"])
        theme(tickDirection="out", closed=True)
        save(chart, str(tmp_path / "outward"), format=["svg"], background=["light"])
        tick_size = alt.theme.options["tickSize"]
        assert x_label_y(str(tmp_path / "inward.svg")) == pytest.approx(
            x_label_y(str(tmp_path / "outward.svg")) - tick_size
        )


# ── _layer_axes_below_marks() ────────────────────────────────────────────────


class TestLayerAxesBelowMarks:
    def test_axis_placed_after_grid_before_marks(self, tmp_path):
        # A datum plotted exactly on an axis renders OVER the axis line - data wins
        # over chrome - while axis chrome still covers the grid.
        svg = textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <g class="mark-group role-axis" id="axis">
                <g><line x1="0" y1="0" x2="10" y2="0"/></g>
              </g>
              <g class="mark-group role-axis" id="grid">
                <g><g class="mark-rule role-axis-grid">
                  <line x1="0" y1="0" x2="100" y2="0"/>
                </g></g>
              </g>
              <g class="data-layer"/>
            </svg>
        """)
        root = ET.fromstring(svg)
        _layer_axes_below_marks(root)
        ids = [c.get("id") or c.get("class") for c in root]
        assert ids == ["grid", "axis", "data-layer"]

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
        root = ET.fromstring(svg)
        _layer_axes_below_marks(root)
        children = list(root)
        assert children[0].get("class") == "mark-group role-axis"
        assert children[-1].get("class") == "data-layer"

    def test_background_fill_and_stroke_split(self, tmp_path):
        # viewFill + closed: fill stays at the very back, stroke clone sits above
        # the grid but BELOW the data marks.
        svg = textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <path class="background" fill="#eeeeee" stroke="black"/>
              <g class="mark-group role-axis" id="grid">
                <g><g class="mark-rule role-axis-grid">
                  <line x1="0" y1="0" x2="100" y2="0"/>
                </g></g>
              </g>
              <g class="data-layer"/>
            </svg>
        """)
        root = ET.fromstring(svg)
        _layer_axes_below_marks(root)
        children = list(root)
        assert children[0].get("class") == "background"
        assert children[0].get("stroke") == "none"  # original → fill-only, stays back
        assert children[1].get("id") == "grid"
        assert children[2].get("fill") == "none"  # stroke-only clone above grid
        assert children[2].get("stroke") == "black"
        assert children[-1].get("class") == "data-layer"  # marks render last


# ── scaffolding marks vs real data marks ─────────────────────────────────────


class TestScaffoldingMarks:
    def test_log_ticks_emit_no_scaffolding_marks(self, tmp_path):
        # add_log_ticks hosts its minor-tick axis on a layer filtered to zero rows, so the SVG
        # carries NO axis-host point marks (the old bug: a column of ~n transparent circles), while
        # the minor-tick <line> elements still render and read(what="data") sees one user frame.
        import dysonsphere as ds

        df = pl.DataFrame({"x": list(range(20)), "y": [1.5**i for i in range(20)]})
        line = (
            alt.Chart(df)
            .mark_line()
            .encode(
                x="x:Q", y=alt.Y("y:Q", scale=alt.Scale(type="log"), axis=alt.Axis(values=[1, 10, 100, 1000, 10000]))
            )
        )
        chart = ds.add_log_ticks(line, df, "y", axis="y")
        save(chart, str(tmp_path / "out"), format=["svg", "json"], background="light")
        svg = (tmp_path / "out.svg").read_text(encoding="utf-8")
        assert 'opacity="0"' not in svg  # no scaffolding marks leaked
        assert "<line" in svg  # minor ticks still drawn
        assert ds.metadata.read(str(tmp_path / "out.json"), what="data").shape == (20, 2)  # one user frame, intact

    def test_transparent_data_marks_are_preserved(self, tmp_path):
        # The crux of the fix: a user's own opacity-encoded (fully transparent) DATA marks must
        # survive to the SVG - the export must stay a complete rendering of the data (provenance).
        # A blanket opacity="0" strip would have wrongly deleted these.
        df = pl.DataFrame({"x": [0.0, 1.0, 2.0], "y": [1.0, 2.0, 3.0]})
        chart = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q", opacity=alt.value(0.0))
        save(chart, str(tmp_path / "out"), format="svg", background="light")
        svg = (tmp_path / "out.svg").read_text(encoding="utf-8")
        # all three transparent points are still present as marks
        assert svg.count('aria-roledescription="point"') == 3


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
        root = ET.fromstring(svg)
        _simplify_svg(root)
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
        root = ET.fromstring(svg)
        _simplify_svg(root)
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
        root = ET.fromstring(svg)
        _simplify_svg(root)
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
        root = ET.fromstring(svg)
        _simplify_svg(root)
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
        root = ET.fromstring(svg)
        _simplify_svg(root)
        assert root.find(f"{{{NS}}}g") is None
        assert root.find(f"{{{NS}}}rect") is not None


class TestFixSuperscriptLabels:
    def _svg_with_text(self, content: str) -> str:
        return textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <text>{content}</text>
            </svg>
        """)

    def test_scientific_two_digit_exponent(self):
        # ¹ (U+00B9, Latin-1) mixed with ⁴ (U+2074, Superscripts block) — the misalignment case
        root = ET.fromstring(self._svg_with_text("P = 1.94×10⁻¹⁴"))
        _fix_superscript_labels(root)
        text_el = root.find(f"{{{NS}}}text")
        assert text_el is not None
        assert text_el.text == "P = 1.94×10"
        tspan = text_el.find(f"{{{NS}}}tspan")
        assert tspan is not None
        # no font-size on the <text>, so the exponent scales to the theme fontSize (6): 6*2/3, -6*5/12
        assert tspan.get("dy") == "-2.5"
        assert tspan.get("font-size") == "4"
        assert tspan.text == "−14"

    def test_power_notation_single_digit(self):
        root = ET.fromstring(self._svg_with_text("P ≈ 10⁻⁵"))
        _fix_superscript_labels(root)
        text_el = root.find(f"{{{NS}}}text")
        assert text_el is not None
        tspan = text_el.find(f"{{{NS}}}tspan")
        assert tspan is not None
        assert tspan.text == "−5"

    def test_bare_log_axis_label(self):
        # The bug: log_label_expr emits bare 10ⁿ (no ×/≈), and the U+2070 zero gets font-
        # substituted and rendered slanted unless re-typeset. Base "10" stays; exponent -> ASCII.
        # (Letter+superscript like r² is left alone - the pattern requires a digit base.)
        root = ET.fromstring(self._svg_with_text("10⁰"))
        _fix_superscript_labels(root)
        text_el = root.find(f"{{{NS}}}text")
        assert text_el is not None
        assert text_el.text == "10"
        tspan = text_el.find(f"{{{NS}}}tspan")
        assert tspan is not None
        assert tspan.text == "0"

    def test_fixer_typesets_every_generator_superscript(self):
        # Guard against reopening the log-label bug: the SINGLE fixer must convert EVERY Unicode
        # superscript that ANY generator emits (p-value labels, log-axis labels, table columns -
        # all funnel through utils._SUP / stats._superscript), so no fragile glyph survives
        # into the font-rendered SVG. If a future generator emits a superscript form the fixer's
        # pattern misses, a fragile char is left in the text and this fails.
        from dysonsphere.stats import _format_pvalue, _superscript
        from dysonsphere.utils import _SUP

        labels = [
            _format_pvalue(1e-5, notation="power"),  # p-value: P ≈ 10⁻⁵
            _format_pvalue(1.23e-5, notation="scientific"),  # p-value: ... ×10⁻⁵
            *[f"10{_superscript(i)}" for i in range(13)],  # log-axis 10⁰..10¹² (0/4-9 + two-digit)
            f"2{_superscript(20)}",  # log-axis, non-base-10: 2²⁰
        ]
        fragile = set(_SUP) | {"⁻"}
        for lab in labels:
            root = ET.fromstring(self._svg_with_text(lab))
            _fix_superscript_labels(root)
            text_el = root.find(f"{{{NS}}}text")
            assert text_el is not None
            rendered = "".join(text_el.itertext())  # base + ascii exponent + tail
            leftover = fragile & set(rendered)
            assert not leftover, f"unfixed superscript {leftover} left in {lab!r} -> {rendered!r}"

    def test_no_match_leaves_tree_unchanged(self):
        root = ET.fromstring(self._svg_with_text("P = 0.023"))
        _fix_superscript_labels(root)
        text_el = root.find(f"{{{NS}}}text")
        assert text_el is not None
        assert text_el.text == "P = 0.023"  # untouched
        assert text_el.find(f"{{{NS}}}tspan") is None  # nothing injected

    def test_aria_label_attribute_not_modified(self, tmp_path):
        # Vega adds aria-label attributes with the same text — must not inject <tspan> there
        svg = textwrap.dedent(f"""\
            <svg xmlns="{NS}">
              <text aria-label="P = 1.94×10⁻¹⁴">P = 1.94×10⁻¹⁴</text>
            </svg>
        """)
        root = ET.fromstring(svg)
        _fix_superscript_labels(root)
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
        root = ET.fromstring(svg)
        _fix_superscript_labels(root)
        outer_tspan = root.find(f".//{{{NS}}}tspan[@dy='0']")
        assert outer_tspan is not None
        assert outer_tspan.text == "P = 3.03×10"
        inner_tspan = outer_tspan.find(f"{{{NS}}}tspan")
        assert inner_tspan is not None
        assert inner_tspan.text == "−14"

    def test_caret_superscript_token(self):
        # `^` author token: q^2 -> q + raised "2" (superscript mirror of the __ subscript token).
        root = ET.fromstring(self._svg_with_text("q^2"))
        _fix_superscript_labels(root)
        text_el = root.find(f"{{{NS}}}text")
        assert text_el is not None
        assert text_el.text == "q"  # the caret is dropped
        tspan = text_el.find(f"{{{NS}}}tspan")
        assert tspan is not None
        assert tspan.text == "2"
        assert tspan.get("dy", "").startswith("-")  # raised


class TestFixSubscriptLabels:
    def _svg_with_text(self, content: str, fs: str | None = None) -> str:
        attr = f' font-size="{fs}"' if fs else ""
        return f'<svg xmlns="{NS}"><text{attr}>{content}</text></svg>'

    def _one_tspan(self, content: str):
        root = ET.fromstring(self._svg_with_text(content))
        _fix_subscript_labels(root)
        text_el = root.find(f"{{{NS}}}text")
        assert text_el is not None
        return text_el

    def test_dunder_token(self):
        # q__x -> q + LOWERED "x"; the double underscore is dropped.
        text_el = self._one_tspan("q__x")
        assert text_el.text == "q"
        tspan = text_el.find(f"{{{NS}}}tspan")
        assert tspan is not None
        assert tspan.text == "x"
        assert not tspan.get("dy", "").startswith("-")  # lowered (positive dy)

    def test_literal_unicode_subscript(self):
        # A hand-typed Unicode subscript (t₀) is lowered to ASCII too, dodging font substitution.
        text_el = self._one_tspan("t₀")
        assert text_el.text == "t"
        tspan = text_el.find(f"{{{NS}}}tspan")
        assert tspan is not None
        assert tspan.text == "0"

    def test_column_names_untouched(self):
        # The crux: a default axis title equal to a column name must NOT be subscripted. Neither
        # single-underscore snake_case NOR double-underscore sklearn-style names (whose base is
        # mid-word) trip the boundary-guarded `__` token - only a deliberate q__x does.
        for name in ("x_1", "q_x", "t_0", "flipper_length_mm", "p_value", "T_max", "model__alpha", "param__C"):
            text_el = self._one_tspan(name)
            assert text_el.text == name  # unchanged
            assert text_el.find(f"{{{NS}}}tspan") is None

    def test_multiple_and_mixed_scripts_in_one_label(self):
        # One pass handles several tokens AND both directions: q__x = 10^3 -> lowered x, raised 3.
        root = ET.fromstring(self._svg_with_text("q__x = 10^3"))
        _typeset_scripts(root)
        text_el = root.find(f"{{{NS}}}text")
        assert text_el is not None
        assert text_el.text == "q"
        tspans = text_el.findall(f"{{{NS}}}tspan")
        assert [t.text for t in tspans] == ["x", "3"]
        assert not tspans[0].get("dy", "").startswith("-")  # x lowered
        assert tspans[1].get("dy", "").startswith("-")  # 3 raised
        assert "".join(text_el.itertext()) == "qx = 103"  # reading order preserved, connectors gone


class TestItalicizeStatSymbols:
    def _root_with_text(self, content: str) -> ET.Element:
        escaped = content.replace("&", "&amp;").replace("<", "&lt;")
        return ET.fromstring(f'<svg xmlns="{NS}"><text>{escaped}</text></svg>')

    def _italic_runs(self, root: ET.Element) -> list[str]:
        return [t.text or "" for t in root.iter(f"{{{NS}}}tspan") if t.get("font-style") == "italic"]

    def _flat_text(self, el: ET.Element) -> str:
        return "".join(el.itertext())  # text + descendant text/tails, in document order

    def test_pvalue_forms(self):
        for label in ("P = 0.012", "P < 0.001", "P ≈ 0.05"):
            root = self._root_with_text(label)
            _italicize_stat_symbols(root)
            assert self._italic_runs(root) == ["P"], label
            text_el = root.find(f"{{{NS}}}text")
            assert text_el is not None
            assert self._flat_text(text_el) == label  # content preserved, only markup added

    def test_pvalue_word_forms(self):
        # The "p" in "p-value" / "P-value" / "p value" is italic by convention; "power" is not.
        for label, expect in (
            ("adj. p-value", ["p"]),
            ("P-value", ["P"]),
            ("uncorrected p value", ["p"]),
            ("power output", []),
        ):
            root = self._root_with_text(label)
            _italicize_stat_symbols(root)
            assert self._italic_runs(root) == expect, label
            text_el = root.find(f"{{{NS}}}text")
            assert text_el is not None
            assert self._flat_text(text_el) == label

    def test_verbose_omnibus_latin_italic_greek_upright(self):
        root = self._root_with_text("ANOVA F(2, 57) = 6.34, P = 0.003, η² = 0.18")
        _italicize_stat_symbols(root)
        assert self._italic_runs(root) == ["F", "P"]  # η² stays upright

    def test_kruskal_and_alexander_govern_statistics(self):
        root = self._root_with_text("Kruskal-Wallis H(2) = 8.11, P = 0.017, ε² = 0.21")
        _italicize_stat_symbols(root)
        assert self._italic_runs(root) == ["H", "P"]
        root = self._root_with_text("Alexander-Govern A(2) = 9.02, P = 0.011, η² = 0.20")
        _italicize_stat_symbols(root)
        assert self._italic_runs(root) == ["A", "P"]

    def test_friedman_kendalls_w(self):
        root = self._root_with_text("Friedman χ²(2) = 7.60, P = 0.022, W = 0.42")
        _italicize_stat_symbols(root)
        assert self._italic_runs(root) == ["P", "W"]  # left-to-right; χ² stays upright

    def test_correlation_readout(self):
        root = self._root_with_text("r = 0.904, r² = 0.818, P < 0.001, y = 0.791x - 0.0342")
        _italicize_stat_symbols(root)
        assert self._italic_runs(root) == ["r", "r", "P", "y", "x"]
        text_el = root.find(f"{{{NS}}}text")
        assert text_el is not None
        # the ² digit stays upright (outside the italic tspan)
        assert "² = 0.818" in self._flat_text(text_el)

    def test_sample_size_row_label(self):
        root = self._root_with_text("n =")
        _italicize_stat_symbols(root)
        assert self._italic_runs(root) == ["n"]

    def test_test_name_labels(self):
        root = self._root_with_text("Mann-Whitney U")
        _italicize_stat_symbols(root)
        assert self._italic_runs(root) == ["U"]
        root = self._root_with_text("Student's t-test")
        _italicize_stat_symbols(root)
        assert self._italic_runs(root) == ["t"]

    def test_ns_label_stays_upright(self):
        # "ns" is an abbreviation (not significant), not a symbol - multi-letter
        # abbreviations stay upright
        for label in ("ns", "delay of 10 ns"):
            root = self._root_with_text(label)
            _italicize_stat_symbols(root)
            text_el = root.find(f"{{{NS}}}text")
            assert text_el is not None
            assert text_el.get("font-style") is None, label
            assert self._italic_runs(root) == [], label

    def test_letter_context_guards(self):
        # symbols embedded in words never match
        for label in ("power = 5", "mean = 3", "sharpen = true", "PP = 1", "2x faster"):
            root = self._root_with_text(label)
            _italicize_stat_symbols(root)
            assert self._italic_runs(root) == [], label

    def test_asterisk_labels_untouched(self):
        for label in ("*", "**", "***"):
            root = self._root_with_text(label)
            _italicize_stat_symbols(root)
            assert self._italic_runs(root) == [], label

    def test_after_superscript_fixer(self):
        # pipeline order: superscript fixer splits the exponent out first; the P (still in
        # .text) and any symbols in the exponent tspan's TAIL must still be found
        root = self._root_with_text("r = 0.9, P = 3.03×10⁻¹⁴, y = 0.8x + 0.2")
        _fix_superscript_labels(root)
        _italicize_stat_symbols(root)
        assert self._italic_runs(root) == ["r", "P", "y", "x"]
        text_el = root.find(f"{{{NS}}}text")
        assert text_el is not None
        # exponent tspan still present with its styling (raised via a negative dy)
        exp = [t for t in text_el.iter(f"{{{NS}}}tspan") if (t.get("dy") or "").startswith("-")]
        assert len(exp) == 1 and exp[0].text == "−14"
        # document order preserved: exponent sits between the P and y italic runs
        kinds = [(t.get("font-style"), t.text) for t in text_el.iter(f"{{{NS}}}tspan")]
        assert kinds == [("italic", "r"), ("italic", "P"), (None, "−14"), ("italic", "y"), ("italic", "x")]

    def test_vega_outer_tspan_wrapper(self):
        # Vega sometimes wraps a whole label in an outer <tspan>
        root = ET.fromstring(f'<svg xmlns="{NS}"><text><tspan dy="0">P = 0.012</tspan></text></svg>')
        _italicize_stat_symbols(root)
        assert self._italic_runs(root) == ["P"]
        outer = root.find(f".//{{{NS}}}tspan[@dy='0']")
        assert outer is not None
        inner = outer.find(f"{{{NS}}}tspan")
        assert inner is not None and inner.text == "P"

    def test_aria_label_attribute_not_modified(self):
        root = ET.fromstring(f'<svg xmlns="{NS}"><text aria-label="P = 0.012">P = 0.012</text></svg>')
        _italicize_stat_symbols(root)
        text_el = root.find(f"{{{NS}}}text")
        assert text_el is not None
        assert text_el.get("aria-label") == "P = 0.012"
        assert self._italic_runs(root) == ["P"]

    def test_rendered_chart_has_italic_symbols(self, tmp_path):
        # end-to-end through save(): bracket P and the n= multilabel row both italicized
        import dysonsphere as ds

        df = pl.DataFrame(
            {
                "g": ["a"] * 6 + ["b"] * 6,
                "y": [1.0, 2.0, 3.0, 2.5, 1.5, 2.2, 4.0, 5.0, 4.5, 5.5, 4.8, 5.2],
            }
        )
        chart = ds.mark_strip(df, "g", "y", ["a", "b"]) + ds.stats.comparisons(
            df, "g", "y", pairs=[("a", "b")], test="mannwhitneyu"
        )
        save(chart, str(tmp_path / "italic"), format="svg", background=["light"])
        svg = (tmp_path / "italic.svg").read_text(encoding="utf-8")
        assert '<tspan font-style="italic">P</tspan>' in svg


class TestFixFontForIllustrator:
    THEME_STACK = "Helvetica Neue, HelveticaNeue, Helvetica, Arial, sans-serif"
    FIXED = "HelveticaNeue, Arial, sans-serif"

    def test_default_stack_uses_postscript_primary_keeps_fallbacks(self):
        # Illustrator aliases the spaced "Helvetica Neue" (and its "Helvetica" prefix) to plain
        # Helvetica; the despaced PostScript name resolves. Keep Arial/sans-serif for non-mac.
        assert _illustrator_font_family(self.THEME_STACK) == self.FIXED

    def test_prefix_alias_dropped_genuine_fallbacks_kept(self):
        # "Helvetica" (a prefix of the primary) is the trap and is dropped; Arial/sans-serif stay.
        out = _illustrator_font_family(self.THEME_STACK)
        assert "Helvetica," not in out and " Helvetica " not in out  # the bare-Helvetica trap is gone
        assert out.endswith("Arial, sans-serif")

    def test_single_family_without_despaced_fallback_kept(self):
        # A single spaced family with no PostScript fallback resolves fine in Illustrator as-is;
        # its genuinely-different fallbacks are preserved.
        assert _illustrator_font_family("Courier New") == "Courier New"
        assert _illustrator_font_family("Courier New, monospace") == "Courier New, monospace"

    def test_single_word_family_unchanged(self):
        assert _illustrator_font_family("Arial") == "Arial"
        assert _illustrator_font_family("Arial, sans-serif") == "Arial, sans-serif"

    def test_quotes_and_whitespace_tolerated(self):
        assert _illustrator_font_family(" 'Helvetica Neue' , HelveticaNeue , Helvetica ") == "HelveticaNeue"

    def test_generic_only_unchanged(self):
        assert _illustrator_font_family("sans-serif") == "sans-serif"

    def test_fixer_rewrites_every_font_family_in_tree(self):
        svg = (
            f'<svg xmlns="{NS}">'
            f'<text font-family="{self.THEME_STACK}">a<tspan font-style="italic">P</tspan></text>'
            f'<text font-family="{self.THEME_STACK}">b</text></svg>'
        )
        root = ET.fromstring(svg)
        _fix_font_for_illustrator(root)
        families = {t.get("font-family") for t in root.iter(f"{{{NS}}}text")}
        assert families == {self.FIXED}
        # italic tspan inherits the parent family (no own font-family), so it stays but resolves
        tspan = root.find(f".//{{{NS}}}tspan")
        assert tspan is not None and tspan.get("font-family") is None and tspan.get("font-style") == "italic"

    def test_save_svg_uses_postscript_primary_theme_option_unchanged(self, tmp_path, simple_chart):
        out = str(tmp_path / "fig")
        save(simple_chart, out, format="svg", background="light")
        svg = (tmp_path / "fig.svg").read_text(encoding="utf-8")
        families = set(re.findall(r'font-family="([^"]*)"', svg))
        assert families == {self.FIXED}, families
        # the SVG-only fix must NOT mutate the theme option (HTML/JSON keep the full stack)
        assert alt.theme.options["font"] == self.THEME_STACK


class TestShadeBehindAxes:
    """shade draws a background - it must never paint over the axes or the frame."""

    def _chart(self, closed):
        cats = ["a", "b", "c", "d"]
        df = pl.DataFrame({"g": cats, "v": [5.0, 6.0, 4.0, 7.0]})
        theme(closed=closed, width=200, height=200)
        import dysonsphere as ds

        return ds.shade(categories=cats) + alt.Chart(df).mark_bar().encode(
            alt.X("g:N", title="g"), alt.Y("v:Q", title="v")
        )

    def _paint_order(self, path):
        """Classify every painted path in document order."""
        xml = path.read_text().split("?>", 1)[-1]
        seq = []
        for el in ET.fromstring(xml).iter(f"{{{NS}}}path"):
            d = el.get("d") or ""
            stroke, fill = el.get("stroke"), el.get("fill")
            if not d:
                continue
            if stroke in (None, "none") and fill in ("#F1F1F1", "#DBDBDB") and "h200" not in d:
                seq.append("shade")
            elif stroke not in (None, "none") and d.startswith("M0,0h200v200"):
                seq.append("border")
        return seq

    def test_border_paints_after_the_shade(self, tmp_path):
        save(self._chart(True), str(tmp_path / "fig"), format="svg", background="light")
        order = self._paint_order(tmp_path / "fig.svg")
        assert "border" in order, order
        assert order.index("border") > max(i for i, v in enumerate(order) if v == "shade"), order

    def test_no_shade_leaves_the_tree_alone(self):
        """The border relocation must be inert on charts with no shade."""
        svg = (
            f'<svg xmlns="{NS}"><g>'
            f'<path class="background" stroke="black" d="M0,0h10v10h-10Z"/>'
            f'<g><g class="mark-rect role-mark other_marks"/></g>'
            "</g></svg>"
        )
        root = ET.fromstring(svg)
        before = ET.tostring(root)
        _sink_border_below_shade(root)
        assert ET.tostring(root) == before

    def test_transform_between_border_and_shade_blocks_the_move(self):
        """Moving the border across a transform would displace it - leave it where it is."""
        svg = (
            f'<svg xmlns="{NS}"><g>'
            f'<path class="background" stroke="black" d="M0,0h10v10h-10Z"/>'
            f'<g transform="translate(5,5)"><g class="mark-rect role-mark __dsshade_1_marks"/></g>'
            "</g></svg>"
        )
        root = ET.fromstring(svg)
        _sink_border_below_shade(root)
        outer = root[0]
        assert outer[0].get("class") == "background", "border should not have moved"


class TestSuppressNice:
    """viewPadding lands exactly only if Vega does not re-nice the padded domain."""

    def _chart(self):
        df = pl.DataFrame({"x": [0.0, 1.0], "y": [0.0, 8.343]})
        return alt.Chart(df).mark_point().encode(alt.X("x:Q", title="x"), alt.Y("y:Q", title="y"))

    def test_sets_nice_false_on_continuous_position_scales(self):
        spec: dict[str, Any] = {"encoding": {"x": {"type": "quantitative"}, "y": {"type": "quantitative"}}}
        enc: Any = _suppress_nice(spec)["encoding"]
        assert enc["x"]["scale"]["nice"] is False
        assert enc["y"]["scale"]["nice"] is False

    def test_leaves_explicit_user_nice_alone(self):
        spec: dict[str, Any] = {"encoding": {"y": {"type": "quantitative", "scale": {"nice": True}}}}
        _suppress_nice(spec)
        assert spec["encoding"]["y"]["scale"]["nice"] is True

    def test_skips_non_continuous_channels(self):
        spec: dict[str, Any] = {"encoding": {"x": {"type": "nominal"}, "y": {"type": "ordinal"}}}
        _suppress_nice(spec)
        assert "scale" not in spec["encoding"]["x"]
        assert "scale" not in spec["encoding"]["y"]

    def test_recurses_into_every_container(self):
        def leaf() -> dict[str, Any]:
            return {"encoding": {"y": {"type": "quantitative"}}}

        spec: dict[str, Any] = {
            "layer": [leaf()],
            "hconcat": [leaf()],
            "vconcat": [leaf()],
            "concat": [leaf()],
            "spec": leaf(),
        }
        _suppress_nice(spec)
        for key in ("layer", "hconcat", "vconcat", "concat"):
            assert spec[key][0]["encoding"]["y"]["scale"]["nice"] is False
        assert spec["spec"]["encoding"]["y"]["scale"]["nice"] is False

    def test_gate_follows_emitted_padding_not_closed(self):
        theme(closed=True)
        assert _apply_spec_fixes(self._chart().to_dict())["encoding"]["y"]["scale"]["nice"] is False
        theme()  # open, but padded by default - the gate follows the padding, not `closed`
        assert _apply_spec_fixes(self._chart().to_dict())["encoding"]["y"]["scale"]["nice"] is False
        theme(viewPadding=False)  # no padding emitted, so nothing to correct
        assert "scale" not in _apply_spec_fixes(self._chart().to_dict())["encoding"]["y"]

    def test_gate_fires_for_padded_open_plots(self):
        """Padding is what nice conflicts with; the gate must not be tied to `closed`."""
        theme(axisOffset=0)  # open, but padded (a config theme.py may emit in future)
        spec = self._chart().to_dict()
        spec["config"].setdefault("scale", {})["continuousPadding"] = 5
        assert _apply_spec_fixes(spec)["encoding"]["y"]["scale"]["nice"] is False

    def test_gate_respects_view_padding_off(self):
        theme(closed=True, viewPadding=False)
        assert "scale" not in _apply_spec_fixes(self._chart().to_dict())["encoding"]["y"]

    def test_svg_and_json_agree(self, tmp_path):
        """The two spec resolutions in save() must not drift apart."""
        theme(closed=True, width=300, height=300)
        save(self._chart(), str(tmp_path / "fig"), format=["svg", "json"], background="light")
        spec = json.loads((tmp_path / "fig.json").read_text())
        assert spec["encoding"]["y"]["scale"]["nice"] is False
        labels = re.findall(r"<text[^>]*>([^<]*)</text>", (tmp_path / "fig.svg").read_text())
        ticks = [t for t in labels if re.fullmatch(r"[\u2212-]?[\d.]+", t)]
        assert not any(t.startswith("\u2212") for t in ticks[ticks.index("0") :]), ticks

    def test_removes_negative_tick_on_non_negative_data(self, tmp_path):
        """A padded, niced domain invents a -1 tick under data that never goes below zero."""
        theme(closed=True, width=300, height=300)
        save(self._chart(), str(tmp_path / "fig"), format="svg", background="light")
        labels = re.findall(r"<text[^>]*>([^<]*)</text>", (tmp_path / "fig.svg").read_text())
        assert "\u22121" not in labels
