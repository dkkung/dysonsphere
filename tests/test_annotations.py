import altair as alt
import polars as pl
import pytest

from dysonsphere.annotations import _rule_mark_kwargs, add_labels, add_rule, add_shade, add_text
from dysonsphere.theme import theme


def _text_values(spec):
    """All text-mark strings in a chart spec (add_labels encodes text via alt.value)."""
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


class TestAddLabels:
    @pytest.fixture
    def df(self):
        return pl.DataFrame({"x": [1.0, 2.0, 3.0], "y": [1.0, 2.0, 3.0], "g": ["a", "b", "c"]})

    def test_returns_layerchart(self, df):
        assert isinstance(add_labels(df, "x", "y", "g"), alt.LayerChart)

    def test_layer_count_with_leaders(self, df):
        # (connector + text) per label, nothing else - the scale pin rides on the first label layer,
        # no invisible sidecar mark (alwaysShowConnectors so no short-connector is dropped, making
        # the count deterministic)
        chart = add_labels(df, "x", "y", "g", alwaysShowConnectors=True)
        assert len(chart.to_dict()["layer"]) == 3 * 2

    def test_no_connector(self, df):
        # 1 text per label, no pin layer
        assert len(add_labels(df, "x", "y", "g", connector=False).to_dict()["layer"]) == 3

    def test_no_invisible_pin_mark(self, df):
        # the scale pin must ride on the label marks themselves - no invisible point may land in
        # the spec (it used to show up as a phantom element in the exported SVG)
        spec = add_labels(df, "x", "y", "g").to_dict()
        types = {lyr["mark"]["type"] for lyr in spec["layer"]}
        assert types == {"rule", "text"}

    def test_positions_are_datum_not_value(self, df):
        # label geometry is emitted in data coordinates (alt.datum) - a datum contributes no axis
        # title and never extends the shared domain, unlike a field; the pinned scale then places it
        spec = add_labels(df, "x", "y", "g", alwaysShowConnectors=True).to_dict()
        for lyr in spec["layer"]:
            assert "datum" in lyr["encoding"]["x"]
            assert "datum" in lyr["encoding"]["y"]

    def _connector_stroke_dashes(self, chart):
        return [lyr["mark"]["strokeDash"] for lyr in chart.to_dict()["layer"] if lyr["mark"]["type"] == "rule"]

    def test_connector_stroke_dash_default_solid(self, df):
        dashes = self._connector_stroke_dashes(add_labels(df, "x", "y", "g"))
        assert dashes and all(d == [0, 0] for d in dashes)

    def test_connector_stroke_dash_true_uses_theme(self, df):
        # default_theme fixture sets dashedWidth=[2, 2]
        dashes = self._connector_stroke_dashes(add_labels(df, "x", "y", "g", connectorStrokeDash=True))
        assert all(d == [2, 2] for d in dashes)

    def test_connector_stroke_dash_list_passthrough(self, df):
        dashes = self._connector_stroke_dashes(add_labels(df, "x", "y", "g", connectorStrokeDash=[4, 2]))
        assert all(d == [4, 2] for d in dashes)

    def test_connector_gap_shortens_line(self, df):
        import math

        def total_len(chart):
            # connector ends are datum (data coords); the comparison is scale-free since both
            # charts pin the same domain
            segs = [
                (e["x"]["datum"], e["y"]["datum"], e["x2"]["datum"], e["y2"]["datum"])
                for lyr in chart.to_dict()["layer"]
                if lyr["mark"]["type"] == "rule"
                for e in [lyr["encoding"]]
            ]
            return sum(math.dist((x, y), (x2, y2)) for x, y, x2, y2 in segs)

        # a bigger gap leaves shorter visible connectors; gap=0 leaves the full length
        assert total_len(add_labels(df, "x", "y", "g", connectorGap=3)) < total_len(
            add_labels(df, "x", "y", "g", connectorGap=0)
        )

    def _n_connectors(self, chart):
        return sum(1 for lyr in chart.to_dict()["layer"] if lyr["mark"]["type"] == "rule")

    def test_short_connectors_skipped_by_default(self, df):
        # the skip threshold is 2*connectorGap + 1 (font-independent): a huge gap makes every
        # connector a "stub" that gets dropped by default, while alwaysShowConnectors forces one
        # per label
        assert self._n_connectors(add_labels(df, "x", "y", "g", connectorGap=1000)) == 0
        assert self._n_connectors(add_labels(df, "x", "y", "g", connectorGap=1000, alwaysShowConnectors=True)) == 3

    def test_marker_gap_is_uniform(self):
        # every DRAWN connector starts exactly connectorGap px off its point centre - the gap never
        # shrinks (the old seg*0.25 shrink made short connectors pierce the dot while long ones
        # cleared it: nonuniform touching-vs-gapped dots on one chart). Domains pinned to the chart
        # pixel size so data units == px and distances survive the datum round-trip; points spread
        # wide so each connector start is nearest its OWN anchor.
        import math

        df = pl.DataFrame({"x": [10.0, 50.0, 90.0], "y": [20.0, 80.0, 40.0], "g": ["a", "b", "c"]})
        gap = 1.0
        chart = add_labels(df, "x", "y", "g", connectorGap=gap, xDomain=(0.0, 100.0), yDomain=(0.0, 100.0))
        spec = chart.to_dict()
        anchors = [(x * 1.0, y * 1.0) for x, y in zip(df["x"], df["y"])]
        gaps = [
            min(math.dist((e["x"]["datum"], e["y"]["datum"]), a) for a in anchors)
            for lyr in spec["layer"]
            if lyr["mark"]["type"] == "rule"
            for e in [lyr["encoding"]]
        ]
        assert gaps  # at least one connector must be drawn for the assertion to mean anything
        assert all(g == pytest.approx(gap) for g in gaps)
        # the TEXT end keeps only the whitespace term (2*axisWidth = 0.5px at the default theme) -
        # asymmetric by design, there is no marker to clear at the label. (Assumes side-attached
        # labels, where the text anchor IS the connector attachment point; these spread points
        # place all labels beside their dots, deterministically.)
        text_anchors = [
            (lyr["encoding"]["x"]["datum"], lyr["encoding"]["y"]["datum"])
            for lyr in spec["layer"]
            if lyr["mark"]["type"] == "text"
        ]
        text_gaps = [
            min(math.dist((e["x2"]["datum"], e["y2"]["datum"]), t) for t in text_anchors)
            for lyr in spec["layer"]
            if lyr["mark"]["type"] == "rule"
            for e in [lyr["encoding"]]
        ]
        assert all(g == pytest.approx(0.5) for g in text_gaps)

    def test_all_labels_shown(self, df):
        # force-show: every requested label appears (never dropped)
        assert set(_text_values(add_labels(df, "x", "y", "g").to_dict())) == {"a", "b", "c"}

    def test_labels_selects_subset(self, df):
        # labels= draws only the chosen rows
        assert set(_text_values(add_labels(df, "x", "y", "g", labels=["a", "c"]).to_dict())) == {"a", "c"}

    def test_labels_int_auto_selects_n(self, df):
        # labels=int auto-picks that many (even-spread), no curation
        assert len(_text_values(add_labels(df, "x", "y", "g", labels=2).to_dict())) == 2

    def test_labels_int_deterministic(self, df):
        a = _text_values(add_labels(df, "x", "y", "g", labels=2).to_dict())
        b = _text_values(add_labels(df, "x", "y", "g", labels=2).to_dict())
        assert a == b

    def test_labels_rejects_bool(self, df):
        with pytest.raises(ValueError, match="not a bool"):
            add_labels(df, "x", "y", "g", labels=True)

    def test_domain_spans_full_df_when_labeling_subset(self, df):
        # even labeling one point, the pinned scale must span the full df (no axis clipping);
        # exactly ONE layer carries the pin ((1, 3) nices to itself, so the extent is unchanged)
        spec = add_labels(df, "x", "y", "g", labels=["a"]).to_dict()
        domains = [
            lyr["encoding"]["x"]["scale"]["domain"]
            for lyr in spec["layer"]
            if lyr.get("encoding", {}).get("x", {}).get("scale")
        ]
        assert domains == [[1.0, 3.0]]  # full extent, not the single labeled point's

    def test_default_domain_niced_to_round_bounds(self):
        # the inferred domain is the extent rounded OUTWARD to nice tick multiples (d3 nice), so
        # the pinned axes end on round numbers instead of the raw data extent
        df = pl.DataFrame({"x": [1.13, 2.7, 3.42], "y": [4.2, 6.1, 8.9], "g": ["a", "b", "c"]})
        spec = add_labels(df, "x", "y", "g").to_dict()
        pin = next(lyr["encoding"] for lyr in spec["layer"] if lyr["encoding"]["x"].get("scale"))
        assert pin["x"]["scale"]["domain"] == [1.0, 3.6]
        assert pin["y"]["scale"]["domain"] == [4.0, 9.0]

    def test_explicit_domain_used_exactly(self, df):
        # an explicit xDomain/yDomain is forced as given - no nice rounding
        spec = add_labels(df, "x", "y", "g", xDomain=(1.13, 3.42), yDomain=(0.95, 3.05)).to_dict()
        pin = next(lyr["encoding"] for lyr in spec["layer"] if lyr["encoding"]["x"].get("scale"))
        assert pin["x"]["scale"]["domain"] == [1.13, 3.42]
        assert pin["y"]["scale"]["domain"] == [0.95, 3.05]

    def test_fontsize_defaults_to_primary(self, df):
        theme(fontSize=9)  # labels use the primary fontSize
        spec = add_labels(df, "x", "y", "g").to_dict()
        sizes = {lyr["mark"]["fontSize"] for lyr in spec["layer"] if lyr["mark"]["type"] == "text"}
        assert sizes == {9}

    def test_preserves_base_axis_titles(self, df):
        # add_labels positions by alt.datum (no field), so it must not touch the base axis titles.
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
        svg = vlc.vegalite_to_svg(
            (base + add_labels(df, "x", "y", "g", xDomain=(1.0, 3.0), yDomain=(1.0, 3.0))).to_dict()
        )

        def rendered(t):
            return bool(re.search(r"<text[^>]*>[^<]*" + re.escape(t) + r"[^<]*</text>", svg))

        assert rendered("XT")
        assert rendered("YT")

    def test_read_filters_sidecars(self, tmp_path, df):
        import dysonsphere as ds

        ds.theme()
        base = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q")
        out = tmp_path / "c"
        ds.save(lambda: base + add_labels(df, "x", "y", "g"), str(out), format="json")
        frame = ds.read(str(out) + ".json", what="data")
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


class TestAddRule:
    def test_no_label_returns_chart(self):
        result = add_rule(0.5)
        assert isinstance(result, alt.Chart)

    def test_with_label_returns_layer_chart(self):
        result = add_rule(0.5, label="threshold")
        assert isinstance(result, alt.LayerChart)

    def test_multiple_values_returns_layer(self):
        # One datum layer per value (single-value stays a bare Chart, see test_no_label_returns_chart).
        result = add_rule([0.25, 0.5, 0.75])
        assert isinstance(result, alt.LayerChart)

    def test_multiple_values_with_labels_returns_layer(self):
        result = add_rule([0.25, 0.75], label=["low", "high"])
        assert isinstance(result, alt.LayerChart)

    def test_vertical_rule(self):
        result = add_rule(5.0, axis="x")
        assert isinstance(result, alt.Chart)

    def test_invalid_axis_raises(self):
        with pytest.raises(ValueError, match="axis"):
            add_rule(0.5, axis="z")

    def test_preserves_explicit_base_axis_titles(self):
        # Regression: a rule must not null the base chart's axis title (the datum-vs-field fix).
        import re

        import vl_convert as vlc

        base = (
            alt.Chart(pl.DataFrame({"a": [0.0, 1, 2], "b": [0.0, 1, 2]}))
            .mark_point()
            .encode(x=alt.X("a:Q", title="MyXTitle"), y=alt.Y("b:Q", title="MyYTitle"))
        )
        svg = vlc.vegalite_to_svg((base + add_rule(1.0, axis="x") + add_rule(1.0, axis="y")).to_dict())

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
        svg = vlc.vegalite_to_svg((base + add_rule(1.0, axis="x")).to_dict())
        texts = re.findall(r"<text[^>]*>([^<]+)</text>", svg)
        assert "weight" in texts
        assert not any("__" in t for t in texts)  # no leaked sidecar field name


class TestAddText:
    def test_single_annotation_returns_chart(self):
        assert isinstance(add_text("a", x=1.0, y=1.0), alt.Chart)

    def test_multiple_annotations_return_layer(self):
        # One datum layer per annotation (single stays a bare Chart).
        assert isinstance(add_text(["a", "b"], x=[1.0, 2.0], y=[1.0, 2.0]), alt.LayerChart)

    def test_preserves_base_axis_titles(self):
        # Regression: text annotations must not null the base chart's axis titles.
        import re

        import vl_convert as vlc

        base = (
            alt.Chart(pl.DataFrame({"a": [0.0, 1, 2], "b": [0.0, 1, 2]}))
            .mark_point()
            .encode(x=alt.X("a:Q", title="XT"), y=alt.Y("b:Q", title="YT"))
        )
        svg = vlc.vegalite_to_svg((base + add_text("hi", x=1.0, y=1.0)).to_dict())

        def rendered(t):
            return bool(re.search(r"<text[^>]*>[^<]*" + re.escape(t) + r"[^<]*</text>", svg))

        assert rendered("XT")
        assert rendered("YT")


class TestAddRuleDatum:
    """Facet-safe datum mode: add_rule(data=df) shares the base's frame and positions by datum."""

    @pytest.fixture
    def df(self):
        return pl.DataFrame({"g": ["A", "A", "B", "B"], "x": [1.0, 2, 3, 4], "value": [1.0, 2, 3, 4]})

    def test_datum_single_returns_chart(self, df):
        assert isinstance(add_rule(2.0, data=df), alt.Chart)

    def test_datum_multi_returns_layer(self, df):
        assert isinstance(add_rule([1.0, 3.0], data=df), alt.LayerChart)

    def test_datum_with_label_returns_layer(self, df):
        assert isinstance(add_rule(2.0, label="thr", data=df), alt.LayerChart)

    def test_datum_uses_datum_not_sidecar(self, df):
        import json

        spec = json.dumps(add_rule(2.0, data=df).to_dict())
        assert "__v" not in spec  # no field-based sidecar
        assert "__dysonsphere__" not in spec  # no internal sentinel dataset (shares the user's df)
        assert '"datum"' in spec  # positioned by a constant datum

    def test_datum_pandas_accepted(self, df):
        add_rule(2.0, data=df.to_pandas()).to_dict()  # ensure_polars handles pandas

    def test_datum_faceting_succeeds(self, df):
        base = alt.Chart(df).mark_point().encode(x="x:Q", y="value:Q")
        faceted = (base + add_rule(2.5, label="thr", data=df)).facet(column="g:N")
        assert isinstance(faceted, alt.FacetChart)
        faceted.to_dict()  # compiles without the shared-data facet error

    def test_default_mode_not_facetable(self, df):
        # Contrast: the data-backed default cannot be faceted — the limitation datum mode fixes.
        base = alt.Chart(df).mark_point().encode(x="x:Q", y="value:Q")
        with pytest.raises(ValueError, match="Facet charts require data"):
            (base + add_rule(2.5)).facet(column="g:N")


class TestAddTextDatum:
    """Facet-safe datum mode for add_text(data=df)."""

    @pytest.fixture
    def df(self):
        return pl.DataFrame({"g": ["A", "A", "B", "B"], "cat": ["X", "Y", "X", "Y"], "value": [1.0, 2, 3, 4]})

    def test_datum_single_returns_chart(self, df):
        assert isinstance(add_text("hi", x=1.0, y=2.0, data=df), alt.Chart)

    def test_datum_multi_returns_layer(self, df):
        assert isinstance(add_text(["a", "b"], x=["X", "Y"], y=[1.0, 2.0], data=df), alt.LayerChart)

    def test_datum_uses_datum_not_sidecar(self, df):
        import json

        spec = json.dumps(add_text("hi", x="X", y=2.0, data=df).to_dict())
        assert "__text" not in spec and "__dysonsphere__" not in spec  # no sidecar
        assert '"datum"' in spec and '"value": "hi"' in spec  # datum position + value text

    def test_datum_faceting_succeeds(self, df):
        base = alt.Chart(df).mark_point().encode(x="cat:N", y="value:Q")
        faceted = (base + add_text("★", x="X", y=3.0, data=df)).facet(column="g:N")
        assert isinstance(faceted, alt.FacetChart)
        faceted.to_dict()

    def test_datum_pixel_preset(self, df):
        base = alt.Chart(df).mark_point().encode(x="cat:N", y="value:Q")
        (base + add_text("n", position="topRight", data=df)).facet(column="g:N").to_dict()

    def test_default_not_facetable(self, df):
        base = alt.Chart(df).mark_point().encode(x="cat:N", y="value:Q")
        with pytest.raises(ValueError, match="Facet charts require data"):
            (base + add_text("hi", x="X", y=2.0)).facet(column="g:N")


class TestAddShadeDatum:
    """Facet-safe datum mode for add_shade(positions=..., data=df); band mode is unsupported."""

    @pytest.fixture
    def df(self):
        return pl.DataFrame({"g": ["A", "A", "B", "B"], "x": [1.0, 2, 3, 4], "value": [1.0, 2, 3, 4]})

    def test_datum_numeric_faceting_succeeds(self, df):
        base = alt.Chart(df).mark_point().encode(x="x:Q", y="value:Q")
        faceted = (base + add_shade(positions=[(1.5, 2.5)], axis="x", data=df)).facet(column="g:N")
        assert isinstance(faceted, alt.FacetChart)
        faceted.to_dict()

    def test_datum_uses_datum_not_sidecar(self, df):
        import json

        spec = json.dumps(add_shade(positions=[(1.5, 2.5)], axis="x", data=df).to_dict())
        assert "__xs" not in spec and "__dysonsphere__" not in spec  # no sidecar fields
        assert '"datum"' in spec

    def test_band_mode_with_data_raises(self, df):
        with pytest.raises(ValueError, match="positions mode only"):
            add_shade(["A", "B"], "g", data=df)

    def test_default_not_facetable(self, df):
        base = alt.Chart(df).mark_point().encode(x="x:Q", y="value:Q")
        with pytest.raises(ValueError, match="Facet charts require data"):
            (base + add_shade(positions=[(1.5, 2.5)], axis="x")).facet(column="g:N")

    def test_default_preserves_base_axis_titles(self, df):
        # Regression: a shade's data-range rect must not null the base chart's axis titles.
        import re

        import vl_convert as vlc

        base = alt.Chart(df).mark_point().encode(x=alt.X("x:Q", title="XT"), y=alt.Y("value:Q", title="YT"))
        svg = vlc.vegalite_to_svg((base + add_shade(positions=[((1.0, 2.0), (1.0, 2.0))], axis="both")).to_dict())

        def rendered(t):
            return bool(re.search(r"<text[^>]*>[^<]*" + re.escape(t) + r"[^<]*</text>", svg))

        assert rendered("XT")
        assert rendered("YT")
