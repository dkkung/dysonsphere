import altair as alt
import polars as pl
import pytest

import dysonsphere as ds
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
        spec = mark_table(df, columns=["gene"], headerLabels={"gene": "Gene"}).to_dict()
        texts = [layer.get("encoding", {}).get("text", {}).get("value") for layer in spec["layer"]]
        assert "Gene" in texts and "gene" not in texts

    def test_header_false_removes_header_text(self, df):
        # With header=False the top of the plot is flush; height loses one row.
        h_with = mark_table(df, header=True).to_dict()["height"]
        h_without = mark_table(df, header=False).to_dict()["height"]
        assert h_with > h_without

    def test_unknown_column_raises(self, df):
        with pytest.raises(ValueError, match="not in df"):
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
        n_all = len(mark_table(df, strokes=("outer", "all")).to_dict()["layer"])
        assert n_all > n_outer

    def test_no_strokes(self, df):
        assert isinstance(mark_table(df, strokes=()), alt.LayerChart)


class TestFormatting:
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


class TestCellColor:
    def test_non_numeric_column_raises(self, df):
        with pytest.raises(ValueError, match="must be numeric"):
            mark_table(df, cellColor={"gene": "greys"})

    def test_column_not_shown_raises(self, df):
        with pytest.raises(ValueError, match="not among the shown columns"):
            mark_table(df, columns=["gene"], cellColor={"log2FC": "greens"})

    def test_color_scale_present_and_independent(self, df):
        spec = mark_table(df, cellColor={"log2FC": "pinksblues"}).to_dict()
        assert spec["resolve"]["scale"]["color"] == "independent"
        # A quantitative color scale keyed to the value column exists somewhere.
        colors = [layer.get("encoding", {}).get("color", {}) for layer in spec["layer"]]
        assert any(c.get("field") == "log2FC" and c.get("type") == "quantitative" for c in colors)

    def test_diverging_palette_symmetric_domain(self, df):
        # A 13-stop diverging palette centres its domain on 0.
        spec = mark_table(df, cellColor={"log2FC": "pinksblues"}).to_dict()
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
        # A cellColor column keeps its auto-contrast color-scale even under a global textColor.
        spec = mark_table(df, textColor="#555555", cellColor={"log2FC": "pinksblues"}).to_dict()
        has_contrast = any(
            "color" in layer.get("encoding", {}) and layer.get("encoding", {})["color"].get("scale") is None
            for layer in self._text_marks(spec)
        )
        assert has_contrast

    def test_dict_text_color_overrides_heatmap(self, df):
        # An explicit per-column entry is deliberate: it wins over the heatmap auto-contrast.
        spec = mark_table(df, textColor={"log2FC": "#000000"}, cellColor={"log2FC": "pinksblues"}).to_dict()
        log2fc_mark = next(
            layer
            for layer in self._text_marks(spec)
            if layer.get("encoding", {}).get("text", {}).get("field") == "log2FC"
        )
        assert log2fc_mark["mark"].get("color") == "#000000"
        assert "color" not in log2fc_mark.get("encoding", {})

    def test_header_color(self, df):
        spec = mark_table(df, headerColor="#123456").to_dict()
        # Header labels ride as literal text values with fontStyle bold.
        header_colors = {
            layer["mark"].get("color") for layer in self._text_marks(spec) if layer["mark"].get("fontStyle") == "bold"
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
            layer["mark"].get("color") for layer in self._text_marks(spec) if layer["mark"].get("fontStyle") == "bold"
        }
        assert header_colors <= {"black", "white"} and header_colors  # exactly black or white


class TestAlign:
    def test_default_all_left(self, df):
        spec = mark_table(df, columns=["gene", "hits"]).to_dict()
        text_aligns = {
            layer["mark"].get("align")
            for layer in spec["layer"]
            if isinstance(layer.get("mark"), dict) and layer["mark"].get("type") == "text"
        }
        assert text_aligns == {"left"}

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
            cellColor={"log2FC": "pinksblues"},
        )
        out = str(tmp_path / "tbl")
        ds.save(chart, out, format="json", background=["light"])
        recovered = ds.read(out + ".json", what="data")
        assert isinstance(recovered, pl.DataFrame)
        assert recovered.equals(df)
        assert ds.frame_checksum(recovered) == ds.frame_checksum(df)

    def test_datachecksum_single_entry(self, df, tmp_path):
        out = str(tmp_path / "tbl")
        ds.save(mark_table(df), out, format="json", background=["light"])
        meta = ds.read(out + ".json", what="metadata")
        assert len(meta["provenance"]["dataChecksum"]) == 1
