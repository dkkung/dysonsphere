import ast
import inspect
import json
import re
import shutil
import xml.etree.ElementTree as ET
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import altair as alt
import polars as pl
import pytest
import vl_convert as vlc

import dysonsphere as ds

SKILL = Path(__file__).parents[1] / "skills" / "dysonsphere"
EXPECTED_EXAMPLES = {"scatter", "panels", "comparisons", "correlation", "backgrounds"}
STATISTICS = {"comparisons", "correlation"}


def _python_examples(skill: Path) -> dict[str, tuple[str, Path]]:
    examples = {}
    for document in sorted(skill.rglob("*.md")):
        for match in re.finditer(r"^```python\s*\n(.*?)^```\s*$", document.read_text(), re.MULTILINE | re.DOTALL):
            code = match.group(1)
            marker = re.match(r"# example: ([a-z][a-z0-9-]*)\n", code)
            assert marker, f"unidentified Python fence in {document.relative_to(skill)}"
            example_id = marker.group(1)
            assert example_id not in examples, f"duplicate example ID: {example_id}"
            examples[example_id] = (code, document)
    return examples


@pytest.fixture(scope="module")
def portable_skill(tmp_path_factory):
    destination = tmp_path_factory.mktemp("portable-skill") / SKILL.name
    shutil.copytree(SKILL, destination)
    return destination


@pytest.fixture(autouse=True)
def _restore_altair_theme():
    active = alt.theme.active
    options = dict(alt.theme.options)
    with ExitStack() as stack:
        stack.enter_context(alt.theme.enable(active))  # ty: ignore[invalid-argument-type]
        alt.theme.options = options
        yield


def test_skill_frontmatter_uses_bounded_standard_fields(portable_skill):
    lines = (portable_skill / "SKILL.md").read_text().splitlines()
    assert lines[0] == "---"
    end = lines.index("---", 1)
    frontmatter = lines[1:end]
    top_level = [line for line in frontmatter if line and not line.startswith(" ")]
    keys = [line.partition(":")[0] for line in top_level]
    assert len(keys) == len(set(keys))
    assert set(keys) == {"name", "description", "license", "compatibility", "metadata"}

    name_lines = [line for line in frontmatter if line.startswith("name:")]
    description_lines = [line for line in frontmatter if line.startswith("description:")]
    assert len(name_lines) == len(description_lines) == 1
    name = name_lines[0].partition(":")[2].strip()
    assert name == portable_skill.name
    assert 1 <= len(name) <= 64 and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)

    description_index = frontmatter.index(description_lines[0])
    assert description_lines[0] == "description: >-"
    continuation = []
    for line in frontmatter[description_index + 1 :]:
        if line.startswith("  "):
            continuation.append(line.strip())
        else:
            break
    description = " ".join(continuation)
    assert 1 <= len(description) <= 1024

    license_value = next(line.partition(":")[2].strip() for line in top_level if line.startswith("license:"))
    assert license_value == "MIT"
    compatibility_index = frontmatter.index("compatibility: >-")
    compatibility_lines = []
    for line in frontmatter[compatibility_index + 1 :]:
        if line.startswith("  "):
            compatibility_lines.append(line.strip())
        else:
            break
    compatibility = " ".join(compatibility_lines)
    assert 1 <= len(compatibility) <= 500
    assert "Python 3.11+" in compatibility and "Dysonsphere 4.0.0" in compatibility
    metadata_index = frontmatter.index("metadata:")
    assert frontmatter[metadata_index + 1 :] == ['  dysonsphere: "4.0.0"']


def test_relative_markdown_links_are_internal_and_resolve(portable_skill):
    for document in portable_skill.rglob("*.md"):
        for target in re.findall(r"(?<!!)\[[^]]*]\(([^)]+)\)", document.read_text()):
            assert ":" not in target and not target.startswith(("/", "#"))
            resolved = (document.parent / target.split("#", 1)[0]).resolve()
            assert resolved.is_relative_to(portable_skill.resolve())
            assert resolved.is_file()


def test_example_inventory_is_complete_and_unique(portable_skill):
    assert set(_python_examples(portable_skill)) == EXPECTED_EXAMPLES


def test_examples_keep_default_formats_and_raster_density(portable_skill):
    for example_id, (code, _) in _python_examples(portable_skill).items():
        saves = [
            node
            for node in ast.walk(ast.parse(code))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "save"
        ]
        assert saves, example_id
        assert all(keyword.arg not in {"format", "ppi"} for call in saves for keyword in call.keywords), example_id


def _saved_y_scales(path):
    compiled = vlc.vegalite_to_vega(json.loads(path.read_text()))
    return [scale for scale in compiled["scales"] if scale["name"].endswith("_y")]


def test_strip_parent_encoding_does_not_fix_nested_assembled_scale(tmp_path):
    ds.theme()
    data = pl.DataFrame({"group": ["A"] * 4 + ["B"] * 4, "value": [1.0, 1.2, 1.4, 1.6, 2.0, 2.2, 2.4, 2.6]})
    domain = alt.Scale(domain=[0, 4])
    figure = ds.assemble(
        [
            (lambda: alt.Chart(data).mark_point().encode(x="value:Q", y=alt.Y("value:Q", scale=domain)), 180, 130, "a"),
            (
                lambda: ds.mark_strip(data, "group", "value", ["A", "B"]).encode(y=alt.Y("value:Q", scale=domain)),
                120,
                130,
                "b",
            ),
        ]
    )
    stem = tmp_path / "parent-domain"
    ds.save(figure, stem, format="json", background="light")
    scales = _saved_y_scales(stem.with_suffix(".json"))
    assert scales[0]["domain"] == [0, 4]
    assert isinstance(scales[1]["domain"], dict)


@pytest.mark.parametrize("example_id", sorted(EXPECTED_EXAMPLES))
def test_python_example_exports_are_valid(portable_skill, tmp_path, monkeypatch, example_id):
    code, document = _python_examples(portable_skill)[example_id]
    work = tmp_path / example_id
    work.mkdir()
    monkeypatch.chdir(work)
    filename = f"{document}#{example_id}"
    namespace: dict[str, Any] = {"__name__": "__main__"}
    exec(compile(code, filename, "exec"), namespace)

    suffixes = ("_light", "_dark") if example_id == "backgrounds" else ("",)
    assert {path.name for path in work.iterdir()} == {
        f"skill_{example_id}{suffix}.{extension}" for suffix in suffixes for extension in ("svg", "json")
    }
    preview_dir = tmp_path / "inspection"
    preview_dir.mkdir()
    default_ppi = inspect.signature(ds.save).parameters["ppi"].default
    assert isinstance(default_ppi, int)
    metadata = []
    specs = []
    for suffix in suffixes:
        stem = work / f"skill_{example_id}{suffix}"
        svg = ET.parse(stem.with_suffix(".svg"))
        assert svg.getroot().tag.rsplit("}", 1)[-1] == "svg"
        # Inspect the already-corrected SVG without changing the example's default deliverables.
        svg.getroot().insert(
            0,
            ET.Element(
                "{http://www.w3.org/2000/svg}rect",
                {"width": "100%", "height": "100%", "fill": "black" if suffix == "_dark" else "white"},
            ),
        )
        preview = preview_dir / f"{stem.name}.png"
        preview.write_bytes(vlc.svg_to_png(ET.tostring(svg.getroot(), encoding="unicode"), ppi=default_ppi))
        assert preview.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        specs.append(json.loads(stem.with_suffix(".json").read_text()))
        verification = ds.metadata.verify(stem.with_suffix(".json"))
        assert verification.specValid is True and verification.ok
        metadata.append(ds.metadata.read(stem.with_suffix(".json"), what="metadata"))

        statistics = ds.metadata.read(stem.with_suffix(".json"), what="statistics")
        assert len(statistics) == (1 if example_id in STATISTICS else 0)
        if example_id == "comparisons":
            record = statistics[0]
            assert record["test"] == "mannwhitneyu"
            assert [(group["label"], group["n"]) for group in record["groups"]] == [
                ("Control", 6),
                ("Treatment", 6),
            ]
            assert record["comparisons"]["pairs"][0]["group1"] == "Control"
            assert record["comparisons"]["pairs"][0]["group2"] == "Treatment"
        elif example_id == "correlation":
            record = statistics[0]
            assert record["method"] == "pearson"
            assert record["n"] == 6

    if example_id == "panels":
        endpoint = namespace["endpoint"]
        assert endpoint.group_by("formulation").len().sort("formulation")["len"].to_list() == [4, 4]
        summaries = endpoint.group_by("formulation").agg(
            pl.col("extension_mm").mean().alias("mean"),
            pl.col("extension_mm").std().alias("sd"),
        )
        observed = {row["formulation"]: (row["mean"], row["sd"]) for row in summaries.iter_rows(named=True)}
        assert observed["Reference"] == pytest.approx((3.15, 0.3872983346))
        assert observed["Modified"] == pytest.approx((1.85, 0.3872983346))

        saved = work / "skill_panels"
        compiled = vlc.vegalite_to_vega(json.loads(saved.with_suffix(".json").read_text()))
        scales = [scale for scale in compiled["scales"] if scale["name"].endswith("_y")]
        assert len(scales) == 2 and [scale["domain"] for scale in scales] == [[0, 4], [0, 4]]
        assert all(scale["range"][-1] == 0 for scale in scales)
        child_heights = [signal["value"] for signal in compiled["signals"] if signal["name"].endswith("childHeight")]
        assert child_heights == [130, 130]
        aggregate_ops = {
            operation
            for item in compiled["data"]
            for transform in item.get("transform", [])
            if transform.get("type") == "aggregate"
            for operation in transform["ops"]
        }
        assert {"mean", "stdev"} <= aggregate_ops

        root = ET.parse(saved.with_suffix(".svg")).getroot()
        visible_text = " ".join("".join(element.itertext()) for element in root.iter() if element.tag.endswith("text"))
        assert "All specimens" in visible_text and "n = 8 per formulation" in visible_text
        assert "3 mN endpoint" in visible_text and "Mean ± SD; n = 4 each" in visible_text
        tick_y = {}
        for element in root.iter():
            if (
                element.tag.endswith("text")
                and element.attrib.get("text-anchor") == "end"
                and element.text in {"0", "4"}
            ):
                match = re.fullmatch(r"translate\([^,]+,([^)]+)\)", element.attrib["transform"])
                assert match
                tick_y.setdefault(element.text, []).append(float(match.group(1)))
        assert len(tick_y["0"]) == len(tick_y["4"]) == 2
        assert tick_y["0"][0] == pytest.approx(tick_y["0"][1])
        assert tick_y["4"][0] == pytest.approx(tick_y["4"][1])

    if example_id == "backgrounds":
        assert alt.theme.options["darkmode"] is False
        colors = [spec["mark"]["color"] for spec in specs]
        assert colors[0] != colors[1] and all(re.fullmatch(r"#[0-9A-Fa-f]{6}", color) for color in colors)
        provenance = [item["provenance"] for item in metadata]
        assert provenance[0]["exportIdentifier"] == provenance[1]["exportIdentifier"]
        assert provenance[0]["dataChecksum"] == provenance[1]["dataChecksum"]
