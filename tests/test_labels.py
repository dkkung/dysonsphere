import altair as alt
import polars as pl
import pytest

from dysonsphere.labels import label_expr
from dysonsphere.theme import theme


@pytest.fixture(autouse=True)
def default_theme():
    theme()


class TestLabelExpr:
    def test_basic_mapping(self):
        expr = label_expr({"a": "A", "b": "B"})
        assert expr == "datum.value == 'a' ? 'A' : datum.value == 'b' ? 'B' : datum.value"

    def test_falls_back_to_raw_value(self):
        assert label_expr({"a": "A"}).endswith(" : datum.value")

    def test_numeric_keys(self):
        expr = label_expr({5: "five", 2.5: "two and a half"})
        assert "datum.value == 5 ? 'five'" in expr
        assert "datum.value == 2.5 ? 'two and a half'" in expr

    def test_quote_and_backslash_escaping(self):
        expr = label_expr({"it's": "5' UTR", "back\\slash": "b"})
        assert "datum.value == 'it\\'s' ? '5\\' UTR'" in expr
        assert "'back\\\\slash'" in expr

    def test_multiline_label_renders_array(self):
        expr = label_expr({"tnf": ["TNF-α", "(10 ng/mL)"]})
        assert "? ['TNF-α', '(10 ng/mL)']" in expr

    def test_empty_string_label_survives(self):
        # the reason for the ternary chain: '' is falsy, so the {...}[v] || v idiom
        # would silently fall back to the raw value instead of hiding it
        expr = label_expr({"hideme": ""})
        assert "datum.value == 'hideme' ? ''" in expr

    def test_empty_mapping_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            label_expr({})

    def test_bad_label_type_raises(self):
        with pytest.raises(TypeError, match="str or list"):
            label_expr({"a": 5})  # ty: ignore[invalid-argument-type]

    def test_bad_multiline_item_raises(self):
        with pytest.raises(TypeError, match="list of str"):
            label_expr({"a": ["ok", 5]})  # ty: ignore[invalid-argument-type]

    def test_end_to_end_labels_rendered(self, tmp_path):
        # the mapped labels appear in the rendered SVG text; the raw values do not
        from dysonsphere.export import save

        df = pl.DataFrame({"g": ["metadata_group1", "metadata_group2"] * 3, "v": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]})
        mapping = {"metadata_group1": "group 1", "metadata_group2": "group 2"}
        chart = alt.Chart(df).mark_point().encode(x=alt.X("g:N", axis=alt.Axis(labelExpr=label_expr(mapping))), y="v:Q")
        save(chart, str(tmp_path / "lab"), format="svg", background="light")
        svg = (tmp_path / "lab.svg").read_text(encoding="utf-8")
        assert ">group 1<" in svg and ">group 2<" in svg
        assert ">metadata_group1<" not in svg  # raw value not shown as a label

    def test_end_to_end_data_keeps_raw_values(self, tmp_path):
        # presentation-only: the exported data still holds the raw values
        import dysonsphere as ds

        df = pl.DataFrame({"g": ["raw_a", "raw_b"], "v": [1.0, 2.0]})
        chart = (
            alt.Chart(df)
            .mark_point()
            .encode(x=alt.X("g:N", axis=alt.Axis(labelExpr=label_expr({"raw_a": "A"}))), y="v:Q")
        )
        ds.save(chart, str(tmp_path / "raw"), format="json", background="light")
        frame = ds.read(str(tmp_path / "raw.json"), what="data")
        assert set(frame["g"].to_list()) == {"raw_a", "raw_b"}
