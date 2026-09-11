from typing import Any

import altair as alt
import numpy as np
import polars as pl
import pytest

from dysonsphere.marks import mark_strip
from dysonsphere.multilabel import _multilabel_layer, add_multilabel
from dysonsphere.theme import theme


@pytest.fixture(autouse=True)
def default_theme():
    theme(dashedWidth=[2, 2])


CATS = ["A", "B", "C", "D"]
GROUPS = {"Row": [True, False, True, False]}

ML_CATS = ["A", "B", "C"]
ML_GROUPS = {"Row 1": [True, False, True]}


class TestSpans:
    def test_line_style_height_larger_than_no_spans(self):
        theme(width=100)
        base = _multilabel_layer(GROUPS, CATS)
        with_spans = _multilabel_layer(GROUPS, CATS, span={"": ["A", "B"]})
        assert with_spans._kwds["height"] > base._kwds["height"]

    def test_bracket_style_height_larger_than_line(self):
        theme(width=100)
        line = _multilabel_layer(GROUPS, CATS, span={"": ["A", "B"]})
        bracket = _multilabel_layer(
            GROUPS,
            CATS,
            span={"": ["A", "B"]},
            spanBracketStyle="bracket",
            spanBracketReverse=False,
        )
        assert bracket._kwds["height"] > line._kwds["height"]

    def test_label_increases_height(self):
        theme(width=100)
        no_lbl = _multilabel_layer(GROUPS, CATS, span={"": ["A", "B"]})
        with_lbl = _multilabel_layer(GROUPS, CATS, span={"Group 1": ["A", "B"]})
        assert with_lbl._kwds["height"] > no_lbl._kwds["height"]

    def test_implicit_span_matches_explicit(self):
        theme(width=100)
        explicit = _multilabel_layer(GROUPS, CATS, span={"G": ["A", "B", "C"]})
        implicit = _multilabel_layer(GROUPS, CATS, span={"G": ["A", "C"]})
        assert explicit._kwds["height"] == pytest.approx(implicit._kwds["height"])

    def test_span_label_position_top(self):
        theme(width=100)
        ann = _multilabel_layer(GROUPS, CATS, span={"G1": ["A", "B"]}, spanLabelPosition="top")
        assert isinstance(ann, alt.LayerChart)

    def test_span_reverse(self):
        theme(width=100)
        rev = _multilabel_layer(
            GROUPS,
            CATS,
            span={"": ["A", "B"]},
            spanBracketStyle="bracket",
            spanBracketReverse=True,
        )
        line = _multilabel_layer(GROUPS, CATS, span={"": ["A", "B"]})
        assert rev._kwds["height"] == pytest.approx(line._kwds["height"])

    def test_multiple_spans(self):
        theme(width=100)
        ann = _multilabel_layer(
            GROUPS,
            CATS,
            span={"Group 1": ["A", "B"], "Group 2": ["C", "D"]},
        )
        assert isinstance(ann, alt.LayerChart)

    def test_list_of_dicts_multiple_unlabeled(self):
        theme(width=100)
        ann = _multilabel_layer(
            GROUPS,
            CATS,
            span=[{None: ["A", "B"]}, {None: ["C", "D"]}],
        )
        assert isinstance(ann, alt.LayerChart)

    def test_invalid_cat_raises(self):
        theme(width=100)
        with pytest.raises(ValueError, match="not in categories"):
            _multilabel_layer(GROUPS, CATS, span={"G": ["A", "Z"]})

    def test_empty_span_raises(self):
        theme(width=100)
        with pytest.raises(ValueError, match="must not be empty"):
            _multilabel_layer(GROUPS, CATS, span={"G": []})

    def test_invalid_bracket_style_raises(self):
        theme(width=100)
        with pytest.raises(ValueError, match="spanBracketStyle"):
            _multilabel_layer(GROUPS, CATS, span={"": ["A", "B"]}, spanBracketStyle="arrow")

    def test_invalid_label_position_raises(self):
        theme(width=100)
        with pytest.raises(ValueError, match="spanLabelPosition"):
            _multilabel_layer(GROUPS, CATS, span={"": ["A", "B"]}, spanLabelPosition="left")

    def test_explicit_span_gap_changes_height(self):
        theme(width=100)
        default_gap = _multilabel_layer(GROUPS, CATS, span={"": ["A", "B"]})
        large_gap = _multilabel_layer(GROUPS, CATS, span={"": ["A", "B"]}, spanGap=20)
        assert large_gap._kwds["height"] > default_gap._kwds["height"]

    def test_defer_cat_label_below_spans(self):
        theme(width=100)
        no_span = _multilabel_layer(GROUPS, CATS, categoryLabel=True, categoryLabelPosition="bottom")
        with_span = _multilabel_layer(
            GROUPS,
            CATS,
            categoryLabel=True,
            categoryLabelPosition="bottom",
            span={"G": ["A", "B"]},
        )
        assert with_span._kwds["height"] > no_span._kwds["height"]


class TestRowSpacingUnderViewPadding:
    """The row centres are precomputed pixels - viewPadding must not compress them."""

    def _row_ys(self):
        import re
        import xml.etree.ElementTree as ET

        import vl_convert as vlc

        from dysonsphere.utils import _apply_spec_fixes

        ns = "{http://www.w3.org/2000/svg}"
        cats = ["A", "B", "C"]
        df = pl.DataFrame({"g": cats * 4, "v": [1.0, 2.0, 3.0] * 4})
        base = alt.Chart(df).mark_point().encode(alt.X("g:N", title=None), alt.Y("v:Q", title="v"))
        groups = {"first": [True, False, True], "second": [False, True, True]}
        spec = _apply_spec_fixes(add_multilabel(base, groups, cats).to_dict())
        root = ET.fromstring(vlc.vegalite_to_svg(spec))
        ys = []
        for t in root.iter(f"{ns}text"):
            if (t.text or "").strip() in groups:
                m = re.search(r"translate\(([-\d.]+),\s*([-\d.]+)\)", t.get("transform") or "")
                if m:
                    ys.append(float(m.group(2)))
        return sorted(ys)

    def test_row_gap_matches_with_and_without_padding(self):
        theme(viewPadding=False)
        without = self._row_ys()
        theme()  # default: padding is emitted on every plot
        with_padding = self._row_ys()
        assert len(without) == 2
        assert with_padding == pytest.approx(without), (with_padding, without)


class TestAddMultilabel:
    def test_accepts_plain_chart(self):
        theme(width=100)
        df = pl.DataFrame({"g": ML_CATS * 5, "v": range(15)})
        base = alt.Chart(df).mark_boxplot().encode(x=alt.X("g:N", sort=ML_CATS), y=alt.Y("v:Q"))
        result = add_multilabel(base, ML_GROUPS, categories=ML_CATS)
        assert isinstance(result, alt.VConcatChart)

    def test_accepts_layer_chart(self):
        theme(width=100)
        rng = np.random.default_rng(0)
        df = pl.DataFrame({"g": ML_CATS * 20, "v": rng.normal(0, 1, 60).tolist()})
        strip = mark_strip(df, "g", "v", ML_CATS)
        assert isinstance(strip, alt.LayerChart)
        result = add_multilabel(strip, ML_GROUPS, categories=ML_CATS)
        assert isinstance(result, alt.VConcatChart)

    def test_preserves_hidden_axes(self):
        # Regression: a layer's explicit axis=None (e.g. mark_violin's internal pixel-x
        # layers) must STAY None - replacing it with Axis(labels=False) re-enables the
        # domain line and ticks, drawing a phantom axis above the chart.
        from dysonsphere.marks import mark_violin

        theme(width=100)
        rng = np.random.default_rng(0)
        df = pl.DataFrame({"g": ML_CATS * 20, "v": rng.normal(0, 1, 60).tolist()})
        violin = mark_violin(df, "g", "v", ML_CATS)
        spec = add_multilabel(violin, ML_GROUPS, categories=ML_CATS).to_dict()
        chart_panel = spec["vconcat"][0]
        hidden = [lyr for lyr in chart_panel["layer"] if lyr.get("encoding", {}).get("x", {}).get("field") == "__x"]
        assert hidden and all(lyr["encoding"]["x"].get("axis") is None for lyr in hidden)

    def test_accepts_concat_chart(self):
        # A vconcat stack (e.g. western_blot's image strips): _strip_x_labels recurses into the
        # panels, so the table lands below the whole stack. The param annotation includes the
        # concat types, so this is a first-class call (no type-ignore needed).
        theme(width=100)
        df = pl.DataFrame({"g": ML_CATS * 5, "v": range(15)})
        panel = alt.Chart(df).mark_boxplot().encode(x=alt.X("g:N", sort=ML_CATS), y="v:Q")
        stack = alt.vconcat(panel, panel)
        assert isinstance(stack, alt.VConcatChart)
        result = add_multilabel(stack, ML_GROUPS, categories=ML_CATS)
        assert isinstance(result, alt.VConcatChart)
        result.to_dict()  # would raise if the composition were malformed


class TestMultilabelLabelMap:
    def test_category_label_row_uses_display_names(self):
        import json

        chart = _multilabel_layer(
            {"C1": [True, False]},
            ["metadata_a", "metadata_b"],
            categoryLabel=True,
            labelMap={"metadata_a": "A!", "metadata_b": ["B", "two lines"]},
        )
        blob = json.dumps(chart.to_dict())
        assert "A!" in blob
        assert "B two lines" in blob  # list labels space-joined in the text row
        # raw values still present (they are the band-scale positions)
        assert "metadata_a" in blob


class TestMultilabelXOrder:
    def _x_domains(self, vg) -> list[list[str]]:
        found: list[list[str]] = []

        def walk(o):
            if isinstance(o, dict):
                for s in o.get("scales", []) or []:
                    if s.get("name") == "x" and isinstance(s.get("domain"), list):
                        found.append(s["domain"])
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)

        walk(vg)
        return found

    def test_shared_x_domain_follows_categories_not_alphabetical(self):
        # Regression: add_multilabel shares the x scale; without pinning the annotation's x
        # domain, resolve_scale(x="shared") re-sorted it alphabetically, so the strip's bars
        # rendered in a different order than the (unshared) colour scale - category colours
        # stopped matching their bars. Use a NON-alphabetical order to catch it.
        import vl_convert as vlc

        cats = ["USA", "Europe", "Japan"]  # not alphabetical
        df = pl.DataFrame({"g": [c for c in cats for _ in range(5)], "y": [float(i) for i in range(15)]})
        strip = mark_strip(df, "g", "y", cats)
        chart = add_multilabel(strip, categories=cats, showSampleSize=True, data=df, x="g")
        vg = vlc.vegalite_to_vega(chart.to_dict())
        domains = self._x_domains(vg)
        assert domains, "no resolved x domain found"
        for dom in domains:
            assert dom == cats, f"x domain {dom} did not preserve categories order {cats}"


class TestRowStylesListWithSampleSize:
    """A rowStyles LIST must survive the sample-size row that add_multilabel injects."""

    C = ["A", "B", "C"]
    GROUPS = {"a": [True, True, True], "b": [True, False, True]}

    def _df(self):
        return pl.DataFrame({"g": [c for c in self.C for _ in range(4)], "v": [float(i) for i in range(12)]})

    def _styles(self, spec_owner) -> dict[str, str]:
        """Map each row label to the mark type it rendered as (point == symbol style)."""
        spec = spec_owner.to_dict()
        panel = spec.get("vconcat", [spec])[-1]
        out: dict[str, str] = {}
        for layer in panel.get("layer", []):
            mark = layer.get("mark")
            mtype = mark.get("type") if isinstance(mark, dict) else mark
            src = layer.get("data", {}).get("name")
            for name, rows in spec.get("datasets", {}).items():
                if name != src:
                    continue
                for row in rows:
                    if "__value" in row:
                        out[row["__label"]] = "symbol" if mtype == "point" else "flat"
        return out

    def _with_n(self, **kwargs):
        df = self._df()
        return add_multilabel(
            mark_strip(df, "g", "v", self.C),
            self.GROUPS,
            categories=self.C,
            showSampleSize=True,
            data=df,
            x="g",
            **kwargs,
        )

    def test_list_follows_display_order_not_insertion_order(self):
        # Regression: the list was zipped against groups.keys() (insertion order) while
        # _multilabel_layer zips against row_order, so an explicit `order` inverted the styles.
        plain = _multilabel_layer(self.GROUPS, self.C, order=["b", "a"], rowStyles=["symbol", "plusminus"])
        with_n = self._with_n(order=["b", "a"], rowStyles=["symbol", "plusminus"])
        assert self._styles(plain) == {"b": "symbol", "a": "flat"}
        assert {k: v for k, v in self._styles(with_n).items() if k != "n ="} == self._styles(plain)

    def test_list_length_is_validated(self):
        # zip() truncated silently, so the check _multilabel_layer applies never fired.
        with pytest.raises(ValueError, match="rowStyles list has 1 entries but there are 2 rows"):
            self._with_n(rowStyles=["symbol"])
        with pytest.raises(ValueError, match="rowStyles list has 4 entries but there are 2 rows"):
            self._with_n(rowStyles=["symbol", "plusminus", "text", "text"])

    def test_list_without_order_is_unchanged(self):
        got = self._styles(self._with_n(rowStyles=["symbol", "plusminus"]))
        assert got["a"] == "symbol" and got["b"] == "flat"

    def test_dict_is_unchanged(self):
        got = self._styles(self._with_n(order=["b", "a"], rowStyles={"b": "symbol", "a": "plusminus"}))
        assert got["b"] == "symbol" and got["a"] == "flat"

    def test_sample_size_row_still_forced_to_text(self):
        assert self._styles(self._with_n(style="symbol", rowStyles=["symbol", "symbol"]))["n ="] == "flat"


class TestRowValueAngle:
    """Per-row text rotation and the per-row heights it needs."""

    TEXT_GROUPS = {"r1": ["1", "2", "3"], "r2": ["10", "20", "30"]}

    def _text_marks(self, layer) -> list[dict[str, Any]]:
        """Every content-text datum in the layer, with its __y and __angle."""
        spec = layer.to_dict()
        out: list[dict[str, Any]] = []
        for ds_ in spec.get("datasets", {}).values():
            for row in ds_:
                if "__angle" in row:
                    out.append(row)
        for sub in spec.get("layer", []):
            data = sub.get("data", {})
            for row in data.get("values", []) or []:
                if "__angle" in row:
                    out.append(row)
        return out

    def _row_y(self, layer, label: str) -> float:
        ys = {r["__y"] for r in self._text_marks(layer) if r["__label"] == label}
        assert len(ys) == 1, f"row {label!r} has non-unique y: {ys}"
        return ys.pop()

    def test_default_is_unrotated(self):
        layer = _multilabel_layer(self.TEXT_GROUPS, ML_CATS)
        assert {r["__angle"] for r in self._text_marks(layer)} == {0.0}

    def test_scalar_applies_to_every_row(self):
        layer = _multilabel_layer(self.TEXT_GROUPS, ML_CATS, rowValueAngle=-90)
        assert {r["__angle"] for r in self._text_marks(layer)} == {270.0}

    def test_dict_applies_per_row(self):
        layer = _multilabel_layer(self.TEXT_GROUPS, ML_CATS, rowValueAngle={"r2": -90})
        by_row = {r["__label"]: r["__angle"] for r in self._text_marks(layer)}
        assert by_row == {"r1": 0.0, "r2": 270.0}

    def test_list_applies_in_row_order(self):
        layer = _multilabel_layer(self.TEXT_GROUPS, ML_CATS, rowValueAngle=[0, 90])
        by_row = {r["__label"]: r["__angle"] for r in self._text_marks(layer)}
        assert by_row == {"r1": 0.0, "r2": 90.0}

    def test_rotated_row_grows_taller(self):
        groups = {"r1": ["1", "2", "3"], "r2": ["1.98", "6.67", "4.44"]}
        flat = _multilabel_layer(groups, ML_CATS)
        rotated = _multilabel_layer(groups, ML_CATS, rowValueAngle={"r2": -90})
        assert rotated._kwds["height"] > flat._kwds["height"]
        # Only the rotated row grew, so the flat row above it keeps its center.
        assert self._row_y(rotated, "r1") == self._row_y(flat, "r1")

    def test_short_rotated_values_keep_the_default_row_height(self):
        # Auto-sizing floors at the 10px default, so a 1-2 char rotated row never shrinks
        # the table or grows it needlessly.
        flat = _multilabel_layer(self.TEXT_GROUPS, ML_CATS)
        rotated = _multilabel_layer(self.TEXT_GROUPS, ML_CATS, rowValueAngle=-90)
        assert rotated._kwds["height"] == flat._kwds["height"]

    def test_rotated_row_height_scales_with_longest_value(self):
        short = _multilabel_layer({"r": ["1", "2", "3"]}, ML_CATS, rowValueAngle=-90)
        long = _multilabel_layer({"r": ["1", "2", "3000000"]}, ML_CATS, rowValueAngle=-90)
        assert long._kwds["height"] > short._kwds["height"]

    def test_explicit_row_height_pins_a_rotated_row(self):
        auto = _multilabel_layer({"r": ["1000000", "2", "3"]}, ML_CATS, rowValueAngle=-90)
        pinned = _multilabel_layer({"r": ["1000000", "2", "3"]}, ML_CATS, rowValueAngle=-90, rowHeight=10)
        assert auto._kwds["height"] > 10
        assert pinned._kwds["height"] == 10

    def test_row_height_dict_is_partial_and_stacks(self):
        layer = _multilabel_layer(self.TEXT_GROUPS, ML_CATS, rowHeight={"r1": 30})
        # r1 occupies [0, 30), r2 auto-sizes to the 10px default below it.
        assert self._row_y(layer, "r1") == 15.0
        assert self._row_y(layer, "r2") == 35.0
        assert layer._kwds["height"] == 40.0

    def test_row_height_list_applies_in_row_order(self):
        layer = _multilabel_layer(self.TEXT_GROUPS, ML_CATS, rowHeight=[20, 40])
        assert self._row_y(layer, "r1") == 10.0
        assert self._row_y(layer, "r2") == 40.0

    def test_uniform_rows_keep_the_classic_centers(self):
        # Regression: rows used to ride an ordinal point scale, which placed them at
        # rowHeight*(i+0.5). The pixel layout that replaced it must not shift them.
        layer = _multilabel_layer(self.TEXT_GROUPS, ML_CATS)
        assert self._row_y(layer, "r1") == 5.0
        assert self._row_y(layer, "r2") == 15.0

    def test_category_label_top_offsets_every_row(self):
        layer = _multilabel_layer(self.TEXT_GROUPS, ML_CATS, categoryLabel=True, categoryLabelPosition="top")
        head = layer._kwds["height"] - 20.0  # the reserved category-label row
        assert head > 0
        assert self._row_y(layer, "r1") == head + 5.0
        assert self._row_y(layer, "r2") == head + 15.0

    def test_rotation_reaches_the_rendered_svg(self):
        import vl_convert as vlc

        svg = vlc.vegalite_to_svg(_multilabel_layer({"r": ["12", "34", "56"]}, ML_CATS, rowValueAngle=-90).to_dict())
        assert svg.count("rotate(270)") == 3

    def test_unknown_row_label_raises(self):
        with pytest.raises(ValueError, match="rowValueAngle has unknown row label"):
            _multilabel_layer(self.TEXT_GROUPS, ML_CATS, rowValueAngle={"nope": 90})
        with pytest.raises(ValueError, match="rowHeight has unknown row label"):
            _multilabel_layer(self.TEXT_GROUPS, ML_CATS, rowHeight={"nope": 20})

    def test_wrong_list_length_raises(self):
        with pytest.raises(ValueError, match="rowValueAngle list has 3 entries"):
            _multilabel_layer(self.TEXT_GROUPS, ML_CATS, rowValueAngle=[0, 90, 180])

    def test_symbol_rows_rotate_too(self):
        import vl_convert as vlc

        rotated = _multilabel_layer(ML_GROUPS, ML_CATS, style="symbol", symbol="triangle-up", rowValueAngle=-90)
        svg = vlc.vegalite_to_svg(rotated.to_dict())
        # One rotation per category: the marks carry the angle, not just text rows.
        assert svg.count("rotate(270)") == len(ML_CATS)

    def test_symbol_rows_keep_their_height_when_rotated(self):
        # A symbol's footprint is set by symbolSize, not by text length, so rotating one
        # must not resize the row the way a long rotated string does.
        flat = _multilabel_layer(ML_GROUPS, ML_CATS, style="symbol")
        rotated = _multilabel_layer(ML_GROUPS, ML_CATS, style="symbol", rowValueAngle=-90)
        assert rotated._kwds["height"] == flat._kwds["height"]

    def test_per_cell_angle_reaches_symbol_marks(self):
        layer = _multilabel_layer(
            {"r": [True, True, True]},
            ML_CATS,
            style="symbol",
            symbol="triangle-up",
            rowValueAngle={"r": [0, 90, 180]},
        )
        by_cat = {
            r["__category"]: r["__angle"]
            for rows in layer.to_dict()["datasets"].values()
            for r in rows
            if "__angle" in r
        }
        assert by_cat == {"A": 0.0, "B": 90.0, "C": 180.0}

    def test_per_cell_angle_list_rotates_only_some_cells(self):
        # The dose-response case: numeric doses stand on end, the untreated controls'
        # placeholders stay upright.
        layer = _multilabel_layer(
            {"dose": ["-", "10", "6.67"]},
            ML_CATS,
            rowValueAngle={"dose": [0, -90, -90]},
        )
        by_cat = {r["__category"]: r["__angle"] for r in self._text_marks(layer)}
        assert by_cat == {"A": 0.0, "B": 270.0, "C": 270.0}

    def test_per_cell_angle_sizes_the_row_from_its_tallest_cell(self):
        upright = _multilabel_layer({"dose": ["-", "1", "2"]}, ML_CATS, rowValueAngle={"dose": [0, 0, 0]})
        mixed = _multilabel_layer({"dose": ["-", "6.67", "2"]}, ML_CATS, rowValueAngle={"dose": [0, -90, 0]})
        assert mixed._kwds["height"] > upright._kwds["height"]

    def test_per_cell_angle_wrong_length_raises(self):
        with pytest.raises(ValueError, match=r"rowValueAngle\['dose'\] has 2 entries"):
            _multilabel_layer({"dose": ["-", "1", "2"]}, ML_CATS, rowValueAngle={"dose": [0, -90]})


class TestPlaceholderMinus:
    def test_lone_hyphen_renders_as_typographic_minus(self):
        # A "-" placeholder in a text row must match the "−" a plusminus row draws for
        # False, or the two glyphs differ visibly within one table.
        layer = _multilabel_layer({"drug": [False, True, True], "dose": ["-", "10", "20"]}, ML_CATS)
        values = {
            (r["__label"], r["__category"]): r["__value"]
            for ds_ in layer.to_dict().get("datasets", {}).values()
            for r in ds_
            if "__value" in r
        }
        assert values[("dose", "A")] == "−"
        assert values[("drug", "A")] == "−"

    def test_hyphen_inside_a_longer_value_is_untouched(self):
        layer = _multilabel_layer({"range": ["1-2", "-", "a-b-c"]}, ML_CATS)
        values = {
            r["__category"]: r["__value"]
            for ds_ in layer.to_dict().get("datasets", {}).values()
            for r in ds_
            if "__value" in r
        }
        assert values == {"A": "1-2", "B": "−", "C": "a-b-c"}


class TestSampleSizeRowInteraction:
    """add_multilabel injects the n-row into groups, which list-shaped kwargs must survive."""

    C = ["A", "B", "C"]
    GROUPS = {"r1": ["1", "2", "3"], "r2": ["10", "20", "30"]}

    def _df(self):
        return pl.DataFrame({"g": [c for c in self.C for _ in range(4)], "v": [float(i) for i in range(12)]})

    def _angles(self, chart) -> dict[str, float]:
        out: dict[str, float] = {}
        for rows in chart.to_dict().get("datasets", {}).values():
            for r in rows:
                if "__angle" in r:
                    out[r["__label"]] = r["__angle"]
        return out

    def _built(self, **kwargs):
        df = self._df()
        base = mark_strip(df, "g", "v", self.C)
        return add_multilabel(base, self.GROUPS, categories=self.C, showSampleSize=True, data=df, x="g", **kwargs)

    def test_row_angle_list_survives_the_injected_n_row(self):
        # Regression: the list is sized to the user's rows, but the n-row joins them before
        # _multilabel_layer sees them - so an unpinned list raised "2 entries but 3 rows".
        assert self._angles(self._built(rowValueAngle=[0, -90])) == {"r1": 0.0, "r2": 270.0, "n =": 0.0}

    def test_row_angle_list_maps_correctly_with_a_trailing_n_row(self):
        got = self._angles(self._built(rowValueAngle=[0, -90], sampleSizeIndex=2))
        assert got == {"r1": 0.0, "r2": 270.0, "n =": 0.0}

    def test_row_height_list_survives_the_injected_n_row(self):
        chart = self._built(rowHeight=[20, 30])
        # 20 + 30 for the user's rows, plus the auto-sized 10px n-row.
        table = chart.to_dict()["vconcat"][-1]
        assert table["height"] == 60.0

    def test_row_angle_list_length_is_still_checked(self):
        with pytest.raises(ValueError, match="rowValueAngle list has 3 entries but there are 2 rows"):
            self._built(rowValueAngle=[0, -90, 0])


class TestSampleSizeRowWithExplicitOrder:
    """An explicit `order` lists the caller's rows, so the injected n-row must still land."""

    C = ["A", "B", "C"]
    GROUPS = {"a": [True, True, True], "b": [True, False, True]}

    def _df(self):
        return pl.DataFrame({"g": [c for c in self.C for _ in range(4)], "v": [float(i) for i in range(12)]})

    def _rows(self, **kwargs) -> list[str]:
        """Row labels in the order they were rendered."""
        df = self._df()
        chart = add_multilabel(
            mark_strip(df, "g", "v", self.C),
            self.GROUPS,
            categories=self.C,
            showSampleSize=True,
            data=df,
            x="g",
            **kwargs,
        )
        seen: list[str] = []
        for rows in chart.to_dict().get("datasets", {}).values():
            for row in rows:
                if "__label" in row and row["__label"] not in seen:
                    seen.append(row["__label"])
        return seen

    def test_order_without_the_n_row_still_shows_it(self):
        # Regression: the n-row is injected after the caller wrote `order`, so it was absent
        # from row_order and silently dropped - taking sampleSizeIndex out of service with it.
        assert self._rows(order=["b", "a"]) == ["n =", "b", "a"]

    def test_sample_size_index_positions_it_within_an_explicit_order(self):
        assert self._rows(order=["b", "a"], sampleSizeIndex=2) == ["b", "a", "n ="]
        assert self._rows(order=["b", "a"], sampleSizeIndex=-1) == ["b", "n =", "a"]

    def test_naming_the_row_in_order_wins(self):
        # sampleSizeIndex defaults to 0, but an explicit placement is the caller's.
        assert self._rows(order=["b", "a", "n ="]) == ["b", "a", "n ="]

    def test_custom_sample_size_label_is_matched(self):
        assert self._rows(order=["b", "a"], sampleSizeLabel="N") == ["N", "b", "a"]

    def test_order_may_still_subset_the_caller_rows(self):
        assert self._rows(order=["b"]) == ["n =", "b"]

    def test_empty_order_stays_empty(self):
        # An empty order means no rows; the line resolving the list basis reads it as
        # "no order given", so injecting the n-row here would disagree with that.
        assert self._rows(order=[]) == []

    def test_caller_order_list_is_not_mutated(self):
        shared = ["b", "a"]
        assert self._rows(order=shared) == ["n =", "b", "a"]
        assert shared == ["b", "a"]
        assert self._rows(order=shared) == ["n =", "b", "a"]

    def test_list_kwargs_still_count_the_caller_rows(self):
        # The n-row joins `order` only after the list normalization, so a list stays sized
        # to the rows the caller actually wrote.
        assert self._rows(order=["b", "a"], rowValueAngle=[0, -90]) == ["n =", "b", "a"]
        with pytest.raises(ValueError, match="rowValueAngle list has 3 entries but there are 2 rows"):
            self._rows(order=["b", "a"], rowValueAngle=[0, -90, 0])


class TestRowValidation:
    """Bad row labels report themselves instead of failing obscurely or silently."""

    C = ["A", "B", "C"]
    GROUPS = {"a": [True, True, True], "b": [True, False, True]}

    def _df(self):
        return pl.DataFrame({"g": [c for c in self.C for _ in range(4)], "v": [float(i) for i in range(12)]})

    def _with_n(self, groups, **kwargs):
        df = self._df()
        return add_multilabel(
            mark_strip(df, "g", "v", self.C),
            groups,
            categories=self.C,
            showSampleSize=True,
            data=df,
            x="g",
            **kwargs,
        )

    def test_order_naming_an_unknown_row_raises(self):
        # Was a bare KeyError from the value-count loop, naming nothing useful.
        with pytest.raises(ValueError, match=r"order names row\(s\) \['zz'\] that are not in groups"):
            _multilabel_layer(self.GROUPS, self.C, order=["b", "zz"])

    def test_the_error_lists_the_rows_that_do_exist(self):
        with pytest.raises(ValueError, match=r"Rows are \['a', 'b'\]"):
            _multilabel_layer(self.GROUPS, self.C, order=["bb"])

    def test_valid_order_still_builds(self):
        assert isinstance(_multilabel_layer(self.GROUPS, self.C, order=["b", "a"]), alt.LayerChart)
        assert isinstance(_multilabel_layer(self.GROUPS, self.C, order=[]), alt.LayerChart)

    def test_order_rejects_duplicate_rows(self):
        with pytest.raises(ValueError, match="duplicate row label"):
            _multilabel_layer(self.GROUPS, self.C, order=["a", "a"])

    def test_styling_maps_validate_full_rows_not_displayed_subset(self):
        chart = _multilabel_layer(
            self.GROUPS,
            self.C,
            order=["a"],
            rowStyles={"b": "symbol"},
            rowHeight={"b": 20},
            rowValueAngle={"b": -90},
        )
        assert isinstance(chart, alt.LayerChart)
        with pytest.raises(ValueError, match="rowStyles has unknown row label"):
            _multilabel_layer(self.GROUPS, self.C, order=["a"], rowStyles={"zz": "symbol"})

    def test_sample_size_label_colliding_with_a_row_raises(self):
        # One row silently replaced the other, and which one won depended on `order`.
        groups = {"n =": ["x", "y", "z"], "b": [True, False, True]}
        with pytest.raises(ValueError, match="groups already has a row labelled 'n ='"):
            self._with_n(groups)
        with pytest.raises(ValueError, match="groups already has a row labelled 'n ='"):
            self._with_n(groups, order=["b", "n ="])

    def test_a_custom_sample_size_label_avoids_the_collision(self):
        chart = self._with_n({"n =": ["x", "y", "z"]}, sampleSizeLabel="N")
        labels = {r["__label"] for rows in chart.to_dict()["datasets"].values() for r in rows if "__label" in r}
        assert labels == {"n =", "N"}  # the caller's row AND the counts row

    def test_the_label_is_free_without_show_sample_size(self):
        df = self._df()
        chart = add_multilabel(mark_strip(df, "g", "v", self.C), {"n =": ["x", "y", "z"]}, categories=self.C)
        assert isinstance(chart, alt.VConcatChart)
