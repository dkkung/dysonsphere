import altair as alt
import polars as pl
import pytest

import dysonsphere as ds
from dysonsphere.palettes import colors
from dysonsphere.table import (
    _contrast_expr,
    _fmt_power,
    _fmt_scientific,
    _rel_luminance,
    mark_table,
)
from dysonsphere.theme import theme


@pytest.fixture(autouse=True)
def default_theme():
    theme()


@pytest.fixture
def df():
    return pl.DataFrame(
        {
            "gene": ["TP53", "EGFR", "MYC", "BRCA1"],
            "log2FC": [2.31, -1.84, 0.42, 3.10],
            "pvalue": [1.2e-14, 3.4e-3, 0.42, 5.6e-9],
            "hits": [128, 44, 12, 301],
        }
    )


class TestMarkTable:
    def test_returns_layer_chart(self, df):
        assert isinstance(mark_table(df), alt.LayerChart)

    def test_self_sizes_from_content(self, df):
        # A table can't use the 100x100 default: width follows column content (here it
        # exceeds 100), height scales with the row count (header + 4 rows).
        spec = mark_table(df, rowHeight=14).to_dict()
        assert spec["width"] > 100
        assert spec["height"] == 5 * 14  # header + 4 data rows

    def test_height_scales_with_rows(self, df):
        two = mark_table(df.head(2), rowHeight=14).to_dict()["height"]
        four = mark_table(df, rowHeight=14).to_dict()["height"]
        assert four - two == 2 * 14

    def test_columns_subset_and_order(self, df):
        spec = mark_table(df, columns=["pvalue", "gene"]).to_dict()
        # Header labels ride as literal text values on the sidecar layers.
        texts = [layer.get("encoding", {}).get("text", {}).get("value") for layer in spec["layer"]]
        assert "pvalue" in texts and "gene" in texts and "hits" not in texts

    def test_header_labels_rename(self, df):
        spec = mark_table(df, columns=["gene"], headerLabels={"gene": "Gene", "absent": "Unused"}).to_dict()
        texts = [layer.get("encoding", {}).get("text", {}).get("value") for layer in spec["layer"]]
        assert "Gene" in texts and "gene" not in texts

    def test_header_false_removes_header_text(self, df):
        # With header=False the top of the plot is flush; height loses one row.
        h_with = mark_table(df, header=True).to_dict()["height"]
        h_without = mark_table(df, header=False).to_dict()["height"]
        assert h_with > h_without

    def test_unknown_column_raises(self, df):
        with pytest.raises(ValueError, match="not in data"):
            mark_table(df, columns=["nope"])

    def test_empty_df_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            mark_table(pl.DataFrame({"a": []}))

    def test_empty_columns_raises(self, df):
        with pytest.raises(ValueError, match="at least one column"):
            mark_table(df, columns=[])

    def test_pandas_input(self, df):
        assert isinstance(mark_table(df.to_pandas()), alt.LayerChart)

    def test_pandas_matches_polars_size(self, df):
        assert mark_table(df).to_dict()["width"] == mark_table(df.to_pandas()).to_dict()["width"]


class TestStrokes:
    def test_string_accepted(self, df):
        assert isinstance(mark_table(df, strokes="all"), alt.LayerChart)

    def test_unknown_stroke_raises(self, df):
        with pytest.raises(ValueError, match="unknown strokes"):
            mark_table(df, strokes=("outer", "middle"))

    def test_all_draws_more_rules_than_outer(self, df):
        n_outer = len(mark_table(df, strokes="outer").to_dict()["layer"])
        n_all = len(mark_table(df, strokes="all").to_dict()["layer"])
        assert n_all > n_outer

    def test_grid_expands_to_rows_and_cols(self, df):
        # "grid" == the interior only (rows + cols), NOT the outer border or header separator.
        n_grid = len(mark_table(df, strokes="grid").to_dict()["layer"])
        n_rows_cols = len(mark_table(df, strokes=("rows", "cols")).to_dict()["layer"])
        assert n_grid == n_rows_cols

    def test_all_is_grid_plus_outer_and_header(self, df):
        # "all" == every rule: it draws strictly more than the interior grid alone.
        n_all = len(mark_table(df, strokes="all").to_dict()["layer"])
        n_grid = len(mark_table(df, strokes="grid").to_dict()["layer"])
        n_everything = len(mark_table(df, strokes=("outer", "header", "rows", "cols")).to_dict()["layer"])
        assert n_all == n_everything > n_grid

    def test_no_strokes(self, df):
        assert isinstance(mark_table(df, strokes=()), alt.LayerChart)


class TestStriping:
    def _n_rect_layers(self, spec):
        return sum(
            1 for layer in spec["layer"] if isinstance(layer.get("mark"), dict) and layer["mark"].get("type") == "rect"
        )

    def test_per_cell_rects_scale_with_columns(self):
        # Striping draws one rect per cell (per column), so adding a column adds nStripes rects -
        # each cell background is an independent <rect> for Illustrator editing.
        d2 = pl.DataFrame({"a": [1, 2], "b": [3, 4]})
        d3 = pl.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6]})
        n2 = self._n_rect_layers(mark_table(d2, strokes=()).to_dict())
        n3 = self._n_rect_layers(mark_table(d3, strokes=()).to_dict())
        assert n2 == 2 * 2  # 2 columns x nStripes(=2)
        assert n3 - n2 == 2  # one more column -> nStripes more rects

    def test_striping_false_draws_no_rects(self):
        d2 = pl.DataFrame({"a": [1, 2], "b": [3, 4]})
        assert self._n_rect_layers(mark_table(d2, striping=False, strokes=()).to_dict()) == 0


class TestFormatting:
    @staticmethod
    def _svg_text(svg):
        import xml.etree.ElementTree as ET

        root = ET.fromstring(svg)
        return [element.text or "" for element in root.iter("{http://www.w3.org/2000/svg}text")]

    def test_scientific_calc_layer_present(self, df):
        spec = mark_table(df, columnFormat={"pvalue": "scientific"}).to_dict()
        calcs = [t for layer in spec["layer"] for t in layer.get("transform", []) if "calculate" in t]
        assert any("×10" in c["calculate"] for c in calcs)

    def test_power_calc_layer_present(self, df):
        spec = mark_table(df, columnFormat={"pvalue": "power"}).to_dict()
        calcs = [t for layer in spec["layer"] for t in layer.get("transform", []) if "calculate" in t]
        assert any("'10'" in c["calculate"] for c in calcs)

    def test_printf_spec_native_format(self, df):
        spec = mark_table(df, columnFormat={"log2FC": ".2f"}).to_dict()
        formats = [layer.get("encoding", {}).get("text", {}).get("format") for layer in spec["layer"]]
        assert ".2f" in formats

    def test_fmt_scientific_python(self):
        assert _fmt_scientific(1.2e-14, 3) == "1.20×10⁻¹⁴"
        assert _fmt_scientific(-3.4e3, 2) == "−3.4×10³"
        assert _fmt_scientific(0.0, 3) == "0"

    def test_fmt_power_python(self):
        assert _fmt_power(1.2e-14, 3) == "10⁻¹⁴"
        assert _fmt_power(0.0, 3) == "0"

    def test_calc_expr_is_valid_vega(self, df):
        # A calc-notation column must actually render (the expression must compile in Vega).
        chart = mark_table(df, columnFormat={"pvalue": "scientific", "log2FC": "power"})
        chart.to_dict()  # would raise if the transform were malformed

    def test_missing_zero_and_signed_values_render_in_body_text(self):
        import vl_convert as vlc

        data = pl.DataFrame({"number": [None, 0.0, 1.25, -2.5]})
        svg = vlc.vegalite_to_svg(mark_table(data, header=False, columnFormat={"number": "scientific"}).to_dict())
        assert self._svg_text(svg) == ["0", "1.25×10⁰", "−2.50×10⁰"]

    def test_missing_body_text_does_not_change_later_row_positions(self):
        import re
        import xml.etree.ElementTree as ET

        import vl_convert as vlc

        def positions(data):
            svg = vlc.vegalite_to_svg(
                mark_table(data, header=False, rowHeight=14, columnFormat={"number": "scientific"}).to_dict()
            )
            out = {}
            for element in ET.fromstring(svg).iter("{http://www.w3.org/2000/svg}text"):
                text = element.text or ""
                match = re.search(r",([\d.]+)\)$", element.get("transform", ""))
                if text and match:
                    out[text] = float(match.group(1))
            return out

        with_missing = positions(pl.DataFrame({"number": [None, 0.0, 1.25, -2.5]}))
        without_missing = positions(pl.DataFrame({"number": [9.0, 0.0, 1.25, -2.5]}))
        assert {key: with_missing[key] for key in ("0", "1.25×10⁰", "−2.50×10⁰")} == {
            key: without_missing[key] for key in ("0", "1.25×10⁰", "−2.50×10⁰")
        }

    def test_explicit_d3_format_renders_without_python_formatting(self):
        import vl_convert as vlc

        data = pl.DataFrame({"number": [1234.5]})
        svg = vlc.vegalite_to_svg(mark_table(data, columnFormat={"number": "$,.2f"}).to_dict())
        assert "$1,234.50" in svg

    def test_named_si_format_uses_sigfigs(self):
        import vl_convert as vlc

        data = pl.DataFrame({"number": [12345.6]})
        svg = vlc.vegalite_to_svg(mark_table(data, columnFormat={"number": "si"}, sigFigs=3).to_dict())
        assert "12.3k" in svg

    def test_null_dtype_named_formats_remain_blank(self):
        import vl_convert as vlc

        data = pl.DataFrame({"number": [None, None]})
        for notation in ("scientific", "power", "e", "si"):
            svg = vlc.vegalite_to_svg(mark_table(data, header=False, columnFormat={"number": notation}).to_dict())
            assert self._svg_text(svg) == []

    def test_nan_is_missing_for_display_and_palette_domain(self):
        import vl_convert as vlc

        data = pl.DataFrame({"number": [float("nan"), 0.0, 2.0]})
        chart = mark_table(data, header=False, columnFormat={"number": "scientific"}, cellPalette={"number": "greys"})
        svg = vlc.vegalite_to_svg(chart.to_dict())
        assert self._svg_text(svg) == ["0", "2.00×10⁰"]
        color = next(
            layer["encoding"]["color"] for layer in chart.to_dict()["layer"] if "color" in layer.get("encoding", {})
        )
        assert color["scale"]["domain"] == [0.0, 2.0]

    def test_string_column_keeps_valid_d3_character_format(self):
        import vl_convert as vlc

        data = pl.DataFrame({"label": ["A", "B"]})
        svg = vlc.vegalite_to_svg(mark_table(data, header=False, columnFormat={"label": "c"}).to_dict())
        assert self._svg_text(svg) == ["A", "B"]

    def test_string_format_padding_is_applied_by_d3(self):
        import json

        import vl_convert as vlc

        spec = mark_table(pl.DataFrame({"label": ["A"]}), header=False, columnFormat={"label": ">4c"}).to_dict()
        # Vega trims edge spaces in SVG; the scenegraph retains the formatter's result.
        assert '"text": "   A"' in json.dumps(vlc.vegalite_to_scenegraph(spec))

    def test_numeric_notation_does_not_silently_ignore_string_values(self):
        with pytest.raises(ValueError, match="requires numeric values"):
            mark_table(pl.DataFrame({"label": ["A", "B"]}), columnFormat={"label": "scientific"})

    def test_explicit_numeric_format_preserves_boolean_support(self):
        import vl_convert as vlc

        svg = vlc.vegalite_to_svg(
            mark_table(
                pl.DataFrame({"flag": [True, False]}), header=False, columnFormat={"flag": "scientific"}
            ).to_dict()
        )
        assert self._svg_text(svg) == ["1.00×10⁰", "0"]

    def test_boolean_values_use_explicit_numeric_format(self):
        import vl_convert as vlc

        svg = vlc.vegalite_to_svg(
            mark_table(pl.DataFrame({"flag": [True, False]}), header=False, columnFormat={"flag": ".2f"}).to_dict()
        )
        assert self._svg_text(svg) == ["1.00", "0.00"]

    def test_extreme_scientific_and_power_values_render(self):
        import vl_convert as vlc

        data = pl.DataFrame({"number": [9.999, 1e100, 5e-324]}, strict=False)
        scientific = vlc.vegalite_to_svg(mark_table(data, columnFormat={"number": "scientific"}).to_dict())
        power = vlc.vegalite_to_svg(mark_table(data, columnFormat={"number": "power"}).to_dict())
        assert "1.00×10¹" in scientific and "1.00×10¹⁰⁰" in scientific
        assert "4.94×10⁻³²⁴" in scientific
        assert "10¹⁰⁰" in power and "10⁻³²³" in power

    def test_invalid_d3_format_raises(self, df):
        with pytest.raises(ValueError, match="valid Vega/d3 format"):
            mark_table(df, columnFormat={"pvalue": "not-a-format"})


class TestCellColor:
    @pytest.mark.parametrize("name", ["viridis", "Blues", "blues"])
    def test_palette_names_are_shared_and_case_sensitive(self, df, name):
        spec = mark_table(df, cellPalette={"log2FC": name}, stripePalette=name).to_dict()
        scales = [layer.get("encoding", {}).get("color", {}).get("scale", {}) for layer in spec["layer"]]
        assert any(scale.get("range") == colors[name] for scale in scales)
        with pytest.raises(ValueError, match="unknown palette"):
            mark_table(df, cellPalette={"log2FC": "Viridis"})
        with pytest.raises(ValueError, match="unknown palette"):
            mark_table(df, stripePalette="Viridis")

    def test_non_numeric_column_raises(self, df):
        with pytest.raises(ValueError, match="must be numeric"):
            mark_table(df, cellPalette={"gene": "greys"})

    def test_known_excluded_column_is_allowed(self, df):
        # Styling maps describe input columns, not only the displayed subset. An excluded numeric
        # column is valid and must not be resolved or rendered as a heatmap.
        assert isinstance(mark_table(df, columns=["gene"], cellPalette={"log2FC": "greens"}), alt.LayerChart)

    def test_unknown_column_raises(self, df):
        with pytest.raises(ValueError, match="cellPalette has unknown column"):
            mark_table(df, columns=["gene"], cellPalette={"nope": "greens"})

    def test_color_scale_present_and_independent(self, df):
        spec = mark_table(df, cellPalette={"log2FC": "pinksblues"}).to_dict()
        assert spec["resolve"]["scale"]["color"] == "independent"
        # A quantitative color scale keyed to the value column exists somewhere.
        colors = [layer.get("encoding", {}).get("color", {}) for layer in spec["layer"]]
        assert any(c.get("field") == "log2FC" and c.get("type") == "quantitative" for c in colors)

    def test_diverging_palette_symmetric_domain(self, df):
        # A 13-stop diverging palette centres its domain on 0.
        spec = mark_table(df, cellPalette={"log2FC": "pinksblues"}).to_dict()
        for layer in spec["layer"]:
            c = layer.get("encoding", {}).get("color", {})
            if c.get("field") == "log2FC" and c.get("type") == "quantitative":
                lo, hi = c["scale"]["domain"]
                assert lo == -hi
                return
        pytest.fail("no value-color layer found")

    def test_contrast_expr_flips_black_white(self):
        expr = _contrast_expr("v", ["#000000", "#ffffff"], (0.0, 1.0))
        assert "'white'" in expr and "'black'" in expr

    def test_rel_luminance_bounds(self):
        assert _rel_luminance("#000000") == pytest.approx(0.0, abs=1e-6)
        assert _rel_luminance("#ffffff") == pytest.approx(1.0, abs=1e-6)


class TestColors:
    def _text_marks(self, spec):
        return [
            layer
            for layer in spec["layer"]
            if isinstance(layer.get("mark"), dict) and layer["mark"].get("type") == "text"
        ]

    def _cell_by_field(self, spec, prop):
        # Map each body cell layer's text field -> a mark property (headers carry no field).
        return {
            layer.get("encoding", {}).get("text", {}).get("field"): layer["mark"].get(prop)
            for layer in self._text_marks(spec)
            if layer.get("encoding", {}).get("text", {}).get("field")
        }

    def test_font_style_per_column_dict(self, df):
        spec = mark_table(df, columns=["gene", "hits"], fontStyle={"gene": "italic"}).to_dict()
        by_field = self._cell_by_field(spec, "fontStyle")
        assert by_field.get("gene") == "italic"
        assert by_field.get("hits") is None  # unlisted inherits

    def test_font_style_global(self, df):
        spec = mark_table(df, columns=["gene", "hits"], fontStyle="italic").to_dict()
        assert set(self._cell_by_field(spec, "fontStyle").values()) == {"italic"}

    def test_style_maps_accept_known_excluded_columns_and_reject_unknown_keys(self, df):
        mark_table(
            df,
            columns=["gene"],
            columnFormat={"pvalue": ".2f"},
            align={"hits": "right"},
            textColor={"log2FC": "red"},
            fontStyle={"pvalue": "italic"},
            columnWidths={"hits": 20},
        )
        with pytest.raises(ValueError, match="columnFormat has unknown column"):
            mark_table(df, columnFormat={"unknown": ".2f"})

    def test_text_color_global(self, df):
        spec = mark_table(df, textColor="#555555").to_dict()
        colors = {layer["mark"].get("color") for layer in self._text_marks(spec)}
        assert "#555555" in colors

    def test_text_color_per_column_dict(self, df):
        # Cell text marks carry a text FIELD (headers carry a literal text value); key on field.
        spec = mark_table(df, columns=["gene", "hits"], textColor={"gene": "#aa0000"}).to_dict()
        by_field = {
            layer.get("encoding", {}).get("text", {}).get("field"): layer["mark"].get("color")
            for layer in self._text_marks(spec)
            if layer.get("encoding", {}).get("text", {}).get("field")
        }
        assert by_field.get("gene") == "#aa0000"
        assert by_field.get("hits") is None  # unlisted inherits (no explicit color)

    def test_global_text_color_does_not_override_heatmap_contrast(self, df):
        # A cellPalette column keeps its auto-contrast color-scale even under a global textColor.
        spec = mark_table(df, textColor="#555555", cellPalette={"log2FC": "pinksblues"}).to_dict()
        has_contrast = any(
            "color" in layer.get("encoding", {}) and layer.get("encoding", {})["color"].get("scale") is None
            for layer in self._text_marks(spec)
        )
        assert has_contrast

    def test_dict_text_color_overrides_heatmap(self, df):
        # An explicit per-column entry is deliberate: it wins over the heatmap auto-contrast.
        spec = mark_table(df, textColor={"log2FC": "#000000"}, cellPalette={"log2FC": "pinksblues"}).to_dict()
        log2fc_mark = next(
            layer
            for layer in self._text_marks(spec)
            if layer.get("encoding", {}).get("text", {}).get("field") == "log2FC"
        )
        assert log2fc_mark["mark"].get("color") == "#000000"
        assert "color" not in log2fc_mark.get("encoding", {})

    def test_header_is_bold_by_default(self, df):
        """headerFontStyle="bold" was a no-op - Vega takes bold as a WEIGHT, not a style."""
        marks = [layer["mark"] for layer in self._text_marks(mark_table(df).to_dict())]
        assert any(m.get("fontWeight") == "bold" for m in marks)
        assert not any(m.get("fontStyle") == "bold" for m in marks)

    def test_header_weight_and_style_are_separate(self, df):
        marks = [
            layer["mark"]
            for layer in self._text_marks(mark_table(df, headerFontWeight="normal", headerFontStyle="italic").to_dict())
        ]
        assert any(m.get("fontStyle") == "italic" and m.get("fontWeight") == "normal" for m in marks)

    def test_header_color(self, df):
        spec = mark_table(df, headerColor="#123456").to_dict()
        # Header labels ride as literal text values at bold weight.
        header_colors = {
            layer["mark"].get("color") for layer in self._text_marks(spec) if layer["mark"].get("fontWeight") == "bold"
        }
        assert "#123456" in header_colors

    def test_header_fill_string_draws_band(self, df):
        n_off = len(mark_table(df, headerFill=False).to_dict()["layer"])
        spec_on = mark_table(df, headerFill="#eeeeee").to_dict()
        assert len(spec_on["layer"]) == n_off + 1
        fills = {
            layer["mark"].get("fill")
            for layer in spec_on["layer"]
            if isinstance(layer.get("mark"), dict) and layer["mark"].get("type") == "rect"
        }
        assert "#eeeeee" in fills

    def test_header_fill_true_auto_contrasts_text(self, df):
        # With a fill and no explicit headerColor, header text auto-contrasts (a color is set).
        spec = mark_table(df, headerFill=True).to_dict()
        header_colors = {
            layer["mark"].get("color") for layer in self._text_marks(spec) if layer["mark"].get("fontWeight") == "bold"
        }
        assert header_colors <= {"black", "white"} and header_colors  # exactly black or white


class TestAlign:
    def test_default_type_aware(self, df):
        # Default (align=None): numeric columns right-aligned, non-numeric left.
        spec = mark_table(df, columns=["gene", "log2FC", "hits"]).to_dict()
        aligns = {
            layer.get("encoding", {}).get("text", {}).get("value"): layer["mark"].get("align")
            for layer in spec["layer"]
            if isinstance(layer.get("mark"), dict) and layer["mark"].get("type") == "text"
        }
        assert aligns.get("gene") == "left"  # string → left
        assert aligns.get("log2FC") == "right"  # numeric → right
        assert aligns.get("hits") == "right"  # numeric → right

    def test_dict_align_override(self, df):
        spec = mark_table(df, columns=["gene", "hits"], align={"hits": "right"}).to_dict()
        aligns = {
            layer.get("encoding", {}).get("text", {}).get("value"): layer["mark"].get("align")
            for layer in spec["layer"]
            if isinstance(layer.get("mark"), dict) and layer["mark"].get("type") == "text"
        }
        assert aligns.get("gene") == "left"  # unlisted stays left
        assert aligns.get("hits") == "right"

    def test_global_align_string(self, df):
        spec = mark_table(df, align="center").to_dict()
        text_aligns = {
            layer["mark"].get("align")
            for layer in spec["layer"]
            if isinstance(layer.get("mark"), dict) and layer["mark"].get("type") == "text"
        }
        assert text_aligns == {"center"}


class TestColumnWidths:
    def test_list_override(self, df):
        w = [40.0, 30.0, 50.0, 20.0]
        assert mark_table(df, columnWidths=w).to_dict()["width"] == sum(w)

    def test_list_length_mismatch_raises(self, df):
        with pytest.raises(ValueError, match="columnWidths has"):
            mark_table(df, columnWidths=[10, 20])

    def test_dict_override_partial(self, df):
        # Unlisted columns keep their estimate; total still grows with the override.
        base = mark_table(df).to_dict()["width"]
        wide = mark_table(df, columnWidths={"gene": base}).to_dict()["width"]
        assert wide > base


class TestDataProvenance:
    def test_one_user_frame_and_pristine_recovery(self, df, tmp_path):
        # The df must inline exactly once, untouched, so read() recovers it byte-for-byte
        # and its dataChecksum matches - the whole point of the transform-driven design.
        chart = mark_table(
            df,
            columnFormat={"pvalue": "scientific", "log2FC": ".2f"},
            cellPalette={"log2FC": "pinksblues"},
        )
        out = str(tmp_path / "tbl")
        ds.save(chart, out, format="json", background=["light"])
        recovered = ds.metadata.read(out + ".json", what="data")
        assert isinstance(recovered, pl.DataFrame)
        assert recovered.equals(df)
        assert ds.metadata.frame_checksum(recovered) == ds.metadata.frame_checksum(df)

    def test_datachecksum_single_entry(self, df, tmp_path):
        out = str(tmp_path / "tbl")
        ds.save(mark_table(df), out, format="json", background=["light"])
        meta = ds.metadata.read(out + ".json", what="metadata")
        assert len(meta["provenance"]["dataChecksum"]) == 1

    def test_null_and_float_types_survive_export(self, tmp_path):
        data = pl.DataFrame({"number": [None, 0.0, 2.5]}, strict=False)
        out = str(tmp_path / "nulls")
        ds.save(mark_table(data, columnFormat={"number": ".2f"}), out, format="json", background=["light"])
        recovered = ds.metadata.read(out + ".json", what="data")
        assert isinstance(recovered, pl.DataFrame)
        assert recovered.equals(data)
        assert recovered.schema == data.schema
        assert ds.metadata.frame_checksum(pl.DataFrame({"number": [None]})) != ds.metadata.frame_checksum(
            pl.DataFrame({"number": [0.0]})
        )
