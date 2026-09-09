"""Tests for dysonsphere_biology.volcano - and the full extension-discovery path.

`test_entry_point_*` prove the real installed entry point resolves (ds.extensions() /
ds.biology.volcano), which the monkeypatched core tests can't. The rest cover volcano's
classification, labeling, and - crucially - that its generated label sidecar is filtered by
ds.metadata.read(what="data"), the payoff of building on the ext.internal_data primitive.
"""

import altair as alt
import dysonsphere_biology as dsbio
import polars as pl
import pytest
import vl_convert as vlc

import dysonsphere as ds


def _df():
    return pl.DataFrame(
        {
            "gene": ["up1", "up2", "down1", "ns_fc", "ns_p", "zero_p"],
            "log2fc": [2.0, 3.5, -2.5, 0.2, 2.0, 1.8],
            "pvalue": [1e-3, 1e-6, 1e-4, 1e-3, 0.5, 0.0],
        }
    )


def _main_rows(chart):
    """The classified point dataset from a built volcano spec."""
    for rows in chart.to_dict().get("datasets", {}).values():
        if rows and "significance" in rows[0]:
            return rows
    raise AssertionError("no classified point dataset found")


def test_entry_point_registered():
    assert "biology" in ds.extensions()
    assert ds.biology.volcano is dsbio.volcano


def test_builds_layerchart_with_expected_layers():
    chart = ds.biology.volcano(_df())
    assert isinstance(chart, alt.LayerChart)
    # points + neutral legend carrier + 3 threshold rules (two vertical +-fc, one horizontal p)
    assert len(chart.to_dict()["layer"]) == 5


def test_no_threshold_lines():
    chart = ds.biology.volcano(_df(), thresholdLines=False)
    assert len(chart.to_dict()["layer"]) == 2


def test_significance_classification():
    rows = _main_rows(ds.biology.volcano(_df()))
    sig = {r["gene"]: r["significance"] for r in rows}
    assert sig["up1"] == "Gained" and sig["up2"] == "Gained"
    assert sig["down1"] == "Lost"
    # "Non-differential" (the call), not "ns" (significance): these two miss the fold-change or
    # p-value threshold and so are neither Gained nor Lost.
    assert sig["ns_fc"] == "Non-differential"  # |log2fc| below threshold
    assert sig["ns_p"] == "Non-differential"  # p above threshold


def test_pvalue_zero_is_finite():
    rows = _main_rows(ds.biology.volcano(_df()))
    zero = next(r for r in rows if r["gene"] == "zero_p")
    assert zero["neglog10p"] < 1e308  # clamped, not +inf


def test_pandas_input():
    pd = pytest.importorskip("pandas")
    chart = ds.biology.volcano(pd.DataFrame(_df().to_dict(as_series=False)))
    assert isinstance(chart, alt.LayerChart)


def test_label_top_n_count():
    chart = ds.biology.volcano(_df(), labels="gene", subset=2)
    # top-2 significant by combined score -> 2 gene labels (placed by labels)
    assert len(_label_texts(chart)) == 2


def test_label_top_n_selects_rows_when_names_repeat():
    df = pl.DataFrame(
        {
            "gene": ["duplicate", "duplicate", "other"],
            "log2fc": [4.0, 3.0, -2.0],
            "pvalue": [1e-8, 1e-7, 1e-6],
        }
    )
    assert _label_texts(ds.biology.volcano(df, labels="gene", subset=0)) == []
    assert _label_texts(ds.biology.volcano(df, labels="gene", subset=1)) == ["duplicate"]
    assert _label_texts(ds.biology.volcano(df, labels="gene", subset=2)) == ["duplicate", "duplicate"]


def test_label_significant_does_not_rematch_nondifferential_duplicate():
    df = pl.DataFrame(
        {
            "gene": ["duplicate", "duplicate", "other"],
            "log2fc": [3.0, 0.2, -2.0],
            "pvalue": [1e-8, 1e-8, 1e-6],
        }
    )
    assert _label_texts(ds.biology.volcano(df, labels="gene", subset="significant")) == ["duplicate", "other"]


def test_label_explicit_list_retains_value_matching_for_duplicates():
    df = pl.DataFrame(
        {
            "gene": ["duplicate", "duplicate", "other"],
            "log2fc": [3.0, 0.2, -2.0],
            "pvalue": [1e-8, 1e-8, 1e-6],
        }
    )
    assert _label_texts(ds.biology.volcano(df, labels="gene", subset=["duplicate"])) == ["duplicate", "duplicate"]


def test_label_list_selects_named_genes():
    chart = ds.biology.volcano(_df(), labels="gene", subset=["up1", "down1"])
    texts = _label_texts(chart)
    assert set(texts) == {"up1", "down1"}


def test_label_requires_gene_col():
    with pytest.raises(ValueError, match="requires labels"):
        ds.biology.volcano(_df(), subset=5)


def test_label_rejects_bool():
    with pytest.raises(ValueError, match="does not accept a bool"):
        ds.biology.volcano(_df(), labels="gene", subset=True)


def test_label_rejects_unknown_string():
    with pytest.raises(ValueError, match="not recognized"):
        ds.biology.volcano(_df(), labels="gene", subset="everything")


def test_palette_and_nscolor_override():
    # The established tuple order is (gained, lost); quantitative ranges run low to high.
    chart = ds.biology.volcano(_df(), palette=("#111111", "#222222"), nonDifferentialColor="#333333")
    spec = chart.to_dict()
    assert spec["layer"][0]["encoding"]["color"]["scale"]["range"] == ["#222222", "#111111"]
    assert spec["layer"][1]["encoding"]["color"]["scale"]["range"] == ["#333333"]


def test_palette_validation_and_case_sensitive_name():
    for palette in [("#111111", ""), ("#111111", 2), [], ["#111111", ""]]:
        with pytest.raises(ValueError, match="palette"):
            ds.biology.volcano(_df(), palette=palette)
    with pytest.raises(ValueError, match="unknown palette"):
        ds.biology.volcano(_df(), palette="Div1")


@pytest.mark.parametrize("palette", ["div1", ["#222222", "#dddddd"]])
def test_named_and_list_palette_override_locally(palette):
    scale = ds.biology.volcano(_df(), palette=palette).to_dict()["layer"][0]["encoding"]["color"]["scale"]
    assert scale["range"] == (ds.palettes.colors[palette] if isinstance(palette, str) else palette)


def test_default_palette_natively_inherits_diverging_range():
    ds.theme(divergingPalette="redblue")
    spec = ds.biology.volcano(_df()).to_dict()
    scale = spec["layer"][0]["encoding"]["color"]["scale"]
    assert scale == {"domain": [-1, 1], "domainMid": 0}
    assert spec["config"]["range"]["diverging"]["scheme"] == "redblue"


@pytest.mark.parametrize("darkmode,neutral", [(False, "#DBDBDB"), (True, "#2F2F2F")])
def test_rendered_default_neutral_legend_matches_point(darkmode, neutral):
    ds.theme(darkmode=darkmode)
    svg = vlc.vegalite_to_svg(ds.biology.volcano(_df(), thresholdLines=False).to_dict())
    points, swatches = _rendered_point_and_legend_fills(svg)
    assert neutral.lower() in points
    assert neutral.lower() in swatches


def test_rendered_custom_palette_and_neutral_have_matching_symbol_swatches():
    ds.theme(divergingPalette=["#112233", "#eeeeee", "#445566"])
    svg = vlc.vegalite_to_svg(ds.biology.volcano(_df(), thresholdLines=False, nonDifferentialColor="#778899").to_dict())
    for color in ("rgb(17, 34, 51)", "rgb(68, 85, 102)", "#778899"):
        assert color.lower() in _rendered_point_and_legend_fills(svg)[0]
        assert color.lower() in _rendered_point_and_legend_fills(svg)[1]


def test_legend_false_removes_both_legends():
    spec = ds.biology.volcano(_df(), legend=False).to_dict()
    assert "legends" not in vlc.vegalite_to_vega(spec)
    _, swatches = _rendered_point_and_legend_fills(vlc.vegalite_to_svg(spec))
    assert not swatches


@pytest.mark.parametrize(
    "diverging,endpoints",
    [
        (["#112233", "#eeeeee", "#445566"], {"rgb(17, 34, 51)", "rgb(68, 85, 102)"}),
        ("redblue", {"rgb(19, 75, 133)", "rgb(140, 13, 37)"}),
    ],
)
@pytest.mark.parametrize("darkmode,neutral", [(False, "#DBDBDB"), (True, "#2F2F2F")])
def test_callable_save_renders_inherited_palette_and_neutral(tmp_path, diverging, endpoints, darkmode, neutral):
    ds.theme(divergingPalette=diverging)
    out = tmp_path / "callable_volcano"
    ds.save(
        lambda: ds.biology.volcano(_df(), thresholdLines=False),
        out,
        format="svg",
        background="dark" if darkmode else "light",
    )
    fills = _rendered_fills(out.with_suffix(".svg").read_text())
    assert neutral.lower() in fills
    assert endpoints <= fills


def test_parent_composition_after_theme_switch_renders_inherited_scales():
    ds.theme(divergingPalette="redblue")
    chart = alt.hconcat(
        ds.biology.volcano(_df(), labels="gene", subset=2, thresholdLines=False),
        ds.biology.volcano(_df(), thresholdLines=False),
    )
    ds.theme(divergingPalette=["#112233", "#eeeeee", "#445566"])
    svg = vlc.vegalite_to_svg(chart.to_dict())
    points, swatches = _rendered_point_and_legend_fills(svg)
    for color in ("rgb(17, 34, 51)", "rgb(68, 85, 102)"):
        assert color in points
        assert color in swatches
    assert set(_label_texts(chart)) == {"up2", "zero_p"}


def test_axis_titles_render():
    # Regression guard: threshold rules must not null the base axis titles (the rule bug).
    import re

    import vl_convert as vlc

    svg = vlc.vegalite_to_svg(ds.biology.volcano(_df()).to_dict())

    def rendered(text):
        return bool(re.search(r"<text[^>]*>[^<]*" + re.escape(text) + r"[^<]*</text>", svg))

    assert rendered("log2 fold change")
    assert rendered("-log10 P")


def test_read_filters_generated_label_sidecar(tmp_path):
    # A user column matching the temporary row-index stem is preserved; selection chooses a
    # collision-free internal name and never passes that temporary column to ds.labels.
    df = _df().with_columns(pl.Series("__dysonsphere_volcano_row", range(_df().height)))
    out = tmp_path / "volcano"
    ds.save(lambda: ds.biology.volcano(df, labels="gene", subset=3), str(out), format="json")
    frame = ds.metadata.read(str(out) + ".json", what="data")
    # Only the user's frame returns (with volcano's derived columns) - the tagged label
    # sidecar and the threshold-rule sidecars are all filtered out.
    assert frame.height == df.height
    assert set(frame.columns) == set(df.columns) | {"neglog10p", "significance"}
    assert sorted(frame["__dysonsphere_volcano_row"].to_list()) == list(range(df.height))


def test_user_significance_score_column_is_preserved(tmp_path):
    helper = "__dysonsphere_volcano_significance_score"
    df = _df().with_columns(
        pl.Series("significance_score", range(_df().height)),
        pl.Series(helper, range(10, 10 + _df().height)),
        pl.Series(helper + "_", range(20, 20 + _df().height)),
    )
    out = tmp_path / "volcano_collision"
    ds.save(lambda: ds.biology.volcano(df), out, format="json")
    frame = ds.metadata.read(out.with_suffix(".json"), what="data")
    assert set(frame.columns) == set(df.columns) | {"neglog10p", "significance"}
    for column in ("significance_score", helper, helper + "_"):
        assert dict(zip(frame["gene"], frame[column])) == dict(zip(df["gene"], df[column]))


def test_provenance_records_biology_extension(tmp_path):
    # End-to-end via the REAL entry point: a saved volcano records dysonsphere-biology's version in
    # provenance (ext.tag_extension self-tagging -> save() scans it -> environment[dysonsphere-extensions]).
    import importlib.metadata

    out = tmp_path / "volcano"
    ds.save(lambda: ds.biology.volcano(_df()), str(out), format="json")
    env = ds.metadata.read(str(out) + ".json", what="metadata")["provenance"]["environment"]
    assert env["dysonsphere-extensions"] == {"biology": importlib.metadata.version("dysonsphere-biology")}


def _label_texts(chart):
    """Gene-label strings placed by labels (each encoded via alt.value)."""
    out = []

    def walk(node):
        if isinstance(node, dict):
            t = node.get("encoding", {}).get("text")
            if isinstance(t, dict) and "value" in t:
                out.append(t["value"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(chart.to_dict())
    return out


def _rendered_point_and_legend_fills(svg):
    """Return normalized fills for plotted points and symbol-legend descendants."""
    import xml.etree.ElementTree as et

    root = et.fromstring(svg)
    points = {
        element.attrib["fill"].lower()
        for element in root.iter()
        if element.attrib.get("aria-roledescription") == "point" and "fill" in element.attrib
    }
    swatches = set()
    for element in root.iter():
        if element.attrib.get("aria-roledescription") == "legend":
            swatches.update(child.attrib["fill"].lower() for child in element.iter() if "fill" in child.attrib)
    return points, swatches


def _rendered_fills(svg):
    """Return normalized fill colors from a saved SVG whose accessibility roles were stripped."""
    import re

    return {fill.lower() for fill in re.findall(r'fill="([^\"]+)"', svg)}
