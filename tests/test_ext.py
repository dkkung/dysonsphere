"""Tests for the public extension API (dysonsphere/ext.py).

Beyond asserting the re-exports are the real internal objects, `test_dogfood_composite_*`
build a small composite annotation like an extension (for example, dysonsphere-biology's volcano)
would - scatter over the user's frame plus generated label data tagged via `ext.internal_data` -
and verify the API matches core chart behavior: `read(what="data")` filters the generated data,
`opt` drives styling, and the union types the return.
"""

import altair as alt
import polars as pl

import dysonsphere as ds
from dysonsphere import ext
from dysonsphere.export import _AltairChart
from dysonsphere.theme import _opt
from dysonsphere.utils import _INTERNAL_COL, _internal_data


def test_reexports_are_the_internal_objects():
    # ext must re-export the real primitives (single source of truth), not copies.
    assert ext.opt is _opt
    assert ext.internal_data is _internal_data
    assert ext.AltairChart is _AltairChart
    assert ext.tag_extension.__module__ == "dysonsphere.ext"


def test_all_is_minimal():
    # Guard the surface: it grows only when a consumer justifies it (see ext.py docstring).
    # tag_extension was added for the volcano's provenance self-tagging.
    assert set(ext.__all__) == {"AltairChart", "internal_data", "opt", "tag_extension"}


def test_biology_first_import_preserves_namespace_and_chart_type_identity():
    """The extension can import first without a cycle or root helper leakage."""
    import subprocess
    import sys

    code = """
import dysonsphere_biology
import dysonsphere as ds
from dysonsphere import export, ext
assert ext.AltairChart is export._AltairChart
assert callable(ds.extensions) and callable(ds.load_extension)
assert ds.extensions is ext.extensions and ds.load_extension is ext.load_extension
assert not hasattr(ds, "discovery")
for name in ("AltairChart", "internal_data", "opt", "tag_extension"):
    assert not hasattr(ds, name)
"""
    subprocess.run([sys.executable, "-c", code], check=True)


def test_ext_namespaced_not_polluting_top_namespace():
    # ds.ext.opt is the access path; the primitives are NOT star-imported onto ds.*.
    assert ds.ext is ext
    assert not hasattr(ds, "opt")
    assert not hasattr(ds, "internal_data")


def test_opt_reads_theme_option():
    ds.theme()
    assert ext.opt("markSize") == _opt("markSize")
    assert isinstance(ext.opt("width"), (int, float))


def _volcano_like(df):
    """A composite an extension author might write, built only on the public API."""
    ds.theme()
    points = alt.Chart(df).mark_circle().encode(x="log2fc:Q", y="neglog10p:Q")
    # Top hits get text labels from generated data, so it must be tagged.
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
    # Generated data carries the internal marker column; the user frame does not.
    spec = chart.to_dict()
    datasets = spec.get("datasets", {})
    tagged = [name for name, rows in datasets.items() if rows and _INTERNAL_COL in rows[0]]
    assert len(tagged) == 1


def test_dogfood_read_filters_generated_sidecar(tmp_path):
    df = _volcano_df()
    ds.theme()
    out = tmp_path / "volcano"
    ds.save(lambda: _volcano_like(df), str(out), format="json")
    frame = ds.metadata.read(str(out) + ".json", what="data")
    # Only the user's frame comes back; tagged label data is filtered out.
    assert set(frame.columns) == {"gene", "log2fc", "neglog10p"}
    assert frame.height == df.height
