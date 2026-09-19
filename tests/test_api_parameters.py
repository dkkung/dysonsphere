"""Public parameter names must not drift back to the pre-v4 spellings."""

import inspect
from typing import Any, Callable

import altair as alt
import polars as pl
import pytest

import dysonsphere as ds
from dysonsphere import _statistics

_XY = {"df": "data", "xCol": "x", "yCol": "y"}
_RENAMES = {
    "mark_strip": _XY,
    "mark_violin": {**_XY, "boxplotSize": "boxplotWidth", "medianColor": "boxplotMedianColor"},
    "mark_table": {"df": "data", "palette": "stripePalette", "cellColor": "cellPalette"},
    "labels": {**_XY, "labelCol": "labels", "labels": "subset"},
    "add_multilabel": {"df": "data", "xCol": "x", "labelAlign": "labelPosition", "orientation": "lineOrientation"},
    "assemble": {"labelPadding": "labelOffset"},
    "stats.comparisons": {**_XY, "xOffsetCol": "xOffset", "save": "saveReport"},
    "stats.correlation": {**_XY, "groupCol": "groupBy", "save": "saveReport"},
    "transforms.jitter": {"df": "data"},
    "transforms.beeswarm": {"df": "data", "yCol": "column"},
    "transforms.quasirandom": {"df": "data", "yCol": "column"},
    "metadata.frame_checksum": {"df": "data"},
    "metadata.verify": {"df": "data"},
    "metadata.read": {"save": "saveReport"},
    "load": {"raw": "output"},
    "add_log_ticks": {"df": "data"},
    "add_pow_ticks": {"df": "data"},
    "biology.volcano": {
        "df": "data",
        "log2fcCol": "log2fc",
        "pvalueCol": "pvalue",
        "geneCol": "labels",
        "label": "subset",
        "nsColor": "nonDifferentialColor",
    },
    "biology.western_blot": {"padding": "stripSpacing"},
}


def _function(path: str) -> Callable[..., Any]:
    value: Any = ds
    for name in path.split("."):
        value = getattr(value, name)
    return value


@pytest.mark.parametrize("path", _RENAMES)
def test_parameter_names(path):
    signature = inspect.signature(_function(path))
    mapping = _RENAMES[path]
    assert set(mapping.values()) <= signature.parameters.keys()
    for old in set(mapping) - set(mapping.values()):
        assert old not in signature.parameters
        if not any(p.kind == inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values()):
            with pytest.raises(TypeError, match="unexpected keyword"):
                signature.bind_partial(**{old: None})


@pytest.mark.parametrize(
    ("path", "primary"),
    [
        ("transforms.jitter", ["data"]),
        ("transforms.beeswarm", ["data", "column", "groupBy"]),
        ("transforms.quasirandom", ["data", "column", "groupBy"]),
        ("palette", ["name", "n"]),
        ("palettes.categorical", ["members"]),
        ("palettes.export_swatches", ["directory"]),
        ("save", ["chart", "filename"]),
        ("show", ["chart"]),
        ("metadata.verify", ["figure", "data"]),
    ],
)
def test_controls_are_keyword_only(path, primary):
    signature = inspect.signature(_function(path))
    positional = [p.name for p in signature.parameters.values() if p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD]
    assert positional == primary
    for name, parameter in signature.parameters.items():
        if name not in primary:
            assert parameter.kind == inspect.Parameter.KEYWORD_ONLY
    with pytest.raises(TypeError, match="too many positional"):
        signature.bind_partial(*([None] * (len(primary) + 1)))


def test_removed_annotation_parameters_are_rejected():
    shade_signature = inspect.signature(ds.shade)
    multilabel_signature = inspect.signature(ds.add_multilabel)
    assert "xCol" not in shade_signature.parameters
    assert "yPadding" not in multilabel_signature.parameters
    with pytest.raises(TypeError, match="unexpected keyword"):
        ds.shade(categories=["A"], xCol="group")  # ty: ignore[unknown-argument]
    with pytest.raises(TypeError, match="unexpected keyword"):
        ds.add_multilabel(alt.Chart().mark_point(), categories=["A"], yPadding=1)  # ty: ignore[unknown-argument]
    with pytest.raises(TypeError, match="too many positional"):
        shade_signature.bind_partial(["A"], "group")


@pytest.mark.parametrize("path", ["create_config", "palettes.export_swatches"])
def test_directory_parameters_accept_paths(path):
    parameter = inspect.signature(_function(path)).parameters["directory"]
    assert "str" in str(parameter.annotation) and "Path" in str(parameter.annotation)


@pytest.mark.parametrize(
    ("path", "parameter"),
    [
        ("metadata.verify", "data"),
        ("transforms.jitter", "data"),
        ("transforms.beeswarm", "data"),
        ("transforms.quasirandom", "data"),
        ("add_log_ticks", "data"),
        ("add_pow_ticks", "data"),
        ("biology.volcano", "data"),
    ],
)
def test_dataframe_inputs_are_annotated(path, parameter):
    annotation = str(inspect.signature(_function(path)).parameters[parameter].annotation)
    assert "pl.DataFrame" in annotation and "pd.DataFrame" in annotation


def test_volcano_titles_allow_multiple_lines():
    signature = inspect.signature(_function("biology.volcano"))
    assert "list[str]" in str(signature.parameters["xTitle"].annotation)
    assert "list[str]" in str(signature.parameters["yTitle"].annotation)


def test_labels_separates_content_from_selection():
    ds.theme()
    data = pl.DataFrame({"x": [1.0, 2.0, 3.0], "y": [2.0, 1.0, 4.0], "name": ["a", "b", "c"]})
    chart = ds.labels(data=data, x="x", y="y", labels="name", subset=["b"])
    assert isinstance(chart, alt.LayerChart)
    spec = chart.to_dict()
    text = [layer["encoding"]["text"]["value"] for layer in spec["layer"] if layer["mark"]["type"] == "text"]
    assert text == ["b"]


def test_renamed_axes_preserve_statistics_column_identity():
    ds.theme()
    data = pl.DataFrame({"height": [1.0, 2.0, 3.0], "weight": [2.0, 3.0, 5.0]})
    chart = ds.stats.correlation(data=data, x="height", y="weight", saveReport=False)
    assert isinstance(chart, alt.LayerChart)
    record = next(iter(_statistics._REPORTS.values()))
    assert record["x"] == "height"
    assert record["y"] == "weight"
    assert record["dataChecksum"] == ds.metadata.frame_checksum(data=data)


def test_blot_rejects_old_forwarded_parameters():
    from PIL import Image

    ds.theme()
    image = Image.new("RGB", (10, 2), "gray")
    with pytest.raises(TypeError, match="padding"):
        ds.biology.western_blot(image, {"dose": [True]}, ["a"], padding=2)
