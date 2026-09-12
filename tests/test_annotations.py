import math
import re

import altair as alt
import polars as pl
import pytest

from dysonsphere.annotations import (
    _EDGE_OFFSET,
    _default_flush,
    _rule_label_geometry,
    _rule_mark_kwargs,
    labels,
    rule,
    shade,
    text,
)
from dysonsphere.theme import theme


def _text_values(spec):
    """All text-mark strings in a chart spec (labels encodes text via alt.value)."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            t = node.get("encoding", {}).get("text")
            if isinstance(t, dict) and "value" in t:
                found.append(t["value"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(spec)
    return found


class TestLabels:
    @pytest.fixture
    def df(self):
        return pl.DataFrame({"x": [1.0, 2.0, 3.0], "y": [1.0, 2.0, 3.0], "g": ["a", "b", "c"]})

    def test_returns_layerchart(self, df):
        assert isinstance(labels(df, "x", "y", "g"), alt.LayerChart)

    def test_layer_count_with_leaders(self, df):
        # (connector + text) per label, nothing else - the scale pin rides on the first label layer,
        # no invisible sidecar mark (alwaysShowConnectors so no short-connector is dropped, making
        # the count deterministic)
        chart = labels(df, "x", "y", "g", alwaysShowConnectors=True)
        assert len(chart.to_dict()["layer"]) == 3 * 2

    def test_no_connector(self, df):
        # 1 text per label, no pin layer
        assert len(labels(df, "x", "y", "g", connector=False).to_dict()["layer"]) == 3

    @pytest.mark.parametrize("coordinate", ["x", "y"])
    @pytest.mark.parametrize("value", [float("nan"), None, float("inf"), float("-inf")])
    def test_coordinates_are_validated_before_subset(self, coordinate, value):
        values = {"x": [1.0, 2.0, 3.0], "y": [1.0, 2.0, 3.0]}
        values[coordinate][2] = value
        data = pl.DataFrame({**values, "g": ["a", "b", "c"], "unused": [float("inf")] * 3})
        with pytest.raises(ValueError, match=f"label coordinate '{coordinate}'"):
            labels(data, "x", "y", "g", subset=["a"])

    def test_unused_columns_are_not_validated(self, df):
        data = df.with_columns(pl.lit(float("inf")).alias("unused"))
        assert isinstance(labels(data, "x", "y", "g", subset=["a"]), alt.LayerChart)

    @staticmethod
    def _text_marks(chart):
        return [lyr["mark"] for lyr in chart.to_dict()["layer"] if lyr["mark"]["type"] == "text"]

    def test_font_style_default_absent(self, df):
        marks = self._text_marks(labels(df, "x", "y", "g"))
        assert marks and all("fontStyle" not in m for m in marks)

    def test_font_style_italic_applied(self, df):
        marks = self._text_marks(labels(df, "x", "y", "g", fontStyle="italic"))
        assert marks and all(m["fontStyle"] == "italic" for m in marks)

    @staticmethod
    def _rects(chart):
        return [lyr["mark"] for lyr in chart.to_dict()["layer"] if lyr["mark"]["type"] == "rect"]

    def test_fill_false_no_rects(self, df):
        # the chip is gated on fill: default (fill=False) draws no rect even though stroke defaults True
        assert not self._rects(labels(df, "x", "y", "g"))

    def test_fill_true_rect_per_label(self, df):
        from dysonsphere.palettes import colors

        rects = self._rects(labels(df, "x", "y", "g", fill=True, connector=False))
        assert len(rects) == 3 and all(r["fill"] == colors["greys"][0] for r in rects)  # light default

    def test_fill_darkmode_uses_greys11(self, df):
        from dysonsphere.palettes import colors

        theme(dark=True)
        rects = self._rects(labels(df, "x", "y", "g", fill=True, connector=False))
        assert rects and all(r["fill"] == colors["greys"][11] for r in rects)

    def test_fill_true_default_stroke_borders_the_chip(self, df):
        # stroke defaults True, so a fill chip gets a darkmode-aware border
        rects = self._rects(labels(df, "x", "y", "g", fill=True, connector=False))
        assert rects and all(r["stroke"] == "black" for r in rects)

    def test_stroke_false_pins_off_config_rect_border(self, df):
        # the theme styles config.rect with a black stroke; stroke=False must pin it off, not leak it
        rects = self._rects(labels(df, "x", "y", "g", fill=True, stroke=False, connector=False))
        assert rects and all(r["stroke"] is None and r["strokeWidth"] == 0 for r in rects)

    def test_corner_radius_bool_and_float(self, df):
        rounded = self._rects(labels(df, "x", "y", "g", fill=True, fontSize=8, connector=False))
        square = self._rects(labels(df, "x", "y", "g", fill=True, cornerRadius=False, connector=False))
        px = self._rects(labels(df, "x", "y", "g", fill=True, cornerRadius=3.0, connector=False))
        assert all(r["cornerRadius"] == 2.0 for r in rounded)  # True -> fontSize * 0.25
        assert all(r["cornerRadius"] == 0.0 for r in square)
        assert all(r["cornerRadius"] == 3.0 for r in px)

    def test_bg_chip_centers_on_text(self):
        # the chip must sit centred on the glyphs for every alignment: a left/right-anchored label
        # shifts the chip by the TEXT half-width (equal padding both sides), not the padded chip
        # half-width (which hugged the text to the near edge - the off-centre NK label bug).
        from dysonsphere.annotations import _text_bg_props

        fs = 7.0
        tw = len("NK") * fs * 0.6  # text-width estimate the helper uses internally
        _, x_left, _ = _text_bg_props("NK", fs, "left", "middle", 0, 0, "#000", None, 1.0, False)
        _, x_right, _ = _text_bg_props("NK", fs, "right", "middle", 0, 0, "#000", None, 1.0, False)
        _, x_center, _ = _text_bg_props("NK", fs, "center", "middle", 0, 0, "#000", None, 1.0, False)
        assert x_left == pytest.approx(tw / 2)  # text-start anchor -> chip centre a text half-width right
        assert x_right == pytest.approx(-tw / 2)
        assert x_center == 0.0

    def test_fill_centres_text_in_chip(self):
        # Every auto-placed label is centered so its rendered box follows the same geometry when an
        # axis is reflected. Chips remain concentric with that box.
        import numpy as np

        ang = np.linspace(0, 2 * np.pi, 8, endpoint=False)
        ring = pl.DataFrame({"x": list(np.cos(ang)), "y": list(np.sin(ang)), "g": [f"L{i}" for i in range(8)]})

        def _aligns(fill):
            spec = labels(ring, "x", "y", "g", fill=fill).to_dict()
            return [  # expr aligns: read the standard-orientation arm
                a if isinstance(a, str) else re.findall(r"'(left|right)'", a["expr"])[0]
                for lyr in spec["layer"]
                if lyr["mark"]["type"] == "text"
                for a in [lyr["mark"].get("align")]
            ]

        assert all(a == "center" for a in _aligns(False))
        assert all(a == "center" for a in _aligns(True))  # chip: all centred

        # concentric: for every chip label the rect and the text carry the SAME pixel offset from
        # their shared datum anchor, so the chip is centred on the glyphs however wrong the width
        # estimate is (the off-centre NK label).
        spec = labels(ring, "x", "y", "g", fill=True).to_dict()
        rects = [lyr for lyr in spec["layer"] if lyr["mark"]["type"] == "rect"]
        texts = [lyr for lyr in spec["layer"] if lyr["mark"]["type"] == "text"]
        assert len(rects) == len(texts) == 8
        for r, t in zip(rects, texts):
            assert r["encoding"]["x"]["datum"] == pytest.approx(t["encoding"]["x"]["datum"])
            assert r["encoding"]["y"]["datum"] == pytest.approx(t["encoding"]["y"]["datum"])
            assert r["encoding"]["xOffset"]["value"] == 0.0  # centred chip: no horizontal shift

    def test_no_invisible_pin_mark(self, df):
        # the scale pin must ride on the label marks themselves - no invisible point may land in
        # the spec (it used to show up as a phantom element in the exported SVG)
        spec = labels(df, "x", "y", "g", alwaysShowConnectors=True).to_dict()
        types = {lyr["mark"]["type"] for lyr in spec["layer"]}
        assert types == {"rule", "text"}

    def test_positions_are_datum_not_value(self, df):
        # label geometry is emitted in data coordinates (alt.datum) - a datum contributes no axis
        # title and never extends the shared domain, unlike a field; the pinned scale then places it
        spec = labels(df, "x", "y", "g", alwaysShowConnectors=True).to_dict()
        for lyr in spec["layer"]:
            assert "datum" in lyr["encoding"]["x"]
            assert "datum" in lyr["encoding"]["y"]

    def _connector_stroke_dashes(self, chart):
        return [lyr["mark"]["strokeDash"] for lyr in chart.to_dict()["layer"] if lyr["mark"]["type"] == "rule"]

    def test_connector_stroke_dash_default_solid(self, df):
        dashes = self._connector_stroke_dashes(labels(df, "x", "y", "g", alwaysShowConnectors=True))
        assert dashes and all(d == [0, 0] for d in dashes)

    def test_connector_stroke_dash_true_uses_theme(self, df):
        # default_theme fixture sets dashedWidth=[2, 2]
        dashes = self._connector_stroke_dashes(labels(df, "x", "y", "g", connectorStrokeDash=True))
        assert all(d == [2, 2] for d in dashes)

    def test_connector_stroke_dash_list_passthrough(self, df):
        dashes = self._connector_stroke_dashes(labels(df, "x", "y", "g", connectorStrokeDash=[4, 2]))
        assert all(d == [4, 2] for d in dashes)

    def _connector_marks(self, chart):
        return [lyr["mark"] for lyr in chart.to_dict()["layer"] if lyr["mark"]["type"] == "rule"]

    def test_connector_opacity_default_inherits_theme(self, df):
        # None -> no explicit opacity on the mark, so it inherits the theme's mark_rule config
        assert all("opacity" not in m for m in self._connector_marks(labels(df, "x", "y", "g")))

    def test_connector_opacity_sets_mark_opacity(self, df):
        # a float sets the mark opacity but does NOT touch color (stays darkmode-aware)
        marks = self._connector_marks(labels(df, "x", "y", "g", connectorOpacity=0.25, alwaysShowConnectors=True))
        assert marks and all(m["opacity"] == 0.25 and "color" not in m for m in marks)

    def test_connector_cap_default_leaves_spec_unchanged(self, df):
        implicit = labels(df, "x", "y", "g", alwaysShowConnectors=True).to_dict()
        explicit = labels(df, "x", "y", "g", connectorCap=None, alwaysShowConnectors=True).to_dict()
        assert implicit == explicit
        assert all("description" not in mark for mark in self._connector_marks(labels(df, "x", "y", "g")))

    def test_connector_arrow_reuses_existing_start_and_text_end_geometry(self, df):
        plain = labels(df, "x", "y", "g", connectorGap=0, alwaysShowConnectors=True).to_dict()
        arrow = labels(df, "x", "y", "g", connectorGap=0, connectorCap="arrow", alwaysShowConnectors=True).to_dict()
        plain_enc = [layer["encoding"] for layer in plain["layer"] if layer["mark"]["type"] == "rule"]
        arrow_layers = [layer for layer in arrow["layer"] if layer["mark"]["type"] == "rule"]
        assert [layer["encoding"] for layer in arrow_layers] == plain_enc
        assert all(layer["mark"]["description"].startswith("__dsrulecap_") for layer in arrow_layers)

    def test_connector_cap_validation_even_when_connector_disabled(self, df):
        with pytest.raises(ValueError, match="connectorCap"):
            labels(df, "x", "y", "g", connector=False, connectorCap="circle")  # ty: ignore[invalid-argument-type]
        assert isinstance(labels(df, "x", "y", "g", connector=False, connectorCap="arrow"), alt.LayerChart)

    def test_connector_gap_shortens_line(self, df):
        import math

        def total_len(chart):
            # connector endpoints are datum coords; same domains both charts, so comparison is fair
            return sum(
                math.dist((e["x"]["datum"], e["y"]["datum"]), (e["x2"]["datum"], e["y2"]["datum"]))
                for lyr in chart.to_dict()["layer"]
                if lyr["mark"]["type"] == "rule"
                for e in [lyr["encoding"]]
            )

        # a bigger gap leaves shorter visible connectors; gap=0 leaves the full length
        assert total_len(labels(df, "x", "y", "g", connectorGap=3)) < total_len(
            labels(df, "x", "y", "g", connectorGap=0)
        )

    def _n_connectors(self, chart):
        return sum(1 for lyr in chart.to_dict()["layer"] if lyr["mark"]["type"] == "rule")

    def test_short_connectors_skipped_by_default(self, df):
        # An impossible requested clearance omits connectors even when forced; it must never be
        # shrunk into a line touching the marker.
        assert self._n_connectors(labels(df, "x", "y", "g", connectorGap=1000)) == 0
        assert self._n_connectors(labels(df, "x", "y", "g", connectorGap=1000, alwaysShowConnectors=True)) == 0

    def test_marker_gap_is_uniform(self, monkeypatch):
        # every DRAWN connector starts exactly connectorGap px off its point centre. Domains pinned
        # to the chart pixel size so data units == px and distances survive the datum round-trip.
        import math

        from dysonsphere import _placement

        theme(width=100, height=100, viewPadding=False)
        monkeypatch.setattr(
            _placement, "_repel_labels", lambda anchors, sizes, **kwargs: [(x + 20, y) for x, y in anchors]
        )
        df = pl.DataFrame({"x": [10.0, 40.0, 70.0], "y": [20.0, 80.0, 40.0], "g": ["a", "b", "c"]})
        gap = 1.0
        spec = labels(df, "x", "y", "g", connectorGap=gap, xDomain=(0.0, 100.0), yDomain=(0.0, 100.0)).to_dict()
        anchors = [(10.0, 20.0), (40.0, 80.0), (70.0, 40.0)]
        starts = [
            (e["x"]["datum"], e["y"]["datum"])
            for lyr in spec["layer"]
            if lyr["mark"]["type"] == "rule"
            for e in [lyr["encoding"]]
        ]
        assert starts
        assert all(min(math.dist(st, a) for a in anchors) == pytest.approx(gap) for st in starts)
        # The text datum is the box center now; verify the exact text-end clearance against the
        # nearest rectangle boundary using the shared geometry helper.
        from dysonsphere._placement import _estimate_attachment_size

        daylight = 2.0 * alt.theme.options["axisWidth"]
        pending, checked = {}, 0
        for lyr in spec["layer"]:
            if lyr["mark"]["type"] == "rule":
                pending = lyr["encoding"]
            elif lyr["mark"]["type"] == "text" and pending:
                end = (pending["x2"]["datum"], pending["y2"]["datum"])
                center = (lyr["encoding"]["x"]["datum"], lyr["encoding"]["y"]["datum"])
                size = _estimate_attachment_size(lyr["encoding"]["text"]["value"], 6.0)
                edge = (center[0] - size[0] / 2, center[1])  # fixed seats are directly right of their owners
                assert math.dist(end, edge) == pytest.approx(daylight)
                checked += 1
                pending = {}
        assert checked

    def test_default_marker_gap_uses_shared_automatic_formula(self, monkeypatch):
        from dysonsphere import _placement
        from dysonsphere.annotations import _automatic_marker_gap

        theme(width=100, height=100, viewPadding=False)
        monkeypatch.setattr(
            _placement, "_repel_labels", lambda anchors, sizes, **kwargs: [(x + 20, y) for x, y in anchors]
        )
        df = pl.DataFrame({"x": [10.0, 40.0, 70.0], "y": [20.0, 80.0, 40.0], "g": ["a", "b", "c"]})
        spec = labels(
            df,
            "x",
            "y",
            "g",
            alwaysShowConnectors=True,
            xDomain=(0.0, 100.0),
            yDomain=(0.0, 100.0),
        ).to_dict()
        anchors = [(10.0, 20.0), (40.0, 80.0), (70.0, 40.0)]
        starts = [
            (encoding["x"]["datum"], encoding["y"]["datum"])
            for layer in spec["layer"]
            if layer["mark"]["type"] == "rule"
            for encoding in [layer["encoding"]]
        ]
        expected = _automatic_marker_gap()
        assert starts and all(
            min(math.dist(start, anchor) for anchor in anchors) == pytest.approx(expected) for start in starts
        )

    def test_reversed_axis_labels_stay_in_panel(self):
        # reversed axis mirrors markers at render; offsets must mirror too (3.13.0 spilled labels)
        import re

        import vl_convert as vlc

        df = pl.DataFrame({"x": [10.0, 30.0, 50.0], "y": [8.0, 8.5, 7.5], "g": ["aa", "bb", "cc"]})
        base = (
            alt.Chart(df)
            .mark_point()
            .encode(
                x=alt.X("x:Q", scale=alt.Scale(domain=[0, 100])),
                y=alt.Y("y:Q", scale=alt.Scale(domain=[0, 10], reverse=True)),
            )
        )
        svg = vlc.vegalite_to_svg((base + labels(df, "x", "y", "g")).to_dict())
        h = alt.theme.options["height"]
        for m in re.finditer(r"translate\(([-\d.e]+),([-\d.e]+)\)[^>]*>(aa|bb|cc)<", svg):
            assert -1.0 <= float(m.group(2)) <= h + 1.0

    def test_positions_are_datum_never_offsets(self, df):
        # containment invariant: every label/connector position is a data coordinate; no pixel
        # offsets, no scale() expressions - those broke on reversed axes and inside concat
        spec = labels(df, "x", "y", "g").to_dict()
        for lyr in spec["layer"]:
            m, e = lyr["mark"], lyr.get("encoding", {})
            for k in ("xOffset", "yOffset", "x2Offset", "y2Offset", "dx", "dy", "align"):
                assert not isinstance(m.get(k), dict), f"expr in mark.{k}"
            if m["type"] in ("rule", "text"):
                assert "datum" in e["x"] and "datum" in e["y"]
                assert "xOffset" not in m and "yOffset" not in m

    def test_all_labels_shown(self, df):
        # force-show: every requested label appears (never dropped)
        assert set(_text_values(labels(df, "x", "y", "g").to_dict())) == {"a", "b", "c"}

    def test_labels_selects_subset(self, df):
        # subset= draws only the chosen rows
        assert set(_text_values(labels(df, "x", "y", "g", subset=["a", "c"]).to_dict())) == {"a", "c"}

    def test_labels_int_auto_selects_n(self, df):
        # subset=int auto-picks that many (even-spread), no curation
        assert len(_text_values(labels(df, "x", "y", "g", subset=2).to_dict())) == 2

    def test_labels_int_deterministic(self, df):
        a = _text_values(labels(df, "x", "y", "g", subset=2).to_dict())
        b = _text_values(labels(df, "x", "y", "g", subset=2).to_dict())
        assert a == b

    def test_labels_rejects_bool(self, df):
        with pytest.raises(ValueError, match="not a bool"):
            labels(df, "x", "y", "g", subset=True)

    def test_labels_bool_mask_selects_rows(self, df):
        # a per-row boolean mask selects positionally (decoupled from the labels column)
        got = _text_values(labels(df, "x", "y", "g", subset=[True, False, True]).to_dict())
        assert set(got) == {"a", "c"}

    def test_labels_bool_mask_polars_series(self, df):
        got = _text_values(labels(df, "x", "y", "g", subset=df["x"] > 1.5).to_dict())
        assert set(got) == {"b", "c"}

    def test_labels_bool_mask_selects_by_row_not_label_value(self):
        # the whole point: a NON-UNIQUE labels column still selects the intended rows by position
        dup = pl.DataFrame({"x": [1.0, 2.0, 3.0], "y": [1.0, 2.0, 3.0], "g": ["a", "a", "b"]})
        got = _text_values(labels(dup, "x", "y", "g", subset=[False, True, False]).to_dict())
        assert got == ["a"]  # only the middle row, not both "a" rows

    def test_labels_list_of_values_still_matches_labelcol(self, df):
        # a same-length list that is NOT all-bool is treated as label VALUES, not a mask
        got = _text_values(labels(df, "x", "y", "g", subset=["a", "b", "c"]).to_dict())
        assert set(got) == {"a", "b", "c"}

    def test_domain_spans_full_df_when_labeling_subset(self, df):
        # even labeling one point the emitted domain spans the full df, so the union against the
        # base chart's own scale stays a no-op rather than clipping it to the labeled point
        spec = labels(df, "x", "y", "g", subset=["a"]).to_dict()
        domains = {
            tuple(lyr["encoding"]["x"]["scale"]["domain"])
            for lyr in spec["layer"]
            if lyr.get("encoding", {}).get("x", {}).get("scale")
        }
        assert domains == {(1.0, 3.0)}

    def test_emitted_domain_is_raw_extent_and_states_no_nice(self):
        # the emitted domain is the RAW extent - it must union to nothing against the base's scale,
        # so NOT the niced bounds the placement solver assumes internally. It exists only to stop
        # Vega-Lite emitting nice:true from this layer, which would re-nice a base that opted out,
        # so a nice key here (of any value) would defeat the point.
        df = pl.DataFrame({"x": [1.13, 2.7, 3.42], "y": [4.2, 6.1, 8.9], "g": ["a", "b", "c"]})
        spec = labels(df, "x", "y", "g").to_dict()
        enc = next(lyr["encoding"] for lyr in spec["layer"] if lyr["encoding"]["x"].get("scale"))
        assert enc["x"]["scale"]["domain"] == [1.13, 3.42]
        assert enc["y"]["scale"]["domain"] == [4.2, 8.9]
        assert "nice" not in enc["x"]["scale"] and "nice" not in enc["y"]["scale"]

    def test_explicit_domain_used_exactly(self, df):
        # an explicit xDomain/yDomain is forced as given - no nice rounding
        spec = labels(df, "x", "y", "g", xDomain=(1.13, 3.42), yDomain=(0.95, 3.05)).to_dict()
        pin = next(lyr["encoding"] for lyr in spec["layer"] if lyr["encoding"]["x"].get("scale"))
        assert pin["x"]["scale"]["domain"] == [1.13, 3.42]
        assert pin["y"]["scale"]["domain"] == [0.95, 3.05]

    def test_fontsize_defaults_to_primary(self, df):
        theme(fontSize=9)  # labels use the primary fontSize
        spec = labels(df, "x", "y", "g").to_dict()
        sizes = {lyr["mark"]["fontSize"] for lyr in spec["layer"] if lyr["mark"]["type"] == "text"}
        assert sizes == {9}

    def test_preserves_base_axis_titles(self, df):
        # labels positions by alt.datum (no field), so it must not touch the base axis titles.
        import re

        import vl_convert as vlc

        base = (
            alt.Chart(df)
            .mark_point()
            .encode(
                x=alt.X("x:Q", title="XT", scale=alt.Scale(domain=[1, 3], nice=False, zero=False)),
                y=alt.Y("y:Q", title="YT", scale=alt.Scale(domain=[1, 3], nice=False, zero=False)),
            )
        )
        svg = vlc.vegalite_to_svg((base + labels(df, "x", "y", "g", xDomain=(1.0, 3.0), yDomain=(1.0, 3.0))).to_dict())

        def rendered(t):
            return bool(re.search(r"<text[^>]*>[^<]*" + re.escape(t) + r"[^<]*</text>", svg))

        assert rendered("XT")
        assert rendered("YT")

    def test_read_filters_sidecars(self, tmp_path, df):
        import dysonsphere as ds

        ds.theme()
        base = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q")
        out = tmp_path / "c"
        ds.save(lambda: base + labels(df, "x", "y", "g"), str(out), format="json")
        frame = ds.metadata.read(str(out) + ".json", what="data")
        assert set(frame.columns) == {"x", "y", "g"}  # only the user's frame


@pytest.fixture(autouse=True)
def default_theme():
    theme(dashedWidth=[2, 2])


class TestRuleMarkKwargs:
    def test_opacity_always_present(self):
        kwargs = _rule_mark_kwargs(color=None, strokeWidth=None, strokeDash=None, opacity=0.5)
        assert kwargs["opacity"] == pytest.approx(0.5)

    def test_color_none_omitted(self):
        kwargs = _rule_mark_kwargs(color=None, strokeWidth=None, strokeDash=None, opacity=1.0)
        assert "color" not in kwargs

    def test_color_set(self):
        kwargs = _rule_mark_kwargs(color="red", strokeWidth=None, strokeDash=None, opacity=1.0)
        assert kwargs["color"] == "red"

    def test_stroke_width_none_omitted(self):
        kwargs = _rule_mark_kwargs(color=None, strokeWidth=None, strokeDash=None, opacity=1.0)
        assert "strokeWidth" not in kwargs

    def test_stroke_width_set(self):
        kwargs = _rule_mark_kwargs(color=None, strokeWidth=2.0, strokeDash=None, opacity=1.0)
        assert kwargs["strokeWidth"] == pytest.approx(2.0)

    def test_stroke_dash_none_omitted(self):
        kwargs = _rule_mark_kwargs(color=None, strokeWidth=None, strokeDash=None, opacity=1.0)
        assert "strokeDash" not in kwargs

    def test_stroke_dash_false_forces_solid(self):
        kwargs = _rule_mark_kwargs(color=None, strokeWidth=None, strokeDash=False, opacity=1.0)
        assert kwargs["strokeDash"] == [0, 0]

    def test_stroke_dash_true_reads_theme(self):
        kwargs = _rule_mark_kwargs(color=None, strokeWidth=None, strokeDash=True, opacity=1.0)
        assert kwargs["strokeDash"] == [2, 2]

    def test_stroke_dash_list_passthrough(self):
        kwargs = _rule_mark_kwargs(color=None, strokeWidth=None, strokeDash=[4, 2], opacity=1.0)
        assert kwargs["strokeDash"] == [4, 2]


class TestRule:
    def test_no_label_returns_chart(self):
        result = rule(y=0.5)
        assert isinstance(result, alt.Chart)

    def test_with_label_returns_layer_chart(self):
        result = rule(y=0.5, label="threshold")
        assert isinstance(result, alt.LayerChart)

    def test_multiple_values_returns_layer(self):
        # One datum layer per value (single-value stays a bare Chart, see test_no_label_returns_chart).
        result = rule(y=[0.25, 0.5, 0.75])
        assert isinstance(result, alt.LayerChart)

    def test_multiple_values_with_labels_returns_layer(self):
        result = rule(y=[0.25, 0.75], label=["low", "high"])
        assert isinstance(result, alt.LayerChart)

    def test_vertical_rule(self):
        result = rule(x=5.0)
        assert isinstance(result, alt.Chart)

    @pytest.mark.parametrize(
        ("kwargs", "expected"),
        [
            ({"x": 2, "x2": 8, "y": 5}, {"x": {"datum": 2.0}, "x2": {"datum": 8.0}, "y": {"datum": 5.0}}),
            ({"x": 5, "y": 2, "y2": 8}, {"x": {"datum": 5.0}, "y": {"datum": 2.0}, "y2": {"datum": 8.0}}),
            (
                {"x": 2, "y": 3, "x2": 8, "y2": 9},
                {"x": {"datum": 2.0}, "y": {"datum": 3.0}, "x2": {"datum": 8.0}, "y2": {"datum": 9.0}},
            ),
            (
                {"slope": 2, "intercept": 1, "span": (0, 5)},
                {"x": {"datum": 0.0}, "y": {"datum": 1.0}, "x2": {"datum": 5.0}, "y2": {"datum": 11.0}},
            ),
        ],
    )
    def test_coordinate_geometry(self, kwargs, expected):
        assert rule(**kwargs).to_dict()["encoding"] == expected

    def test_equation_intercept_defaults_zero(self):
        assert rule(slope=2, span=(1, 3)).to_dict()["encoding"]["y2"] == {"datum": 6.0}

    def test_equation_requires_span(self):
        with pytest.raises(ValueError, match="span=.*required"):
            rule(slope=1)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {},
            {"x2": 2},
            {"x": 1, "y": 2},
            {"x": 1, "y": 2, "x2": 3, "span": (0, 2)},
            {"slope": 1, "x": 0, "span": (0, 2)},
        ],
    )
    def test_invalid_geometry_raises(self, kwargs):
        with pytest.raises(ValueError):
            rule(**kwargs)

    def test_diagonal_label_is_horizontal_and_anchors_smaller_x_endpoint(self):
        spec = rule(x=8, y=9, x2=2, y2=3, label="trend").to_dict()
        text_layer = next(layer for layer in spec["layer"] if layer["mark"]["type"] == "text")
        assert text_layer["encoding"]["x"] == {"datum": 2.0}
        assert text_layer["encoding"]["y"] == {"datum": 3.0}
        assert "angle" not in text_layer["mark"]

    def test_diagonal_center_label_uses_data_coordinate_midpoint(self):
        spec = rule(x=2, y=3, x2=8, y2=11, label="trend", labelAlign="center").to_dict()
        text_layer = next(layer for layer in spec["layer"] if layer["mark"]["type"] == "text")
        assert text_layer["encoding"]["x"] == {"datum": 5.0}
        assert text_layer["encoding"]["y"] == {"datum": 7.0}

    def test_diagonal_facet_safe_data_mode_renders(self):
        import vl_convert as vlc

        df = pl.DataFrame({"g": ["a", "a", "b", "b"], "x": [0, 2, 0, 2], "y": [0, 2, 1, 3]})
        base = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q")
        faceted = (base + rule(x=0, y=0, x2=2, y2=2, label="trend", data=df)).facet(column="g:N")
        assert vlc.vegalite_to_svg(faceted.to_dict()).count("trend") >= 2

    @pytest.mark.parametrize("coordinate", [True, False, float("nan"), float("inf"), "5"])
    def test_axis_coordinate_rejects_non_numeric_bool_and_nonfinite(self, coordinate):
        with pytest.raises(ValueError, match="finite number"):
            rule(y=coordinate)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"slope": True, "span": (0, 1)},
            {"slope": float("inf"), "span": (0, 1)},
            {"slope": 1, "intercept": False, "span": (0, 1)},
            {"slope": 1, "intercept": float("nan"), "span": (0, 1)},
            {"slope": 1, "span": (False, 1)},
            {"slope": 1, "span": (0, float("inf"))},
            {"x": 0, "y": 0, "x2": True, "y2": 1},
        ],
    )
    def test_all_geometry_numbers_are_strictly_finite(self, kwargs):
        with pytest.raises(ValueError, match="finite number"):
            rule(**kwargs)

    @pytest.mark.parametrize("coordinate", ["x", "y"])
    def test_empty_axis_coordinate_list_rejected(self, coordinate):
        with pytest.raises(ValueError, match="must not be empty"):
            rule(**{coordinate: []})  # ty: ignore[invalid-argument-type]

    def test_bounded_axis_fixed_coordinate_list_is_supported(self):
        spec = rule(x=2, x2=8, y=[3, 7]).to_dict()
        assert [layer["encoding"]["y"]["datum"] for layer in spec["layer"]] == [3.0, 7.0]

    @pytest.mark.parametrize("name", ["startCap", "endCap"])
    def test_invalid_cap_rejected(self, name):
        with pytest.raises(ValueError, match=name):
            rule(y=1, **{name: "triangle"})  # ty: ignore[invalid-argument-type]

    @pytest.mark.parametrize("name", ["startGap", "endGap"])
    @pytest.mark.parametrize("value", [True, -1, float("nan"), float("inf")])
    def test_invalid_gap_rejected(self, name, value):
        with pytest.raises(ValueError, match=name):
            rule(y=1, **{name: value})

    def test_cap_options_create_durable_marker_but_plain_rule_does_not(self):
        from dysonsphere.utils import _RULE_CAP_PREFIX

        assert rule(y=1, startCap="arrow").to_dict()["mark"]["description"].startswith(_RULE_CAP_PREFIX)
        assert "description" not in rule(y=1).to_dict()["mark"]

    def test_explicit_zero_gap_is_distinct_from_cap_default(self):
        from dysonsphere.annotations import _automatic_marker_gap
        from dysonsphere.export import _rule_cap_options

        zero_name = rule(y=1, startCap="circle", startGap=0).to_dict()["mark"]["description"]
        auto_name = rule(y=1, startCap="circle").to_dict()["mark"]["description"]
        assert _rule_cap_options(zero_name) == ("circle", None, 0.0, 0.0)
        assert _rule_cap_options(auto_name) == ("circle", None, _automatic_marker_gap(), 0.0)

    def test_automatic_cap_gap_exactly_matches_labels_formula_and_theme(self):
        from dysonsphere.annotations import _automatic_marker_gap
        from dysonsphere.export import _rule_cap_options

        theme(markSize=50, markStrokeWidth=1.5, axisWidth=0.75)
        expected = math.sqrt(50 / (2 * math.pi)) + 1.5 + 2 * 0.75
        assert _automatic_marker_gap() == pytest.approx(expected)
        marker = rule(y=1, startCap="arrow").to_dict()["mark"]["description"]
        assert _rule_cap_options(marker) == ("arrow", None, pytest.approx(expected), 0.0)

    def test_explicit_rule_gap_is_theme_invariant_and_capless_default_is_zero(self):
        from dysonsphere.export import _rule_cap_options

        theme(markSize=10, axisWidth=0.25)
        explicit_a = rule(y=1, startCap="arrow", startGap=1.25).to_dict()["mark"]["description"]
        theme(markSize=100, axisWidth=2)
        explicit_b = rule(y=1, startCap="arrow", startGap=1.25).to_dict()["mark"]["description"]
        options_a = _rule_cap_options(explicit_a)
        options_b = _rule_cap_options(explicit_b)
        assert options_a is not None and options_b is not None
        assert options_a[2] == options_b[2] == 1.25
        assert "description" not in rule(y=1).to_dict()["mark"]

    def test_positional_coordinate_rejected(self):
        with pytest.raises(TypeError):
            rule(0.5)  # ty: ignore[too-many-positional-arguments]

    def test_preserves_explicit_base_axis_titles(self):
        # Regression: a rule must not null the base chart's axis title (the datum-vs-field fix).
        import re

        import vl_convert as vlc

        base = (
            alt.Chart(pl.DataFrame({"a": [0.0, 1, 2], "b": [0.0, 1, 2]}))
            .mark_point()
            .encode(x=alt.X("a:Q", title="MyXTitle"), y=alt.Y("b:Q", title="MyYTitle"))
        )
        svg = vlc.vegalite_to_svg((base + rule(x=1.0) + rule(y=1.0)).to_dict())

        def rendered(t):
            return bool(re.search(r"<text[^>]*>[^<]*" + re.escape(t) + r"[^<]*</text>", svg))

        assert rendered("MyXTitle")
        assert rendered("MyYTitle")

    def test_preserves_derived_base_axis_title(self):
        # A derived (field-name) base title must not gain a ", __v"-style suffix from the rule.
        import re

        import vl_convert as vlc

        base = (
            alt.Chart(pl.DataFrame({"weight": [0.0, 1, 2], "height": [0.0, 1, 2]}))
            .mark_point()
            .encode(x="weight:Q", y="height:Q")
        )
        svg = vlc.vegalite_to_svg((base + rule(x=1.0)).to_dict())
        texts = re.findall(r"<text[^>]*>([^<]+)</text>", svg)
        assert "weight" in texts
        assert not any("__" in t for t in texts)  # no leaked sidecar field name


class TestRuleLabelInset:
    # An edge-anchored rule label hugs a FLUSH spine, so it is inset by _EDGE_OFFSET (the same 1px
    # text uses). A detached axis already provides the gap. Center anchors are untouched.
    def test_detached_axis_label_at_content_edge(self):
        theme(width=100, height=100, axisOffset=True)
        perp_ch, perp_anchor, _ = _rule_label_geometry("y", "left", "top", 0, 0, 7, None)
        assert perp_ch == "x"
        assert perp_anchor == {"value": 0}  # the detached axis provides the gap

    def test_flush_default_left_label_inset(self):
        theme(width=100, height=100)  # axes are flush by default
        _, perp_anchor, _ = _rule_label_geometry("y", "left", "top", 0, 0, 7, None)
        assert perp_anchor == {"value": _EDGE_OFFSET}

    def test_closed_left_label_inset(self):
        theme(width=100, height=100, closed=True)
        _, perp_anchor, _ = _rule_label_geometry("y", "left", "top", 0, 0, 7, None)
        assert perp_anchor == {"value": _EDGE_OFFSET}

    def test_closed_right_label_inset_from_right_edge(self):
        theme(width=100, height=100, closed=True)
        _, perp_anchor, _ = _rule_label_geometry("y", "right", "top", 0, 0, 7, None)
        assert perp_anchor == {"value": 100 - _EDGE_OFFSET}

    def test_closed_center_label_not_inset(self):
        theme(width=100, height=100, closed=True)
        _, perp_anchor, _ = _rule_label_geometry("y", "center", "top", 0, 0, 7, None)
        assert perp_anchor == {"value": 50}

    def test_closed_vertical_rule_top_label_inset(self):
        theme(width=100, height=100, closed=True)
        perp_ch, perp_anchor, _ = _rule_label_geometry("x", "top", "right", 0, 0, 7, None)
        assert perp_ch == "y"
        assert perp_anchor == {"value": _EDGE_OFFSET}

    def test_matches_text_edge_padding(self):
        """rule and text must inset edge-anchored text by the same amount."""
        theme(width=100, height=100)
        _, perp_anchor, _ = _rule_label_geometry("y", "left", "top", 0, 0, 7, None)
        text_spec = text("t", position="middleLeft").to_dict()
        assert perp_anchor == {"value": _EDGE_OFFSET}
        assert text_spec["encoding"]["x"]["value"] == _EDGE_OFFSET


class TestShadeFlushDefault:
    # flush extends the outermost band to the plot edge. It follows the SPINE, not `closed`:
    # a detached axis already leaves a gap there, a flush one would show a sliver of bare plot.
    @staticmethod
    def _first_band_start(chart) -> float:
        layer = chart.to_dict()["layer"][0]
        return layer["encoding"]["x"]["value"]

    def test_flush_under_the_default_flush_spine(self):
        theme(width=100, height=100)
        assert _default_flush() is True
        assert self._first_band_start(shade(categories=["a", "b", "c", "d"])) == 0

    def test_not_flush_when_the_axis_is_detached(self):
        theme(width=100, height=100, axisOffset=True)
        assert _default_flush() is False
        assert self._first_band_start(shade(categories=["a", "b", "c", "d"])) > 0

    def test_flush_when_closed(self):
        theme(width=100, height=100, closed=True)
        assert _default_flush() is True

    def test_explicit_flush_overrides(self):
        theme(width=100, height=100)  # default would be flush
        assert self._first_band_start(shade(categories=["a", "b", "c", "d"], flush=False)) > 0


class TestRuleSpan:
    # span= slices a rule to a portion of its running axis (the axis it runs along, opposite of
    # `axis`): numeric bounds -> data coords via alt.datum; category names -> pixels via band scale.
    CATS = ["Control", "A", "B", "C", "D"]

    def _enc(self, layer):
        # encoding of a bare Chart, or of each layer of a LayerChart.
        d = layer.to_dict()
        return [lyr["encoding"] for lyr in d["layer"]] if "layer" in d else d["encoding"]

    def test_numeric_span_horizontal_datum(self):
        # axis="y" runs along x: span goes on x / x2 as data-coord datums.
        enc = self._enc(rule(y=5.0, span=(2.0, 8.0)))
        assert enc == {"y": {"datum": 5.0}, "x": {"datum": 2.0}, "x2": {"datum": 8.0}}

    def test_numeric_span_vertical_datum(self):
        # axis="x" runs along y: span goes on y / y2.
        enc = self._enc(rule(x=5.0, span=(2.0, 8.0)))
        assert enc == {"x": {"datum": 5.0}, "y": {"datum": 2.0}, "y2": {"datum": 8.0}}

    def test_no_span_omits_running_channel(self):
        # Regression: without span, a horizontal rule has no x/x2 (spans full width).
        enc = self._enc(rule(y=5.0))
        assert enc == {"y": {"datum": 5.0}}

    def test_category_span_resolves_to_pixels(self):
        # String bounds resolve through the band scale to pixel values (like shade).
        theme(width=100, height=100)
        enc = self._enc(rule(y=5.0, span=("Control", "B"), categories=self.CATS))
        assert enc["y"] == {"datum": 5.0}
        assert "value" in enc["x"] and "value" in enc["x2"]
        assert enc["x"]["value"] < enc["x2"]["value"]

    def test_span_applies_to_every_value(self):
        layers = self._enc(rule(y=[3.0, 7.0], span=(2.0, 8.0)))
        for lyr in layers:
            assert lyr["x"] == {"datum": 2.0} and lyr["x2"] == {"datum": 8.0}

    def test_label_anchors_to_span_end(self):
        # A labelAlign="right" label on a sliced horizontal line sits at the slice's high end (x=8),
        # not the chart edge; "left" sits at the low end (x=2).
        r_enc = self._enc(rule(y=5.0, span=(2.0, 8.0), label="t", labelAlign="right"))
        text_layer = next(e for e in r_enc if "text" in e)
        assert text_layer["x"] == {"datum": 8.0}
        l_enc = self._enc(rule(y=5.0, span=(2.0, 8.0), label="t", labelAlign="left"))
        text_layer = next(e for e in l_enc if "text" in e)
        assert text_layer["x"] == {"datum": 2.0}

    def test_vertical_label_top_is_high_data_value(self):
        # axis="x": "top" anchors to the visually-upper end = the larger data-y (8, not 1).
        enc = self._enc(rule(x=3.0, span=(1.0, 8.0), label="v", labelAlign="top"))
        text_layer = next(e for e in enc if "text" in e)
        assert text_layer["y"] == {"datum": 8.0}

    def test_string_span_without_categories_raises(self):
        with pytest.raises(ValueError, match="categories is required"):
            rule(y=5.0, span=("Control", "B"))

    def test_mixed_span_bounds_raise(self):
        with pytest.raises(ValueError, match="both be numbers or both be category names"):
            rule(y=5.0, span=("Control", 8.0), categories=self.CATS)  # ty: ignore[invalid-argument-type]

    def test_unknown_category_raises(self):
        with pytest.raises(ValueError, match="not in categories"):
            rule(y=5.0, span=("Control", "Z"), categories=self.CATS)

    def test_span_wrong_length_raises(self):
        with pytest.raises(ValueError, match="start, end"):
            rule(y=5.0, span=(2.0, 4.0, 8.0))  # ty: ignore[invalid-argument-type]

    def test_span_preserves_base_axis_titles(self):
        # A sliced rule must not clobber the base chart's axis titles (datum-not-field).
        import vl_convert as vlc

        base = (
            alt.Chart(pl.DataFrame({"a": [0.0, 5, 10], "b": [0.0, 5, 10]}))
            .mark_point()
            .encode(x=alt.X("a:Q", title="MyXTitle"), y=alt.Y("b:Q", title="MyYTitle"))
        )
        svg = vlc.vegalite_to_svg((base + rule(y=5.0, span=(2.0, 8.0), label="s")).to_dict())
        assert "MyXTitle" in svg and "MyYTitle" in svg

    def test_span_facet_safe_data_mode_renders(self):
        # span works in the datum (data=) facet-safe path too.
        df = pl.DataFrame({"a": [0.0, 5, 10], "b": [0.0, 5, 10]})
        layer = rule(y=5.0, span=(2.0, 8.0), data=df)
        layer.to_dict()  # must not raise
        assert layer.to_dict()["encoding"]["x"] == {"datum": 2.0}


def _off(v):
    """Numeric part of a pixel offset: raw float, or the trailing factor of a sign ExprRef."""
    return float(v) if isinstance(v, (int, float)) else float(v["expr"].rsplit("* ", 1)[-1])


class TestText:
    def test_single_annotation_returns_chart(self):
        assert isinstance(text("a", x=1.0, y=1.0), alt.Chart)

    def test_fill_false_bare_text(self):
        # the chip is gated on fill: default (fill=False) draws no rect even though stroke defaults True
        assert text("hi", x=1.0, y=1.0).to_dict()["mark"]["type"] == "text"

    def test_fill_true_adds_background_rect(self):
        from dysonsphere.palettes import colors

        spec = text("hi", x=1.0, y=1.0, fill=True).to_dict()
        assert [lyr["mark"]["type"] for lyr in spec["layer"]] == ["rect", "text"]  # rect behind text
        assert spec["layer"][0]["mark"]["fill"] == colors["greys"][0]  # light default

    def test_fill_darkmode_uses_greys11(self):
        from dysonsphere.palettes import colors

        theme(dark=True)
        rect = text("hi", x=1.0, y=1.0, fill=True).to_dict()["layer"][0]["mark"]
        assert rect["fill"] == colors["greys"][11]

    def test_fill_custom_color_and_opacity(self):
        rect = text("hi", x=1.0, y=1.0, fill="#123456", fillOpacity=0.5).to_dict()["layer"][0]["mark"]
        assert rect["fill"] == "#123456" and rect["fillOpacity"] == pytest.approx(0.5)

    def test_fill_true_default_stroke_borders_the_chip(self):
        # stroke defaults True, so a fill chip gets a darkmode-aware border
        rect = text("hi", x=1.0, y=1.0, fill=True).to_dict()["layer"][0]["mark"]
        assert rect["stroke"] == "black"  # light default

    def test_stroke_false_pins_off_config_rect_border(self):
        # the theme styles config.rect with a black stroke; stroke=False must pin it off, not leak it
        rect = text("hi", x=1.0, y=1.0, fill=True, stroke=False).to_dict()["layer"][0]["mark"]
        assert rect["stroke"] is None and rect["strokeWidth"] == 0

    def test_corner_radius_bool_and_float(self):
        def cr(**kw):
            return text("hi", x=1.0, y=1.0, fill=True, fontSize=8, **kw).to_dict()["layer"][0]["mark"]["cornerRadius"]

        assert cr() == 2.0  # True -> fontSize * 0.25
        assert cr(cornerRadius=False) == 0.0
        assert cr(cornerRadius=3.0) == 3.0

    def test_multiple_annotations_return_layer(self):
        # One datum layer per annotation (single stays a bare Chart).
        assert isinstance(text(["a", "b"], x=[1.0, 2.0], y=[1.0, 2.0]), alt.LayerChart)

    def test_preserves_base_axis_titles(self):
        # Regression: text annotations must not null the base chart's axis titles.
        import re

        import vl_convert as vlc

        base = (
            alt.Chart(pl.DataFrame({"a": [0.0, 1, 2], "b": [0.0, 1, 2]}))
            .mark_point()
            .encode(x=alt.X("a:Q", title="XT"), y=alt.Y("b:Q", title="YT"))
        )
        svg = vlc.vegalite_to_svg((base + text("hi", x=1.0, y=1.0)).to_dict())

        def rendered(t):
            return bool(re.search(r"<text[^>]*>[^<]*" + re.escape(t) + r"[^<]*</text>", svg))

        assert rendered("XT")
        assert rendered("YT")


class TestRuleDatum:
    """Facet-safe datum mode: rule(data=df) shares the base's frame and positions by datum."""

    @pytest.fixture
    def df(self):
        return pl.DataFrame({"g": ["A", "A", "B", "B"], "x": [1.0, 2, 3, 4], "value": [1.0, 2, 3, 4]})

    def test_datum_single_returns_chart(self, df):
        assert isinstance(rule(y=2.0, data=df), alt.Chart)

    def test_datum_multi_returns_layer(self, df):
        assert isinstance(rule(y=[1.0, 3.0], data=df), alt.LayerChart)

    def test_datum_with_label_returns_layer(self, df):
        assert isinstance(rule(y=2.0, label="thr", data=df), alt.LayerChart)

    def test_datum_uses_datum_not_sidecar(self, df):
        import json

        spec = json.dumps(rule(y=2.0, data=df).to_dict())
        assert "__v" not in spec  # no field-based sidecar
        assert "__dysonsphere__" not in spec  # no internal sentinel dataset (shares the user's df)
        assert '"datum"' in spec  # positioned by a constant datum

    def test_datum_pandas_accepted(self, df):
        rule(y=2.0, data=df.to_pandas()).to_dict()  # dataframe normalization handles pandas

    def test_datum_faceting_succeeds(self, df):
        base = alt.Chart(df).mark_point().encode(x="x:Q", y="value:Q")
        faceted = (base + rule(y=2.5, label="thr", data=df)).facet(column="g:N")
        assert isinstance(faceted, alt.FacetChart)
        faceted.to_dict()  # compiles without the shared-data facet error

    def test_default_mode_not_facetable(self, df):
        # Contrast: the data-backed default cannot be faceted — the limitation datum mode fixes.
        base = alt.Chart(df).mark_point().encode(x="x:Q", y="value:Q")
        with pytest.raises(ValueError, match="Facet charts require data"):
            (base + rule(y=2.5)).facet(column="g:N")


class TestTextDatum:
    """Facet-safe datum mode for text(data=df)."""

    @pytest.fixture
    def df(self):
        return pl.DataFrame({"g": ["A", "A", "B", "B"], "cat": ["X", "Y", "X", "Y"], "value": [1.0, 2, 3, 4]})

    def test_datum_single_returns_chart(self, df):
        assert isinstance(text("hi", x=1.0, y=2.0, data=df), alt.Chart)

    def test_datum_multi_returns_layer(self, df):
        assert isinstance(text(["a", "b"], x=["X", "Y"], y=[1.0, 2.0], data=df), alt.LayerChart)

    def test_datum_uses_datum_not_sidecar(self, df):
        import json

        spec = json.dumps(text("hi", x="X", y=2.0, data=df).to_dict())
        assert "__text" not in spec and "__dysonsphere__" not in spec  # no sidecar
        assert '"datum"' in spec and '"value": "hi"' in spec  # datum position + value text

    def test_datum_faceting_succeeds(self, df):
        base = alt.Chart(df).mark_point().encode(x="cat:N", y="value:Q")
        faceted = (base + text("★", x="X", y=3.0, data=df)).facet(column="g:N")
        assert isinstance(faceted, alt.FacetChart)
        faceted.to_dict()

    def test_datum_pixel_preset(self, df):
        base = alt.Chart(df).mark_point().encode(x="cat:N", y="value:Q")
        (base + text("n", position="topRight", data=df)).facet(column="g:N").to_dict()

    def test_default_not_facetable(self, df):
        base = alt.Chart(df).mark_point().encode(x="cat:N", y="value:Q")
        with pytest.raises(ValueError, match="Facet charts require data"):
            (base + text("hi", x="X", y=2.0)).facet(column="g:N")


class TestShadeDatum:
    """Facet-safe datum mode for shade(positions=..., data=df); band mode is unsupported."""

    @pytest.fixture
    def df(self):
        return pl.DataFrame({"g": ["A", "A", "B", "B"], "x": [1.0, 2, 3, 4], "value": [1.0, 2, 3, 4]})

    def test_datum_numeric_faceting_succeeds(self, df):
        base = alt.Chart(df).mark_point().encode(x="x:Q", y="value:Q")
        faceted = (base + shade(positions=[(1.5, 2.5)], axis="x", data=df)).facet(column="g:N")
        assert isinstance(faceted, alt.FacetChart)
        faceted.to_dict()

    def test_datum_uses_datum_not_sidecar(self, df):
        import json

        spec = json.dumps(shade(positions=[(1.5, 2.5)], axis="x", data=df).to_dict())
        assert "__xs" not in spec and "__dysonsphere__" not in spec  # no sidecar fields
        assert '"datum"' in spec

    def test_band_mode_with_data_raises(self, df):
        with pytest.raises(ValueError, match="positions mode only"):
            shade(["A", "B"], data=df)

    def test_default_not_facetable(self, df):
        base = alt.Chart(df).mark_point().encode(x="x:Q", y="value:Q")
        with pytest.raises(ValueError, match="Facet charts require data"):
            (base + shade(positions=[(1.5, 2.5)], axis="x")).facet(column="g:N")

    def test_default_preserves_base_axis_titles(self, df):
        # Regression: a shade's data-range rect must not null the base chart's axis titles.
        import re

        import vl_convert as vlc

        base = alt.Chart(df).mark_point().encode(x=alt.X("x:Q", title="XT"), y=alt.Y("value:Q", title="YT"))
        svg = vlc.vegalite_to_svg((base + shade(positions=[((1.0, 2.0), (1.0, 2.0))], axis="both")).to_dict())

        def rendered(t):
            return bool(re.search(r"<text[^>]*>[^<]*" + re.escape(t) + r"[^<]*</text>", svg))

        assert rendered("XT")
        assert rendered("YT")


class TestShadeCornerRadius:
    """theme(cornerRadius=...) styles config.rect (data marks); shade bands are annotations
    and must stay square regardless."""

    def _rect_corner_radii(self, layer_chart):
        # Collect cornerRadius from every mark spec in the composed shade layer.
        spec = layer_chart.to_dict()
        return [lyr.get("mark", {}).get("cornerRadius") for lyr in spec.get("layer", [spec])]

    def test_band_mode_square_under_rounded_theme(self):
        import dysonsphere as ds

        try:
            ds.theme(cornerRadius=8)
            radii = self._rect_corner_radii(shade(["A", "B", "C"]))
        finally:
            ds.theme()
        assert radii and all(r == 0 for r in radii)

    def test_positions_mode_square_under_rounded_theme(self):
        import dysonsphere as ds

        try:
            ds.theme(cornerRadius=8)
            radii = self._rect_corner_radii(shade(positions=[(1.5, 2.5), (4.0, 5.0)], axis="x"))
        finally:
            ds.theme()
        assert radii and all(r == 0 for r in radii)
