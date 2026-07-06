"""Tests for the public extension-author primitive surface (dysonsphere/ext.py).

Beyond asserting the re-exports are the real internal objects, `test_dogfood_composite_*`
build a mini composite annotation exactly as an extension (e.g. dysonsphere-biology's volcano)
would - scatter over the user's frame plus a GENERATED label sidecar tagged via
`ext.internal_data` - and verify the surface actually delivers first-class behavior:
`read(what="data")` filters the sidecar, `opt` drives styling, the union types the return.
"""

import altair as alt
import polars as pl

import dysonsphere as ds
from dysonsphere import ext
from dysonsphere.discovery import _tag_extension
from dysonsphere.export import _AltairChart
from dysonsphere.theme import _opt
from dysonsphere.utils import _INTERNAL_COL, _internal_data


def test_reexports_are_the_internal_objects():
    # ext must re-export the real primitives (single source of truth), not copies.
    assert ext.opt is _opt
    assert ext.internal_data is _internal_data
    assert ext.AltairChart is _AltairChart
    assert ext.tag_extension is _tag_extension


def test_all_is_minimal():
    # Guard the surface: it grows only when a consumer justifies it (see ext.py docstring).
    # tag_extension was added for the volcano's provenance self-tagging.
    assert set(ext.__all__) == {"AltairChart", "internal_data", "opt", "tag_extension"}


def test_ext_namespaced_not_polluting_top_namespace():
    # ds.ext.opt is the access path; the primitives are NOT star-imported onto ds.*.
    assert ds.ext is ext
    assert not hasattr(ds, "opt")
    assert not hasattr(ds, "internal_data")


def test_opt_reads_theme_option():
    ds.theme()
    assert ext.opt("markSize") == _opt("markSize")
    assert isinstance(ext.opt("chartWidth"), (int, float))


def _volcano_like(df):
    """A composite an extension author might write, built only on the public surface."""
    ds.theme()
    points = alt.Chart(df).mark_circle().encode(x="log2fc:Q", y="neglog10p:Q")
    # Top hits get text labels - a GENERATED sidecar frame, so it must be tagged.
    hits = df.filter(pl.col("neglog10p") > 2.0).select(["log2fc", "neglog10p", "gene"])
    labels = (
        alt.Chart(ext.internal_data(hits))
        .mark_text(fontSize=ext.opt("fontSize"), dy=-5)
        .encode(x="log2fc:Q", y="neglog10p:Q", text="gene:N")
    )
    layered: ext.AltairChart = points + labels
    return layered


def _volcano_df():
    return pl.DataFrame(
        {
            "gene": ["a", "b", "c", "d"],
            "log2fc": [-2.5, 0.1, 1.8, 3.0],
            "neglog10p": [3.1, 0.2, 2.5, 4.0],
        }
    )


def test_dogfood_composite_builds():
    chart = _volcano_like(_volcano_df())
    assert isinstance(chart, alt.LayerChart)
    # The sidecar carries the sentinel column; the user frame does not.
    spec = chart.to_dict()
    datasets = spec.get("datasets", {})
    tagged = [name for name, rows in datasets.items() if rows and _INTERNAL_COL in rows[0]]
    assert len(tagged) == 1


def test_dogfood_read_filters_generated_sidecar(tmp_path):
    df = _volcano_df()
    ds.theme()
    out = tmp_path / "volcano"
    ds.save(lambda: _volcano_like(df), str(out), format="json")
    frame = ds.read(str(out) + ".json", what="data")
    # Only the user's frame comes back - the tagged label sidecar is filtered out.
    assert set(frame.columns) == {"gene", "log2fc", "neglog10p"}
    assert frame.height == df.height
