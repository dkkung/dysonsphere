"""Tests for the extension discovery layer (dysonsphere/discovery.py + package __getattr__)."""

import importlib.metadata
import json
import types

import altair as alt
import polars as pl
import pytest

import dysonsphere as ds
from dysonsphere import _statistics, metadata
from dysonsphere import discovery as ext


@pytest.fixture(autouse=True)
def configured_theme():
    """Initialize the theme only for tests that serialize charts."""
    ds.theme()


def _fake_entry_point(name, module):
    """An EntryPoint whose .load() returns ``module``.

    A real EntryPoint.load() imports the dotted path in ``value``; registering the module in
    sys.modules under a unique name lets load() resolve to our stand-in without a real install.
    """
    import sys

    sys.modules[module.__name__] = module
    return importlib.metadata.EntryPoint(name=name, value=module.__name__, group=ext._ENTRY_POINT_GROUP)


@pytest.fixture
def fake_biology(monkeypatch):
    """Register a fake ``biology`` extension via monkeypatched entry-point discovery."""
    module = types.ModuleType("_fake_dysonsphere_biology")
    module.volcano = lambda: "volcano!"  # ty: ignore[unresolved-attribute]
    ep = _fake_entry_point("biology", module)
    monkeypatch.setattr(ext, "_extension_entry_points", lambda: {"biology": ep})
    yield module
    # __getattr__ caches the resolved module in the package namespace; drop it so it can't leak.
    ds.__dict__.pop("biology", None)


def test_extensions_empty(monkeypatch):
    monkeypatch.setattr(ext, "_extension_entry_points", dict)
    assert ext.extensions() == []


def test_extensions_lists_installed_sorted(monkeypatch):
    monkeypatch.setattr(ext, "_extension_entry_points", lambda: {"physics": object(), "biology": object()})
    assert ext.extensions() == ["biology", "physics"]


def test_load_extension_returns_module(fake_biology):
    assert ext.load_extension("biology") is fake_biology


def test_load_extension_missing_raises_with_available(monkeypatch):
    monkeypatch.setattr(ext, "_extension_entry_points", dict)
    with pytest.raises(ImportError, match="no dysonsphere extension named 'biology'.*no extensions are installed"):
        ext.load_extension("biology")


def test_load_extension_missing_lists_installed(monkeypatch):
    monkeypatch.setattr(ext, "_extension_entry_points", lambda: {"physics": object()})
    with pytest.raises(ImportError, match="installed extensions: physics"):
        ext.load_extension("astronomy")


def test_getattr_resolves_extension(fake_biology):
    assert ds.biology is fake_biology
    assert ds.biology.volcano() == "volcano!"


def test_getattr_caches_resolved_extension(fake_biology):
    ds.biology  # trigger resolution + cache
    assert ds.__dict__["biology"] is fake_biology


def test_getattr_unknown_raises_attributeerror(monkeypatch):
    monkeypatch.setattr(ext, "_extension_entry_points", dict)
    with pytest.raises(AttributeError, match="has no attribute 'definitely_not_installed'"):
        ds.definitely_not_installed


def test_extensions_public_via_namespace():
    # extensions() / load_extension() are exported on the top-level namespace.
    assert callable(ds.extensions)
    assert callable(ds.load_extension)


# ── Extension-usage provenance markers (discovery._tag_extension / _used_extensions) ──────────


def _tiny_chart():
    return alt.Chart(pl.DataFrame({"x": [1.0, 2.0], "y": [1.0, 2.0]})).mark_point().encode(x="x:Q", y="y:Q")


def _ext_marker_names(spec):
    out = []

    def walk(o):
        if isinstance(o, dict):
            n = o.get("name")
            if isinstance(n, str) and n.startswith(ext._EXT_MARKER_PREFIX):
                out.append(n)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(spec)
    return out


def test_tag_extension_marks_chart():
    tagged = ext._tag_extension(_tiny_chart(), "biology")
    names = _ext_marker_names(tagged.to_dict())
    assert len(names) == 1 and names[0].startswith("__dysonsphere_ext_biology_")


def test_tag_extension_marker_survives_composition():
    # The whole point of using a view-name marker (not usermeta): it survives `+`.
    tagged = ext._tag_extension(alt.layer(_tiny_chart()), "biology")
    composed = tagged + _tiny_chart()
    assert any(name.startswith("__dysonsphere_ext_biology_") for name in _ext_marker_names(composed.to_dict()))


def test_tag_extension_names_are_unique_for_composition():
    composed = alt.hconcat(ext._tag_extension(_tiny_chart(), "biology"), ext._tag_extension(_tiny_chart(), "biology"))
    names = _ext_marker_names(composed.to_dict())
    assert len(names) == len(set(names)) == 2


def test_tag_extension_carries_statistics_marker_through_spec_roundtrip():
    marker = "__dysonsphere_0123456789abcdef_7"
    spec = ext._tag_extension(_tiny_chart().properties(name=marker), "biology").to_dict()
    roundtripped = json.loads(json.dumps(spec))

    parsed = ext._parse_extension_marker(roundtripped["name"])
    assert parsed is not None and parsed[0] == "biology"
    _, underlying = ext._unwrap_extension_markers(roundtripped["name"])
    assert underlying == marker and _statistics._marker_hash(underlying) == "0123456789abcdef"
    metadata._strip_markers(roundtripped)
    assert "name" not in roundtripped


def test_tag_extension_restores_user_view_name_when_stripped():
    spec = ext._tag_extension(_tiny_chart().properties(name="user-view"), "biology").to_dict()
    metadata._strip_markers(spec)
    assert spec["name"] == "user-view"


def test_nested_extension_tags_preserve_all_identity():
    marker = "__dysonsphere_0123456789abcdef_7"
    tagged = ext._tag_extension(ext._tag_extension(_tiny_chart().properties(name=marker), "biology"), "other")
    spec = tagged.to_dict()

    assert ext._unwrap_extension_markers(spec["name"]) == (["other", "biology"], marker)
    _, underlying = ext._unwrap_extension_markers(spec["name"])
    assert underlying == marker and _statistics._marker_hash(underlying) == "0123456789abcdef"
    fake = types.SimpleNamespace(dist=types.SimpleNamespace(version="1.0"))
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(ext, "_extension_entry_points", lambda: {"biology": fake, "other": fake})
        assert ext._used_extensions(spec) == {"biology": "1.0", "other": "1.0"}
    metadata._strip_markers(spec)
    assert "name" not in spec


def test_composed_tagged_export_renders_retains_stats_and_is_reproducible(tmp_path, monkeypatch):
    """Fresh callable tags stay unique without entering rendered or metadata identity."""
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    data = pl.DataFrame(
        {
            "group": ["A"] * 8 + ["B"] * 8,
            "value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0],
        }
    )

    def built():
        points = alt.Chart(data).mark_point().encode(x="group:N", y="value:Q")
        comparison = ds.stats.comparisons(data, "group", "value", pairs=[("A", "B")], test="ttest_ind")
        return alt.hconcat(ext._tag_extension(points + comparison, "biology"), ext._tag_extension(points, "biology"))

    ds.save(built, str(tmp_path / "first"), format=["json", "svg"], background=["light"])
    ds.save(built, str(tmp_path / "second"), format=["json", "svg"], background=["light"])

    assert "<svg" in (tmp_path / "first.svg").read_text()
    assert len(ds.metadata.read(tmp_path / "first.json", what="statistics")) == 1
    assert (tmp_path / "first.json").read_bytes() == (tmp_path / "second.json").read_bytes()


def test_used_extensions_maps_marker_to_version(monkeypatch):
    fake = types.SimpleNamespace(dist=types.SimpleNamespace(version="9.9.9"))
    monkeypatch.setattr(ext, "_extension_entry_points", lambda: {"biology": fake})
    spec = ext._tag_extension(_tiny_chart(), "biology").to_dict()
    assert ext._used_extensions(spec) == {"biology": "9.9.9"}


def test_used_extensions_empty_without_markers():
    assert ext._used_extensions(_tiny_chart().to_dict()) == {}


def test_used_extensions_skips_uninstalled(monkeypatch):
    # A marker for an extension with no installed entry point isn't recorded (can't version it).
    monkeypatch.setattr(ext, "_extension_entry_points", dict)
    spec = ext._tag_extension(_tiny_chart(), "ghost").to_dict()
    assert ext._used_extensions(spec) == {}
