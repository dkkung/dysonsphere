import importlib.util

import dysonsphere as ds


def _load_demo():
    spec = importlib.util.spec_from_file_location("demo_palette_families", "scripts/demo_palette_families.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_compiled_review_keeps_all_family_ranges_independent():
    ds.theme()
    vega = _load_demo().build_review().to_dict(format="vega")
    ranges = [
        scale["range"]
        for scale in vega["scales"]
        if scale["name"].endswith("_color") and isinstance(scale.get("range"), list)
    ]
    for name in ("cat1", "cat2", "cat3", "cat4", "div1", "div2", "div3", "div4"):
        assert ds.palettes.colors[name] in ranges
