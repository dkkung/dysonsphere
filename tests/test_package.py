"""Guards the package's public namespace - the per-module __all__ contract (v3.0).

Before v3.0 the star-imports in __init__.py ran without per-module __all__ lists, leaking
every top-level import (ds.np, ds.math, ds.json, even ds.field from dataclasses) onto the
public namespace. These tests pin the intended API surface so a new module-level import
can never silently become public again.
"""

import importlib
import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

import polars as pl
import pytest

import dysonsphere as ds

# importlib (not `from dysonsphere import ...`): the theme FUNCTION shadows its module on
# the package namespace, so attribute access would hand back the wrong object.
_MODULE_NAMES = [
    "annotations",
    "discovery",
    "export",
    "display_labels",
    "marks",
    "assembly",
    "multilabel",
    "nonlinear",
    "table",
    "theme",
]
_MODULES = [importlib.import_module(f"dysonsphere.{name}") for name in _MODULE_NAMES]


class TestPackageNamespace:
    def test_every_public_name_resolves(self):
        for name in ds.__all__:
            assert getattr(ds, name, None) is not None, f"ds.{name} in __all__ but missing"

    def test_package_all_is_union_of_module_alls(self):
        # __init__.__all__ is written out explicitly (self-documenting); this keeps it in
        # sync with star-imported modules plus namespaces, not their functions.
        union = {name for mod in _MODULES for name in mod.__all__}
        assert sorted(ds.__all__) == sorted(union | {"stats", "transforms", "metadata", "palettes", "palette"})

    @pytest.mark.parametrize(
        ("namespace", "names"),
        [
            ("metadata", ("read", "verify", "VerifyResult", "frame_checksum")),
            ("palettes", ("colors", "accents", "categorical", "export_swatches")),
        ],
    )
    def test_helpers_are_namespaced_only(self, namespace, names):
        module = getattr(ds, namespace)
        assert isinstance(module, ModuleType)
        assert module is importlib.import_module(f"dysonsphere.{namespace}")
        for name in names:
            assert name in module.__all__
            assert getattr(module, name) is not None
            assert name not in ds.__all__
            assert not hasattr(ds, name)

    def test_palette_callable_and_registry_survive_module_imports(self):
        palette = ds.palette
        colors = ds.palettes.colors
        assert callable(palette)
        for name in ("palettes", "theme", "marks", "metadata"):
            importlib.import_module(f"dysonsphere.{name}")
            assert ds.palette is palette is ds.palettes.palette
            assert ds.palettes.colors is colors
        assert ds.palettes is importlib.import_module("dysonsphere.palettes")

    def test_public_checksum_reexports_private_helper(self):
        utils = importlib.import_module("dysonsphere.utils")

        assert ds.metadata.frame_checksum is utils._frame_checksum
        assert "frame_checksum" not in utils.__all__
        assert not hasattr(utils, "frame_checksum")

    def test_stats_surface_is_namespaced_only(self):
        assert isinstance(ds.stats, ModuleType)
        assert ds.stats is importlib.import_module("dysonsphere.stats")
        assert sorted(ds.stats.__all__) == ["clear_stats", "comparisons", "correlation"]
        for name in ds.stats.__all__:
            assert callable(getattr(ds.stats, name))
            assert name not in ds.__all__
            assert not hasattr(ds, name), f"stats.{name} leaked onto the top namespace"
        for name in ("add_comparisons", "add_correlation"):
            assert not hasattr(ds.stats, name)
            assert not hasattr(ds, name)
            assert name not in ds.__all__
        for name in ("inference", "statistics"):
            assert importlib.util.find_spec(f"dysonsphere.{name}") is None
            assert not hasattr(ds, name)
            assert name not in ds.__all__

    def test_every_module_defines_all(self):
        for mod in [*_MODULES, ds.stats, ds.transforms, ds.metadata, ds.palettes, ds.ext]:
            assert hasattr(mod, "__all__"), f"{mod.__name__} lacks __all__ (would leak its imports)"

    def test_internal_utils_are_not_advertised(self):
        utils = importlib.import_module("dysonsphere.utils")
        assert utils.__all__ == []
        for old_name, private_name in (
            ("band_geometry", "_band_geometry"),
            ("count_n", "_count_n"),
            ("ensure_polars", "_ensure_polars"),
            ("BandGeometry", "_BandGeometry"),
        ):
            assert not hasattr(utils, old_name)
            assert hasattr(utils, private_name)
            assert old_name not in ds.__all__
            assert not hasattr(ds, old_name)
        assert "utils" not in ds.__all__

    def test_transforms_surface_is_namespaced_only(self):
        assert isinstance(ds.transforms, ModuleType)
        assert ds.transforms is importlib.import_module("dysonsphere.transforms")
        assert sorted(ds.transforms.__all__) == ["beeswarm", "jitter", "quasirandom"]
        for name in ds.transforms.__all__:
            assert callable(getattr(ds.transforms, name))
            assert name not in ds.__all__
            assert not hasattr(ds, name), f"transforms.{name} leaked onto the top namespace"
            old_name = f"add_{name}"
            assert not hasattr(ds.transforms, old_name)
            assert not hasattr(ds, old_name)
            assert old_name not in ds.__all__

    def test_annotation_public_names_without_aliases(self):
        annotations = importlib.import_module("dysonsphere.annotations")
        assert sorted(annotations.__all__) == ["labels", "rule", "shade", "text"]
        for name in annotations.__all__:
            assert callable(getattr(ds, name))
            assert getattr(ds, name) is getattr(annotations, name)
            assert name in ds.__all__
            old_name = f"add_{name}"
            assert not hasattr(annotations, old_name)
            assert not hasattr(ds, old_name)
            assert old_name not in ds.__all__

    @pytest.mark.parametrize("algorithm", ["jitter", "beeswarm", "quasirandom"])
    def test_studio_transform_calls_use_public_api(self, algorithm):
        studio = Path(__file__).resolve().parents[1] / "website/src/components/Studio.astro"
        templates = re.findall(r"`(df = ds\.[^`]+)`", studio.read_text(encoding="utf-8"))
        template = next(t for t in templates if ("${transform}" in t) == (algorithm != "jitter"))
        code = (
            template.replace("${transform}", algorithm)
            .replace("${q(x)}", json.dumps("group"))
            .replace("${q(y)}", json.dumps("value"))
        )
        assert "${" not in code
        data = pl.DataFrame({"group": ["a", "a", "a"], "value": [1.0, 2.0, 3.0]})
        namespace = {"ds": ds, "df": data}
        exec(code, namespace)
        result = namespace["df"]
        assert isinstance(result, pl.DataFrame)
        assert result.height == data.height
        assert f"{algorithm}_x" in result.columns

    def test_studio_applies_inward_ticks_from_resolved_theme(self):
        studio = Path(__file__).resolve().parents[1] / "website/src/components/Studio.astro"
        source = studio.read_text(encoding="utf-8")
        assert "spec.usermeta?.dysonsphere?.theme?.tickDirection === 'in'" in source
        assert "flipTicksInward(chartEl)" in source

    def test_studio_candidate_wheel_is_dev_only_and_passed_safely(self):
        runtime = Path(__file__).resolve().parents[1] / "website/src/lib/runtime.ts"
        source = runtime.read_text(encoding="utf-8")
        assert "import.meta.env.DEV && import.meta.env.PUBLIC_DYSONSPHERE_WHEEL_URL" in source
        assert ": 'dysonsphere';" in source
        assert "globals.set('_dysonsphere_install_target', DYSONSPHERE_INSTALL_TARGET)" in source
        assert "micropip.install(_dysonsphere_install_target, deps=False)" in source
        assert 'micropip.install("dysonsphere", deps=False)' not in source

    def test_labels_function_survives_module_imports(self):
        for name in ("display_labels", "marks", "annotations", "transforms"):
            importlib.import_module(f"dysonsphere.{name}")
            assert callable(ds.labels)
            assert ds.labels is importlib.import_module("dysonsphere.annotations").labels
        assert ds.label_expr is importlib.import_module("dysonsphere.display_labels").label_expr
        assert importlib.util.find_spec("dysonsphere.labels") is None

    def test_no_leaked_stdlib_or_thirdparty_names(self):
        # the exact names that leaked before v3.0
        for leaked in ("alt", "np", "pl", "math", "json", "os", "sys", "re", "Path", "Any", "cast", "field"):
            assert leaked not in ds.__all__, f"ds.__all__ leaks {leaked!r}"

    def test_ext_surface_is_namespaced_only(self):
        # dysonsphere.ext (the extension-author primitive surface) is bound as ds.ext but its
        # contents stay OFF the top namespace - `ext` is deliberately absent from _MODULE_NAMES
        # above because it is not star-imported (its __all__ must not join ds.__all__).
        from dysonsphere import ext

        assert callable(ext.opt) and callable(ext.internal_data)
        for name in ext.__all__:
            assert name not in ds.__all__, f"ext.{name} leaked onto the top namespace"
