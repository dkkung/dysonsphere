import altair as alt
import polars as pl
import pytest

from dysonsphere import assemble
from dysonsphere.theme import _opt, theme


def _no_marker(spec):
    """Drop the label marker so two equivalent member forms compare equal."""
    if isinstance(spec, dict):
        marker = "__dsfigure_"  # label and blank counters both vary between calls
        return {k: _no_marker(v) for k, v in spec.items() if not (k == "name" and str(v).startswith(marker))}
    return [_no_marker(v) for v in spec] if isinstance(spec, list) else spec


def _chart():
    df = pl.DataFrame({"g": ["A"] * 6 + ["B"] * 6, "v": [1.0 + i * 0.1 for i in range(12)]})
    return alt.Chart(df).mark_point().encode(x="g:N", y="v:Q")


class TestAssembleSizing:
    """Each member is built while the theme genuinely says its size."""

    def test_derived_options_recompute_at_the_member_size(self):
        # The reason assemble re-runs theme() instead of poking alt.theme.options: markSize and
        # the corner/arc radii derive from min(width, height) and must follow the member.
        theme()
        seen = []

        def build():
            seen.append(_opt("markSize"))
            return _chart()

        assemble([(build, 200, 200), (build, 100, 100)])
        assert seen == [20.0, 10.0]
        assert _opt("markSize") == 10.0, "must restore"

    def test_stamps_width_and_height_per_member(self):
        theme()
        spec = assemble([(_chart, 200, 150), (_chart, 60, 40)]).to_dict()
        first, second = spec["hconcat"]
        assert (first["width"], first["height"]) == (200, 150)
        assert (second["width"], second["height"]) == (60, 40)

    def test_bare_builder_uses_the_theme_size(self):
        theme(width=123, height=77)
        spec = assemble([_chart, (_chart, 60, 40)]).to_dict()
        assert "width" not in spec["hconcat"][0], "no stamp - it inherits config.view"
        assert spec["hconcat"][1]["width"] == 60
        theme()

    def test_prebuilt_chart_passes_through(self):
        theme()
        prebuilt = _chart().properties(width=42, height=17)
        spec = assemble([prebuilt, (_chart, 60, 40)]).to_dict()
        assert (spec["hconcat"][0]["width"], spec["hconcat"][0]["height"]) == (42, 17)

    def test_nested_assemble_result_is_a_valid_member(self):
        theme()
        row = assemble([(_chart, 60, 40), (_chart, 60, 40)])
        spec = assemble([[row], [(_chart, 90, 40)]]).to_dict()
        assert "hconcat" in spec["vconcat"][0]

    def test_restores_on_exception(self):
        theme()

        def boom():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            assemble([(boom, 999, 999)])
        assert _opt("width") == 100

    def test_restores_complete_theme_state_on_exception(self):
        from dysonsphere.palettes import colors
        from dysonsphere.theme import _active_args

        custom = ["#123456", "#abcdef"]
        theme(dark=True, transparent=False, palette=custom, fontSize=9)
        before_options = dict(alt.theme.options)
        before_args = _active_args()
        before_colors = dict(colors)

        with pytest.raises(RuntimeError, match="boom"):
            assemble([(lambda: (_ for _ in ()).throw(RuntimeError("boom")), 999, 999)])

        assert alt.theme.options == before_options
        assert _active_args() == before_args
        assert colors == before_colors
        theme()

    def test_preserves_explicitly_set_theme_args(self):
        # assemble rebuilds from theme()'s call args, so a caller's explicit settings survive.
        theme(width=300, fontSize=9)
        seen = {}

        def build():
            seen["fontSize"] = _opt("fontSize")
            return _chart()

        assemble([(build, None, 200)])
        assert seen["fontSize"] == 9
        assert _opt("width") == 300 and _opt("fontSize") == 9
        theme()


class TestAssembleLayout:
    def test_flat_list_is_one_row(self):
        theme()
        spec = assemble([(_chart, 60, 40), (_chart, 60, 40)]).to_dict()
        assert "hconcat" in spec and "vconcat" not in spec

    def test_nested_lists_are_rows(self):
        theme()
        spec = assemble([[(_chart, 60, 40), (_chart, 60, 40)], [(_chart, 60, 40)]]).to_dict()
        assert len(spec["vconcat"]) == 2
        assert len(spec["vconcat"][0]["hconcat"]) == 2

    def test_single_member_returns_the_chart_itself(self):
        theme()
        spec = assemble([(_chart, 60, 40)]).to_dict()
        assert "hconcat" not in spec and "vconcat" not in spec
        assert spec["width"] == 60

    def test_scalar_spacing_applies_to_both_directions(self):
        theme()
        spec = assemble([[(_chart, 60, 40), (_chart, 60, 40)], [(_chart, 60, 40)]], spacing=12).to_dict()
        assert spec["spacing"] == 12
        assert spec["vconcat"][0]["spacing"] == 12

    def test_dict_spacing_sets_each_direction(self):
        theme()
        spec = assemble(
            [[(_chart, 60, 40), (_chart, 60, 40)], [(_chart, 60, 40)]],
            spacing={"row": 40, "column": 10},
        ).to_dict()
        assert spec["spacing"] == 40
        assert spec["vconcat"][0]["spacing"] == 10

    def test_legends_survive_composition(self):
        # hconcat defaults legends to shared and DROPS them when the panels' color scales
        # cannot merge, so assemble resolves color independently. Rendered, not inspected:
        # the spec keeps both encodings either way - only the render shows the loss.
        import re

        import vl_convert as vlc

        theme()

        def colored(pal):
            df = pl.DataFrame({"g": ["A", "B"], "v": [1.0, 2.0]})
            return lambda: (
                alt.Chart(df).mark_bar().encode(x="g:N", y="v:Q", color=alt.Color("g:N", scale=alt.Scale(range=pal)))
            )

        figure = assemble([(colored(["#111111", "#222222"]), 60, 40), (colored(["#888888", "#999999"]), 60, 40)])
        assert re.findall("role-legend", vlc.vegalite_to_svg(figure.to_json())), "legends dropped by the concat"


class TestFigureLabels:
    def test_fourth_element_labels_the_chart(self):
        theme()
        spec = assemble([(_chart, 60, 40, "a"), (_chart, 60, 40)]).to_dict()
        first, second = spec["hconcat"]
        assert first["title"]["text"] == "a"
        assert first["vconcat"][0]["width"] == 60, "the label rides a wrapper, chart size intact"
        assert "title" not in second, "a member without a fourth element gets no label"

    def test_text_is_verbatim(self):
        theme()
        spec = assemble([(_chart, 60, 40, "B")]).to_dict()
        assert spec["title"]["text"] == "B", "no case transformation"

    def test_anchors_top_left_in_bold_by_default(self):
        theme()
        title = assemble([(_chart, 60, 40, "a")]).to_dict()["title"]
        assert title["anchor"] == "start"
        assert (title["fontSize"], title["fontWeight"]) == (8, 700)

    def test_color_is_left_to_the_theme_by_default(self):
        # config.title.color is darkmode-aware and resolved when the spec is written, so a
        # save() across both backgrounds gets the right ink without a callable.
        theme()
        assert "color" not in assemble([(_chart, 60, 40, "a")]).to_dict()["title"]
        spec = assemble([(_chart, 60, 40, "a")], labelColor="#ff0000").to_dict()
        assert spec["title"]["color"] == "#ff0000"

    def test_padding_offsets_the_label(self):
        theme()
        default = assemble([(_chart, 60, 40, "a")]).to_dict()["title"]
        assert (default["dx"], default["dy"]) == (-5, 0), "held off the chart like axisOffset"
        one = assemble([(_chart, 60, 40, "a")], labelOffset=3).to_dict()["title"]
        assert (one["dx"], one["dy"]) == (3, 3)
        two = assemble([(_chart, 60, 40, "a")], labelOffset=(-4, 2)).to_dict()["title"]
        assert (two["dx"], two["dy"]) == (-4, 2)

    def test_chart_keeps_its_own_title(self):
        # the label rides a wrapper, so it does not consume the chart's title slot
        theme()

        def titled():
            return _chart().properties(title="Real title")

        spec = assemble([(titled, 60, 40, "a")]).to_dict()
        assert spec["title"]["text"] == "a"
        assert spec["vconcat"][0]["title"] == "Real title"

    def test_anchors_to_the_whole_chart_not_the_plot_area(self):
        # frame="bounds" measures the full bounding box, so the label clears the y-axis
        # labels; frame="group" would stop at the plot area (measured: x=44 vs x=6).
        theme()
        assert assemble([(_chart, 60, 40, "a")]).to_dict()["title"]["frame"] == "bounds"


class TestDictMembers:
    def test_dict_member_matches_the_tuple_form(self):
        theme()
        as_tuple = assemble([(_chart, 60, 40, "a")]).to_dict()
        as_dict = assemble([{"chart": _chart, "width": 60, "height": 40, "label": "a"}]).to_dict()
        assert _no_marker(as_dict) == _no_marker(as_tuple)

    def test_only_chart_is_required(self):
        theme(width=123)
        spec = assemble([{"chart": _chart}]).to_dict()
        assert "width" not in spec, "no stamp - it inherits config.view"
        theme()

    def test_dict_takes_a_prebuilt_chart(self):
        theme()
        spec = assemble([{"chart": _chart().properties(width=42, height=17), "label": "a"}]).to_dict()
        assert spec["title"]["text"] == "a"
        assert spec["vconcat"][0]["width"] == 42

    def test_unknown_key_raises(self):
        theme()
        with pytest.raises(ValueError, match="unknown"):
            assemble([{"chart": _chart, "wdith": 60}])

    def test_missing_chart_key_raises(self):
        theme()
        with pytest.raises(ValueError, match="needs a 'chart' key"):
            assemble([{"width": 60, "height": 40}])

    def test_sizing_a_prebuilt_chart_raises(self):
        # its derived pixel values are already baked, so a size could not be honored
        theme()
        with pytest.raises(ValueError, match="already-built chart"):
            assemble([{"chart": _chart(), "width": 60, "height": 40}])

    def test_wrong_length_tuple_raises(self):
        theme()
        with pytest.raises(ValueError, match="member tuple must be"):
            assemble([(_chart, 60)])


class TestLabelAlignment:
    """Labels in a column line up exactly, whatever each member's axis margin is."""

    @staticmethod
    def _label_x(chart, tmp_path):
        import re
        import xml.etree.ElementTree as ET

        from dysonsphere.export import _render_fixed_svg

        svg = _render_fixed_svg(chart, str(tmp_path / "f.svg"))
        root = ET.fromstring(svg.split("\n", 1)[1])
        found = {}

        def walk(node, x, y):
            m = re.search(r"translate\(([-\d.]+)[, ]+([-\d.]+)\)", node.get("transform") or "")
            if m:
                x, y = x + float(m.group(1)), y + float(m.group(2))
            if node.tag == "{http://www.w3.org/2000/svg}text" and (node.text or "").strip() in ("a", "c"):
                found[node.text.strip()] = round(x + float(node.get("x") or 0), 2)
            for child in node:
                walk(child, x, y)

        walk(root, 0.0, 0.0)
        return found

    @staticmethod
    def _wide():
        df = pl.DataFrame({"x": [1, 2, 3], "y": [100000, 300000, 200000]})
        return alt.Chart(df).mark_line().encode(x=alt.X("x:Q"), y=alt.Y("y:Q", title="A long y axis title"))

    def test_differing_axis_margins_align(self, tmp_path):
        # Vega aligns members by PLOT area, but a label anchors to its member's bounding box -
        # so without the fixer the narrower-margin member's label is indented (26.6 vs 5.2).
        theme()
        figure = assemble([[(_chart, 100, 60, "a")], [(self._wide, 100, 60, "c")]], spacing={"row": 20})
        found = self._label_x(figure, tmp_path)
        assert found["a"] == found["c"]

    def test_blank_aligns_with_a_real_chart(self, tmp_path):
        theme()
        figure = assemble([[(None, 100, 60, "a")], [(self._wide, 100, 60, "c")]], spacing={"row": 20})
        found = self._label_x(figure, tmp_path)
        assert found["a"] == found["c"]


class TestProvenance:
    """An assembled figure must stay honest about what it does and does not cover."""

    def test_figure_markers_are_not_the_statistics_channel(self):
        # sharing the statistics prefix would both feed junk hashes to the record scan and get
        # the markers stripped from written output, which broke ds.load() parity
        from dysonsphere._statistics import _MARKER_PREFIX
        from dysonsphere.assembly import _FIGURE_PREFIX

        assert not _FIGURE_PREFIX.startswith(_MARKER_PREFIX)

    def test_labels_survive_a_load_round_trip(self, tmp_path):
        # ds.load() promises parity, and alignment needs the markers the writer used to strip
        import json

        import dysonsphere as ds

        theme()
        figure = assemble([[(_chart, 60, 40, "a")], [(_chart, 60, 40, "c")]])
        ds.save(figure, str(tmp_path / "fig"), format="json", background="light")
        spec = json.loads((tmp_path / "fig.json").read_text())
        assert "__dsfigure_label_" in json.dumps(spec)
        reloaded = ds.load(str(tmp_path / "fig.json"), raw=True)
        assert "__dsfigure_label_" in json.dumps(reloaded)


class TestAssemblyExportMode:
    @staticmethod
    def _figure(seen=None):
        # A sized outer builder invokes assemble() while its temporary theme is active,
        # producing genuinely nested temporary-theme scopes.
        def inner_chart():
            if seen is not None:
                seen.append(("inner", _opt("width"), _opt("height"), _opt("markSize"), _opt("dark")))
            return _chart()

        def outer_builder():
            if seen is not None:
                seen.append(("outer", _opt("width"), _opt("height"), _opt("markSize"), _opt("dark")))
            return assemble([(inner_chart, 80, 50)])

        return assemble([(outer_builder, 120, 70)])

    @pytest.mark.parametrize("original_darkmode", [False, True])
    @pytest.mark.parametrize("backgrounds", [["light", "dark"], ["dark", "light"]])
    def test_save_variants_keep_requested_mode_and_restore_state(
        self, tmp_path, monkeypatch, original_darkmode, backgrounds
    ):
        import json
        import re

        from PIL import Image

        import dysonsphere as ds
        from dysonsphere.palettes import colors
        from dysonsphere.theme import _active_args

        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text(
            '[ocean]\ncategoryPalette = "local"\n[palettes]\nlocal = ["#123456", "#abcdef"]\n'
        )
        theme(style="ocean", dark=original_darkmode, transparent=True, tickDirection="in")
        before_options = dict(alt.theme.options)
        before_args = _active_args()
        before_colors = dict(colors)
        ds.save(
            lambda: self._figure(),
            tmp_path / "assembled",
            format=["svg", "png", "json"],
            background=backgrounds,
            transparent=False,
            ppi=72,
        )

        for mode, ink, page in (("light", "black", (255, 255, 255)), ("dark", "white", (0, 0, 0))):
            stem = tmp_path / f"assembled_{mode}"
            spec = json.loads(stem.with_suffix(".json").read_text())
            assert spec["usermeta"]["dysonsphere"]["theme"]["dark"] is (mode == "dark")
            assert spec["usermeta"]["dysonsphere"]["theme"]["tickDirection"] == "in"
            assert spec["config"]["axis"]["labelColor"] == ink
            svg = stem.with_suffix(".svg").read_text()
            assert re.search(rf'<text[^>]*fill="{ink}"[^>]*>[12]</text>', svg), "axis tick ink must match the mode"
            assert spec["config"]["range"]["category"] == ["#123456", "#abcdef"]
            with Image.open(stem.with_suffix(".png")) as image:
                assert image.convert("RGB").getpixel((0, 0)) == page
        assert alt.theme.options == before_options
        assert _active_args() == before_args
        assert colors == before_colors

    def test_show_uses_active_mode_and_keeps_sized_geometry(self):
        import re
        from typing import cast

        import dysonsphere as ds

        theme(dark=True, transparent=False)
        before = dict(alt.theme.options)
        seen = []
        svg = cast(str, ds.show(lambda: self._figure(seen)).data)
        assert 'fill="white"' in svg
        assert re.search(r'<rect width="\d+" height="\d+" fill="black"', svg)
        assert seen == [("outer", 120, 70, 7.0, True), ("inner", 80, 50, 5.0, True)]
        assert alt.theme.options == before

    def test_transparent_save_keeps_alpha_and_dark_metadata(self, tmp_path):
        import json

        from PIL import Image

        import dysonsphere as ds

        theme(dark=False)
        ds.save(lambda: self._figure(), tmp_path / "transparent", format=["png", "json"], background="dark")
        spec = json.loads((tmp_path / "transparent.json").read_text())
        assert spec["usermeta"]["dysonsphere"]["theme"]["dark"] is True
        with Image.open(tmp_path / "transparent.png") as image:
            assert image.convert("RGBA").getchannel("A").getpixel((0, 0)) == 0

    def test_save_builder_error_restores_complete_theme_state(self, tmp_path):
        import dysonsphere as ds
        from dysonsphere.palettes import colors
        from dysonsphere.theme import _active_args

        theme(dark=False, transparent=True, categoryPalette=["#123456", "#abcdef"])
        before_options = dict(alt.theme.options)
        before_args = _active_args()
        before_colors = dict(colors)

        def fail():
            return assemble([(lambda: (_ for _ in ()).throw(RuntimeError("boom")), 120, 70)])

        with pytest.raises(RuntimeError, match="boom"):
            ds.save(fail, tmp_path / "error", format="json", background="dark")
        assert alt.theme.options == before_options
        assert _active_args() == before_args
        assert colors == before_colors

    def test_sized_builder_before_explicit_theme_restores_empty_options(self, monkeypatch):
        monkeypatch.setattr(alt.theme, "options", {})
        figure = assemble([(_chart, 80, 50)])
        assert figure._kwds["width"] == 80
        assert alt.theme.options == {}


class TestBlankSlots:
    def test_none_reserves_space(self):
        theme()
        spec = assemble([(None, 120, 80), (_chart, 60, 40)]).to_dict()
        blank = spec["hconcat"][0]
        assert (blank["width"], blank["height"]) == (120, 80)
        assert blank["mark"]["opacity"] == 0

    def test_outline_matches_the_axes(self):
        theme()
        view = assemble([(None, 120, 80)]).to_dict()["view"]
        assert view["strokeWidth"] == _opt("axisWidth")
        assert view["strokeDash"] == [0, 0], "solid - config.rule's dash must not reach it"
        assert view["stroke"] == "black"

    def test_slot_is_filled_so_it_can_be_selected(self):
        # a transparent slot is nothing to grab in a vector editor
        theme()
        assert assemble([(None, 120, 80)]).to_dict()["view"]["fill"] == "white"

    def test_outline_and_fill_follow_darkmode(self):
        theme(dark=True)
        view = assemble([(None, 120, 80)]).to_dict()["view"]
        assert (view["stroke"], view["fill"]) == ("white", "black")
        theme()

    def test_explicit_chart_fill_wins(self):
        theme(chartFill="#eeeeee")
        assert assemble([(None, 120, 80)]).to_dict()["view"]["fill"] == "#eeeeee"
        theme()

    def test_blank_can_be_labelled(self):
        theme()
        spec = assemble([(None, 120, 80, "a")]).to_dict()
        assert spec["title"]["text"] == "a"

    def test_blank_dict_form(self):
        theme()
        as_tuple = assemble([(None, 120, 80, "a")]).to_dict()
        as_dict = assemble([{"chart": None, "width": 120, "height": 80, "label": "a"}]).to_dict()
        assert _no_marker(as_dict) == _no_marker(as_tuple)

    def test_blank_data_is_internal(self, tmp_path):
        # a reserved slot is not part of the figure's data of record
        import dysonsphere as ds

        theme()
        ds.save(assemble([(None, 120, 80), (_chart, 60, 40)]), str(tmp_path / "fig"), format="json")
        frame = ds.metadata.read(str(tmp_path / "fig.json"), what="data")
        assert list(frame.columns) == ["g", "v"], "the blank must not surface as a user frame"


class TestAssembleErrors:
    def test_empty_members(self):
        theme()
        with pytest.raises(ValueError, match="at least one member"):
            assemble([])

    def test_empty_row(self):
        theme()
        with pytest.raises(ValueError, match="rows cannot be empty"):
            assemble([[(_chart, 60, 40)], []])

    def test_mixed_rows_and_bare_members(self):
        theme()
        with pytest.raises(ValueError, match="nest every row"):
            assemble([[(_chart, 60, 40)], (_chart, 60, 40)])

    def test_unknown_spacing_key(self):
        theme()
        with pytest.raises(ValueError, match="row.*column"):
            assemble([(_chart, 60, 40)], spacing={"vertical": 10})


class TestMarkerDeterminism:
    """Two identical figures must produce identical markers - a process-wide counter did not."""

    def _figure(self, blank=False):
        df = pl.DataFrame({"g": ["A", "B"], "v": [1.0, 2.0]})
        bar = lambda: alt.Chart(df).mark_bar().encode(x="g:N", y="v:Q")  # noqa: E731
        row = [(bar, 120, 90, "a"), None if blank else (bar, 120, 90, "b")]
        return assemble([row])

    def _markers(self, chart):
        found: list[str] = []

        def walk(node):
            if isinstance(node, dict):
                name = node.get("name")
                if isinstance(name, str) and name.startswith("__dsfigure_"):
                    found.append(name)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(chart.to_dict())
        return found

    def test_identical_figures_get_identical_markers(self):
        # The counter used to run process-wide, so the second call emitted label_3/label_4 for
        # the same figure - changing its spec, its checksum, and its exported bytes.
        assert self._markers(self._figure()) == self._markers(self._figure())

    def test_repeated_builds_are_byte_identical_when_pinned(self, tmp_path, monkeypatch):
        # SOURCE_DATE_EPOCH promises repeated saves of an unchanged figure are byte-identical.
        # Assembled figures broke that promise.
        import dysonsphere as ds

        monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
        ds.save(self._figure(), str(tmp_path / "r1"), format="json", background=["light"])
        ds.save(self._figure(), str(tmp_path / "r2"), format="json", background=["light"])
        assert (tmp_path / "r1.json").read_text() == (tmp_path / "r2.json").read_text()

    def test_markers_stay_unique_within_one_figure(self):
        # Uniqueness is not cosmetic: Vega rejects duplicate view names outright.
        import vl_convert as vlc

        chart = self._figure(blank=True)
        markers = self._markers(chart)
        assert markers and len(markers) == len(set(markers))
        vlc.vegalite_to_svg(chart.to_dict())  # raises if Vega rejects the names

    def test_a_nested_figure_is_renumbered_by_the_outer_call(self):
        # Renumbering happens on the finished figure, so an assemble() result nested inside
        # another cannot collide with the outer figure's own markers.
        df = pl.DataFrame({"g": ["A", "B"], "v": [1.0, 2.0]})
        bar = lambda: alt.Chart(df).mark_bar().encode(x="g:N", y="v:Q")  # noqa: E731
        inner = assemble([[(bar, 100, 80, "x"), (bar, 100, 80, "y")]])
        outer = assemble([[inner, (bar, 100, 80, "z")]])
        markers = self._markers(outer)
        assert len(markers) == 3
        assert len(set(markers)) == 3, "nested markers must not collide with the outer figure's"
