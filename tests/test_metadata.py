import json
import re
import struct
import sys
import uuid
import zlib
from copy import deepcopy
from typing import Any

import altair as alt
import polars as pl
import pytest

from dysonsphere.export import save
from dysonsphere.metadata import (
    _call_expression,
    _inject_png_metadata,
    _resolve_timestamp,
    _source_date_epoch,
)
from dysonsphere.theme import theme
from dysonsphere.utils import _ROW_HASH_PREFIX

_PROV_ORDER = [
    "user",
    "script",
    "chart",  # best-effort call-site capture; always present here (tests save() from source files)
    "timestamp",
    "environment",
    "vegaliteChecksum",
    "exportIdentifier",
    "dataChecksum",
]
_ENV_ORDER = ["os", "python", "altair", "vl_convert", "dysonsphere", "numpy", "scipy", "polars"]


@pytest.fixture(autouse=True)
def default_theme():
    # metadata tests exercise all three formats, so make save() emit them by default
    theme(saveFormat=["svg", "png", "json"])


@pytest.fixture
def simple_chart():
    df = pl.DataFrame({"x": ["A", "B", "C"], "y": [1.0, 2.0, 3.0]})
    return alt.Chart(df).mark_point().encode(x="x:N", y="y:Q")


class TestSaveUsermeta:
    @pytest.fixture
    def stats_chart(self):
        import numpy as np

        import dysonsphere as ds

        cats = ["A", "B", "C"]
        rng = np.random.default_rng(0)
        df = pl.DataFrame(
            {"g": [c for c in cats for _ in range(20)], "v": np.concatenate([rng.normal(m, 1, 20) for m in (1, 2, 3)])}
        )
        return ds.mark_strip(df, "g", "v", cats) + ds.stats.comparisons(df, "g", "v", test="anova", categories=cats)

    def _usermeta(self, tmp_path, name="out"):
        return json.loads((tmp_path / f"{name}.json").read_text())["usermeta"]

    def _svg_metadata(self, tmp_path, name="out"):
        svg = (tmp_path / f"{name}.svg").read_text(encoding="utf-8")
        m = re.search(r'<metadata id="dysonsphere"><!\[CDATA\[(.*?)\]\]></metadata>', svg, re.DOTALL)
        return json.loads(m.group(1)) if m else None

    def _png_dysonsphere_chunk(self, tmp_path, name="out"):
        data = (tmp_path / f"{name}.png").read_bytes()
        i = 8
        while i < len(data):
            length = struct.unpack(">I", data[i + 4 - 4 : i + 4])[0]
            ctype = data[i + 4 : i + 8]
            chunk = data[i + 8 : i + 8 + length]
            if ctype == b"iTXt" and chunk.split(b"\x00", 1)[0] == b"dysonsphere":
                # after the keyword null come 4 more nulls (compflag/method/lang/transkw), then text
                text = chunk.split(b"\x00", 1)[1].lstrip(b"\x00")
                return json.loads(text.decode("utf-8"))
            i += 12 + length
            if ctype == b"IEND":
                break
        return None

    def test_provenance_block_present(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), background=["light"])
        prov = self._usermeta(tmp_path)["dysonsphere"]["provenance"]
        assert list(prov) == _PROV_ORDER  # order matches the prose
        assert prov["timestamp"].endswith("Z") and "T" in prov["timestamp"]  # ISO-8601

    def test_statistics_records_embedded(self, stats_chart, tmp_path):
        save(stats_chart, str(tmp_path / "out"), background=["light"])
        stats = self._usermeta(tmp_path)["dysonsphere"]["statistics"]
        assert len(stats) == 1
        rec = stats[0]
        assert rec["kind"] == "omnibus" and rec["omnibus"]["name"] == "ANOVA"
        assert isinstance(rec["omnibus"]["pvalue"], float)  # real number, not text
        assert len(rec["comparisons"]["pairs"]) == 3

    def test_correlation_record_embedded(self, tmp_path):
        import numpy as np

        import dysonsphere as ds

        rng = np.random.default_rng(0)
        x = rng.uniform(0, 10, 40)
        df = pl.DataFrame({"x": x, "y": 0.9 * x + rng.normal(0, 1, 40)})
        chart = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q") + ds.stats.correlation(df, "x", "y")
        save(chart, str(tmp_path / "out"), background=["light"])
        rec = self._usermeta(tmp_path)["dysonsphere"]["statistics"][0]
        assert rec["kind"] == "correlation" and rec["method"] == "pearson"
        assert isinstance(rec["coefficient"]["value"], float) and rec["fit"]["slope"] is not None

    def test_no_statistics_key_without_add_comparisons(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), background=["light"])
        block = self._usermeta(tmp_path)["dysonsphere"]
        assert "statistics" not in block and "statisticsBindings" not in block

    def test_merges_with_user_usermeta(self, tmp_path):
        df = pl.DataFrame({"x": [1, 2, 3], "y": [1.0, 2.0, 3.0]})
        chart = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q").properties(usermeta={"project": "Apollo"})
        save(chart, str(tmp_path / "out"), background=["light"])
        um = self._usermeta(tmp_path)
        assert um["project"] == "Apollo"  # user's key preserved
        assert "provenance" in um["dysonsphere"]

    def test_no_usermeta_when_metadata_disabled(self, stats_chart, tmp_path):
        save(stats_chart, str(tmp_path / "out"), saveMetadata=False, background=["light"])
        assert "usermeta" not in (tmp_path / "out.json").read_text()

    def test_svg_embeds_structured_metadata(self, stats_chart, tmp_path):
        save(stats_chart, str(tmp_path / "out"), background=["light"])
        block = self._svg_metadata(tmp_path)
        assert block is not None
        assert list(block["provenance"]) == _PROV_ORDER
        assert block["statistics"][0]["omnibus"]["name"] == "ANOVA"

    def test_svg_metadata_preserves_unicode(self, stats_chart, tmp_path):
        # η² must survive as literal UTF-8 in the SVG (ensure_ascii=False), not ²
        save(stats_chart, str(tmp_path / "out"), background=["light"])
        assert self._svg_metadata(tmp_path)["statistics"][0]["omnibus"]["effect"]["symbol"] == "η²"

    def test_png_embeds_structured_metadata(self, stats_chart, tmp_path):
        save(stats_chart, str(tmp_path / "out"), background=["light"])
        block = self._png_dysonsphere_chunk(tmp_path)
        assert block is not None
        assert block["statistics"][0]["omnibus"]["name"] == "ANOVA"
        assert "provenance" in block

    def test_no_svg_png_metadata_when_disabled(self, stats_chart, tmp_path):
        save(stats_chart, str(tmp_path / "out"), saveMetadata=False, background=["light"])
        assert self._svg_metadata(tmp_path) is None
        assert self._png_dysonsphere_chunk(tmp_path) is None

    def _svg_report(self, tmp_path, section="statistics", name="out"):
        svg = (tmp_path / f"{name}.svg").read_text(encoding="utf-8")
        m = re.search(rf'<metadata id="dysonsphere-report-{section}">(.*?)</metadata>', svg, re.DOTALL)
        return m.group(1) if m else None

    def _png_report_text(self, tmp_path, section="statistics", name="out"):
        data = (tmp_path / f"{name}.png").read_bytes()
        i = 8
        while i < len(data):
            length = struct.unpack(">I", data[i : i + 4])[0]
            ctype = data[i + 4 : i + 8]
            chunk = data[i + 8 : i + 8 + length]
            if ctype == b"iTXt" and chunk.split(b"\x00", 1)[0] == f"dysonsphere-report-{section}".encode():
                return chunk.split(b"\x00", 1)[1].lstrip(b"\x00").decode("utf-8")
            i += 12 + length
            if ctype == b"IEND":
                break
        return None

    def test_report_embedded_by_default(self, stats_chart, tmp_path):
        save(stats_chart, str(tmp_path / "out"), background=["light"])
        report = self._usermeta(tmp_path)["dysonsphere"]["report"]  # JSON member: {section: text}
        assert report["statistics"].startswith("Statistics")  # nested under the report container
        assert "\n" in self._svg_report(tmp_path)  # SVG per-section readable channel, real newlines
        assert self._png_report_text(tmp_path).startswith("Statistics")  # PNG per-section chunk

    def test_report_not_in_description(self, stats_chart, tmp_path):
        save(stats_chart, str(tmp_path / "out"), description="my caption", background=["light"])
        spec = json.loads((tmp_path / "out.json").read_text())
        assert spec["description"] == "my caption"  # description is the user's text only

    def test_report_not_duplicated_in_structured_blob(self, stats_chart, tmp_path):
        # the report is its own JSON member / readable channel, not baked into the structured blob
        save(stats_chart, str(tmp_path / "out"), background=["light"])
        assert "report" not in self._svg_metadata(tmp_path)
        assert "report" not in self._png_dysonsphere_chunk(tmp_path)

    def test_embed_report_false_suppresses_it(self, stats_chart, tmp_path):
        save(stats_chart, str(tmp_path / "out"), embedReport=False, background=["light"])
        block = self._usermeta(tmp_path)["dysonsphere"]
        assert "statistics" in block and "report" not in block  # structured kept, report dropped
        assert self._svg_report(tmp_path) is None and self._png_report_text(tmp_path) is None

    def test_description_in_structured_block_all_formats(self, simple_chart, tmp_path):
        # save(description=...) must ride inside usermeta.dysonsphere in every format's blob.
        save(simple_chart, str(tmp_path / "out"), description="figure 1")
        assert self._usermeta(tmp_path)["dysonsphere"]["description"] == "figure 1"  # JSON
        assert self._svg_metadata(tmp_path)["description"] == "figure 1"  # SVG structured blob
        assert self._png_dysonsphere_chunk(tmp_path)["description"] == "figure 1"  # PNG structured blob

    def test_description_is_last_after_report(self, stats_chart, tmp_path):
        save(stats_chart, str(tmp_path / "out"), description="figure 1", background=["light"])
        keys = list(self._usermeta(tmp_path)["dysonsphere"])
        assert keys[-1] == "description"  # last member
        assert keys.index("report") < keys.index("description")  # after report

    def test_no_description_key_when_none(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"))
        assert "description" not in self._usermeta(tmp_path)["dysonsphere"]
        assert "description" not in self._svg_metadata(tmp_path)

    def test_provenance_environment(self, simple_chart, tmp_path):
        import importlib.metadata

        save(simple_chart, str(tmp_path / "out"), background=["light"])
        import platform

        deps = self._usermeta(tmp_path)["dysonsphere"]["provenance"]["environment"]
        # Exact match also guards that a pure-core figure has NO `extensions` key (added only when used).
        assert list(deps) == _ENV_ORDER  # os first, then the toolchain, in order
        assert deps["os"] == platform.platform()
        assert deps["vl_convert"] == importlib.metadata.version("vl-convert-python")  # renderer (now a project dep)
        assert deps["numpy"] == importlib.metadata.version("numpy")
        assert deps["scipy"] == importlib.metadata.version("scipy")
        assert deps["polars"] == importlib.metadata.version("polars")

    def test_provenance_records_used_extensions(self, simple_chart, tmp_path, monkeypatch):
        # An extension that PRODUCED the figure (tagged via ext.tag_extension) is recorded in
        # environment["dysonsphere-extensions"] with its version, grouped directly after dysonsphere.
        import types

        from dysonsphere import discovery, ext

        fake = types.SimpleNamespace(dist=types.SimpleNamespace(version="9.9.9"))
        monkeypatch.setattr(discovery, "_extension_entry_points", lambda: {"biology": fake})
        save(ext.tag_extension(simple_chart, "biology"), str(tmp_path / "out"), background=["light"])
        deps = self._usermeta(tmp_path)["dysonsphere"]["provenance"]["environment"]
        assert deps["dysonsphere-extensions"] == {"biology": "9.9.9"}
        keys = list(deps)
        assert keys[keys.index("dysonsphere") + 1] == "dysonsphere-extensions"  # sits under dysonsphere

    def test_theme_baked_as_ds_theme_args(self, stats_chart, tmp_path):
        import dysonsphere as ds

        ds.theme(width=180, sigFigs=2)
        save(stats_chart, str(tmp_path / "out"), background=["light"])
        theme = self._usermeta(tmp_path)["dysonsphere"]["theme"]
        assert theme["width"] == 180 and theme["sigFigs"] == 2
        assert "tickWidth" not in theme  # only _BUILTIN_DEFAULTS keys (valid ds.theme() kwargs)

    @pytest.mark.parametrize("initial_darkmode", [False, True])
    def test_automatic_mark_fill_metadata_matches_each_render_mode(self, simple_chart, tmp_path, initial_darkmode):
        import dysonsphere as ds

        ds.theme(darkmode=initial_darkmode)
        ds.save(simple_chart, tmp_path / "modes", format="json", background=["light", "dark"])
        light_spec = json.loads((tmp_path / "modes_light.json").read_text())
        dark_spec = json.loads((tmp_path / "modes_dark.json").read_text())
        light = light_spec["usermeta"]["dysonsphere"]
        dark = dark_spec["usermeta"]["dysonsphere"]
        assert light["theme"]["markFill"] == "#DBDBDB"
        assert dark["theme"]["markFill"] == "#9D9D9D"
        assert light_spec["config"]["point"]["fill"] == light["theme"]["markFill"]
        assert dark_spec["config"]["point"]["fill"] == dark["theme"]["markFill"]
        assert light["themeAutomatic"] == dark["themeAutomatic"] == ["markFill"]
        assert "_markFillAuto" not in light["theme"] and "_markFillAuto" not in dark["theme"]
        assert alt.theme.options["darkmode"] is initial_darkmode

    def test_explicit_mark_fill_metadata_is_pinned_and_load_preserves_origin(self, simple_chart, tmp_path):
        import dysonsphere as ds
        from dysonsphere.theme import _opt

        ds.theme(darkmode=False, markFill="#DBDBDB")
        ds.save(simple_chart, tmp_path / "explicit", format="json", background="dark")
        block = json.loads((tmp_path / "explicit.json").read_text())["usermeta"]["dysonsphere"]
        assert block["theme"]["markFill"] == "#DBDBDB"
        assert "themeAutomatic" not in block
        ds.load(tmp_path / "explicit.json")
        assert _opt("markFill") == "#DBDBDB"

        ds.theme(darkmode=True)
        ds.save(simple_chart, tmp_path / "automatic", format="json", background="dark")
        loaded = ds.load(tmp_path / "automatic.json")
        assert not isinstance(loaded, dict)
        assert _opt("markFill") == "#9D9D9D"
        ds.save(loaded, tmp_path / "reexport", format="json", background="light")
        reexported = json.loads((tmp_path / "reexport.json").read_text())["usermeta"]["dysonsphere"]
        assert reexported["theme"]["markFill"] == "#DBDBDB"
        assert reexported["themeAutomatic"] == ["markFill"]

    def test_load_automatic_fill_ignores_current_toml_and_survives_rebuild(self, simple_chart, tmp_path, monkeypatch):
        import dysonsphere as ds
        from dysonsphere.theme import _opt, _temporary_theme

        ds.theme(darkmode=True)
        ds.save(simple_chart, tmp_path / "saved-auto", format="json", background="dark")
        monkeypatch.chdir(tmp_path)
        (tmp_path / "dysonsphere.toml").write_text('[default]\nmarkFill = "#123456"\n', encoding="utf-8")

        loaded = ds.load(tmp_path / "saved-auto.json")
        assert not isinstance(loaded, dict)
        assert _opt("markFill") == "#9D9D9D"
        assert alt.theme.options["_markFillAuto"] is True
        with _temporary_theme({"width": 240}):
            assert _opt("markFill") == "#9D9D9D"
            assert alt.theme.options["_markFillAuto"] is True
        ds.save(loaded, tmp_path / "opposite", format="json", background="light")
        spec = json.loads((tmp_path / "opposite.json").read_text())
        block = spec["usermeta"]["dysonsphere"]
        assert spec["config"]["point"]["fill"] == "#DBDBDB"
        assert block["theme"]["markFill"] == "#DBDBDB"
        assert block["themeAutomatic"] == ["markFill"]

        ds.theme(darkmode=True, markFill="#DBDBDB")
        ds.save(simple_chart, tmp_path / "saved-explicit", format="json", background="dark")
        ds.load(tmp_path / "saved-explicit.json")
        assert _opt("markFill") == "#DBDBDB"
        assert alt.theme.options["_markFillAuto"] is False


def _capture(chart=None):
    # Mimics save()'s capture: reads the CALLER's frame, so the return is the source text of
    # this helper's first argument at its call site.
    return _call_expression(sys._getframe(1))


class TestCallExpression:
    # Results are assigned before asserting: pytest's assertion rewriting recompiles `assert`
    # lines, and a call inside one may carry rewritten source positions. Plain assignments are
    # untouched, so the captured positions match the file on disk.

    def test_variable_name(self):
        fig = object()
        got = _capture(fig)
        assert got == "fig"

    def test_inline_composition(self):
        got = _capture(1 + 2 + 3)
        assert got == "1 + 2 + 3"

    def test_lambda_verbatim(self):
        got = _capture(lambda: 1 + 2)
        assert got == "lambda: 1 + 2"

    def test_multiline_argument_kept_verbatim(self):
        # fmt: off
        got = _capture(
            1
            + 2
        )
        # fmt: on
        assert got == "1\n            + 2"

    def test_keyword_chart_argument(self):
        fig = object()
        got = _capture(chart=fig)
        assert got == "fig"

    def test_source_unavailable_returns_none(self):
        # exec'd code has filename "<string>" - no linecache source, so capture backs off
        ns = {"_capture": _capture, "fig": object()}
        exec("result = _capture(fig)", ns)
        assert ns["result"] is None

    def test_wrapper_records_wrapper_parameter(self):
        # Honest limitation: capture reads the DIRECT call site, so a user wrapper's own
        # parameter name is what gets recorded, not the caller-of-the-wrapper's composition.
        def wrapper(chart):
            return _capture(chart)

        fig = object()
        got = wrapper(fig)
        assert got == "chart"

    def test_save_embeds_chart_key(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), background=["light"], format="json")
        prov = json.loads((tmp_path / "out.json").read_text())["usermeta"]["dysonsphere"]["provenance"]
        assert prov["chart"] == "simple_chart"

    def test_chart_key_omitted_without_source(self, simple_chart, tmp_path):
        ns = {"save": save, "c": simple_chart, "p": str(tmp_path / "out")}
        exec("save(c, p, background=['light'], format='json')", ns)
        prov = json.loads((tmp_path / "out.json").read_text())["usermeta"]["dysonsphere"]["provenance"]
        assert "chart" not in prov


class TestReadLoad:
    @pytest.fixture
    def saved(self, tmp_path):
        import numpy as np

        import dysonsphere as ds

        ds.theme(width=180, sigFigs=2, saveFormat=["svg", "png", "json"])
        rng = np.random.default_rng(0)
        df = pl.DataFrame({"g": ["A"] * 30 + ["B"] * 30, "v": np.r_[rng.normal(0, 1, 30), rng.normal(2, 1, 30)]})
        chart = alt.Chart(df).mark_boxplot().encode(x="g:N", y="v:Q") + ds.stats.comparisons(
            df, "g", "v", [("A", "B")], categories=["A", "B"]
        )
        ds.save(chart, str(tmp_path / "t"), background=["light"])
        return tmp_path

    @pytest.mark.parametrize("as_path", [False, True])
    def test_read_report_from_each_format(self, saved, as_path):
        import dysonsphere as ds

        for name in ("t.json", "t.svg", "t.png"):
            path = saved / name if as_path else str(saved / name)
            r = ds.metadata.read(path)  # what="report" default
            assert isinstance(r, str) and r.startswith("Statistics")

    def test_read_statistics_exact_floats(self, saved):
        import dysonsphere as ds

        stats = ds.metadata.read(str(saved / "t.png"), what="statistics")
        assert isinstance(stats, list)
        p = stats[0]["comparisons"]["pairs"][0]["pvalue"]
        assert isinstance(p, float) and 0 < p < 1e-6  # exact, not the floored display value

    def test_read_metadata_has_all_keys(self, saved):
        import dysonsphere as ds

        m = ds.metadata.read(str(saved / "t.svg"), what="metadata")
        assert isinstance(m, dict)
        assert set(m) == {"provenance", "statistics", "statisticsBindings", "theme", "themeAutomatic", "report"}
        assert m["theme"]["width"] == 180
        # report is a container keyed by section, not a bare string
        assert list(m["report"]) == ["statistics", "provenance"]  # consistent order across formats
        assert m["report"]["statistics"].startswith("Statistics")
        assert m["report"]["provenance"].startswith("Provenance")

    def test_read_report_rerenders_without_embedded_prose(self, tmp_path):
        import numpy as np

        import dysonsphere as ds

        df = pl.DataFrame({"g": ["A"] * 20 + ["B"] * 20, "v": np.r_[np.zeros(20), np.ones(20)]})
        chart = alt.Chart(df).mark_boxplot().encode(x="g:N", y="v:Q") + ds.stats.comparisons(
            df, "g", "v", [("A", "B")], pvalues=[0.01], categories=["A", "B"]
        )
        ds.save(chart, str(tmp_path / "u"), embedReport=False, background=["light"])
        # no embedded prose, but statistics are present → read re-renders the table
        r = ds.metadata.read(str(tmp_path / "u.png"))
        assert isinstance(r, str) and r.startswith("Statistics")

    def test_report_provenance_sentence(self, saved):
        import dysonsphere as ds

        m = ds.metadata.read(str(saved / "t.png"), what="metadata")
        assert isinstance(m, dict)
        prov = m["report"]["provenance"]
        assert prov.startswith("Provenance\n") and "Generated by " in prov
        assert m["provenance"]["environment"]["dysonsphere"] in prov  # renders the actual version

    def test_stats_free_chart_reads_provenance(self, tmp_path):
        import dysonsphere as ds

        chart = alt.Chart(pl.DataFrame({"x": [1, 2, 3], "y": [1.0, 2.0, 3.0]})).mark_point().encode(x="x:Q", y="y:Q")
        ds.save(chart, str(tmp_path / "bare"), background=["light"])
        m = ds.metadata.read(str(tmp_path / "bare.json"), what="metadata")
        assert isinstance(m, dict)
        assert list(m["report"]) == ["provenance"]  # no statistics section, but provenance is there
        r = ds.metadata.read(str(tmp_path / "bare.svg"))  # what="report" — no longer blank
        assert isinstance(r, str) and r.startswith("Provenance")

    def test_read_invalid_what_raises(self, saved):
        import dysonsphere as ds

        with pytest.raises(ValueError, match="what must be"):
            ds.metadata.read(str(saved / "t.json"), what="bogus")

    def test_read_unsupported_extension_raises(self, tmp_path):
        import dysonsphere as ds

        (tmp_path / "x.txt").write_text("hi")
        with pytest.raises(ValueError, match="supports .png"):
            ds.metadata.read(str(tmp_path / "x.txt"))

    def test_load_returns_composable_object(self, saved):
        import dysonsphere as ds

        obj = ds.load(str(saved / "t.json"))
        assert isinstance(obj, alt.LayerChart)
        assert isinstance(obj + alt.Chart().mark_point(), alt.LayerChart)  # composes

    def test_load_reapplies_theme(self, saved):
        import dysonsphere as ds

        ds.theme(width=999)  # clobber
        ds.load(str(saved / "t.json"))  # applyTheme=True default
        assert alt.theme.options["width"] == 180  # restored from the baked theme

    def test_load_apply_theme_false_leaves_theme(self, saved):
        import dysonsphere as ds

        ds.theme(width=999)
        ds.load(str(saved / "t.json"), applyTheme=False)
        assert alt.theme.options["width"] == 999  # untouched

    def test_load_raw_returns_spec_dict(self, saved):
        import dysonsphere as ds

        ds.theme(width=999)
        spec = ds.load(str(saved / "t.json"), raw=True)
        assert isinstance(spec, dict) and "config" in spec  # raw spec, theme config intact
        assert alt.theme.options["width"] == 999  # globals untouched

    def test_load_requires_json(self, saved):
        import dysonsphere as ds

        with pytest.raises(ValueError, match="Vega-Lite JSON"):
            ds.load(str(saved / "t.png"))

    def test_load_resave_preserves_owned_statistics(self, tmp_path):
        import dysonsphere as ds

        groups = pl.DataFrame({"g": ["A"] * 5 + ["B"] * 5, "v": [1.0, 2, 3, 4, 5, 3, 4, 5, 6, 7]})
        xy = pl.DataFrame({"x": [1.0, 2, 3, 4, 5], "y": [1.1, 2.2, 2.8, 4.1, 5.2]})
        left = alt.Chart(groups).mark_point().encode(x="g:N", y="v:Q") + ds.stats.comparisons(
            groups, "g", "v", [("A", "B")], categories=["A", "B"]
        )
        right = alt.Chart(xy).mark_point().encode(x="x:Q", y="y:Q") + ds.stats.correlation(xy, "x", "y")
        ds.save(alt.hconcat(left, right), str(tmp_path / "original"), format="json", background="light")

        loaded = ds.load(tmp_path / "original.json")
        assert isinstance(loaded, alt.HConcatChart)
        ds.stats.clear_stats()
        ds.stats.correlation(pl.DataFrame({"x": [1, 2, 3], "y": [3, 2, 1]}), "x", "y")
        ds.save(loaded, str(tmp_path / "again"), format="json", background="light")
        records = ds.metadata.read(tmp_path / "again.json", what="statistics")
        assert [record["kind"] for record in records] == ["pairwise", "correlation"]
        assert list(ds.metadata.read(tmp_path / "again.json", what="metadata")["report"]) == [
            "statistics",
            "provenance",
        ]

        left_loaded = loaded.hconcat[0]
        ds.save(left_loaded, str(tmp_path / "left"), format="json", background="light")  # ty: ignore[invalid-argument-type]
        assert [record["kind"] for record in ds.metadata.read(tmp_path / "left.json", what="statistics")] == [
            "pairwise"
        ]
        base_loaded = left_loaded.layer[0]
        ds.save(base_loaded, str(tmp_path / "without-stat"), format="json", background="light")  # ty: ignore[invalid-argument-type]
        assert ds.metadata.read(tmp_path / "without-stat.json", what="statistics") == []

    def test_loaded_statistics_get_fresh_owners_and_do_not_grow(self, tmp_path):
        import dysonsphere as ds

        data = pl.DataFrame({"g": ["A"] * 4 + ["B"] * 4, "v": [1.0, 2, 3, 4, 2, 3, 4, 5]})
        chart = alt.Chart(data).mark_point().encode(x="g:N", y="v:Q") + ds.stats.comparisons(
            data, "g", "v", [("A", "B")], categories=["A", "B"]
        )
        ds.save(chart, str(tmp_path / "one"), format="json", background="light")
        first = ds.load(tmp_path / "one.json")
        second = ds.load(tmp_path / "one.json")
        assert isinstance(first, alt.LayerChart) and isinstance(second, alt.LayerChart)
        composed = alt.hconcat(first, second)
        names = re.findall(r"__dsstatistics_owner_[0-9a-f]{48}", json.dumps(composed.to_dict()))
        assert len(names) == len(set(names)) == 2

        ds.save(composed, str(tmp_path / "two"), format="json", background="light")
        assert len(ds.metadata.read(tmp_path / "two.json", what="statistics")) == 1  # content-hash deduplication
        before = json.loads((tmp_path / "two.json").read_text())["usermeta"]["dysonsphere"]
        twice_loaded = ds.load(tmp_path / "two.json")
        assert isinstance(twice_loaded, alt.HConcatChart)
        ds.save(twice_loaded, str(tmp_path / "three"), format="json", background="light")
        after = json.loads((tmp_path / "three.json").read_text())["usermeta"]["dysonsphere"]
        assert len(after["statistics"]) == len(before["statistics"]) == 1
        assert len(after["statisticsBindings"]) == len(before["statisticsBindings"]) == 2

    def test_load_rejects_malformed_statistics_bindings(self, tmp_path):
        import dysonsphere as ds

        data = pl.DataFrame({"g": ["A"] * 4 + ["B"] * 4, "v": [1.0, 2, 3, 4, 2, 3, 4, 5]})
        chart = alt.Chart(data).mark_point().encode(x="g:N", y="v:Q") + ds.stats.comparisons(
            data, "g", "v", [("A", "B")], categories=["A", "B"]
        )
        ds.save(chart, str(tmp_path / "bad"), format="json", background="light")
        spec = json.loads((tmp_path / "bad.json").read_text())
        spec["usermeta"]["dysonsphere"]["statisticsBindings"] = {
            "f" * 16 + "0" * 32: {"record": "f" * 16, "context": "sha256:" + "0" * 64}
        }
        (tmp_path / "bad.json").write_text(json.dumps(spec))
        with pytest.raises(ValueError, match="unknown statistical record"):
            ds.load(tmp_path / "bad.json")

    def test_loaded_statistics_reject_source_data_edit(self, tmp_path):
        import dysonsphere as ds

        data = pl.DataFrame({"g": ["A"] * 4 + ["B"] * 4, "v": [1.0, 2, 3, 4, 2, 3, 4, 5]})
        chart = alt.Chart(data).mark_point().encode(x="g:N", y="v:Q") + ds.stats.comparisons(
            data, "g", "v", [("A", "B")], categories=["A", "B"]
        )
        ds.save(chart, str(tmp_path / "source"), format="json", background="light")
        loaded = ds.load(tmp_path / "source.json")
        assert isinstance(loaded, alt.LayerChart)
        edited_spec = loaded.to_dict()

        def edit_rows(value):
            if isinstance(value, dict):
                rows = (value.get("data") or {}).get("values") if isinstance(value.get("data"), dict) else None
                if isinstance(rows, list) and rows and "v" in rows[0]:
                    rows[0]["v"] = 99.0
                for child in value.values():
                    edit_rows(child)
            elif isinstance(value, list):
                for child in value:
                    edit_rows(child)

        edit_rows(edited_spec)
        for key in ("$schema", "background", "config", "datasets"):
            edited_spec.pop(key, None)
        edited = alt.LayerChart.from_dict(edited_spec)
        with pytest.raises(ValueError, match="preserved statistical context changed"):
            ds.save(edited, str(tmp_path / "edited"), format="json", background="light")
        assert not (tmp_path / "edited.json").exists()

    def test_loaded_statistics_allow_presentation_edits_but_reject_mappings(self, tmp_path):
        import dysonsphere as ds

        data = pl.DataFrame({"g": ["A"] * 4 + ["B"] * 4, "v": [1.0, 2, 3, 4, 2, 3, 4, 5]})
        chart = alt.Chart(data).mark_point(color="red").encode(x="g:N", y="v:Q") + ds.stats.comparisons(
            data, "g", "v", [("A", "B")], categories=["A", "B"]
        )
        ds.save(chart, str(tmp_path / "source"), format="json", background="light")
        loaded = ds.load(tmp_path / "source.json")
        assert isinstance(loaded, alt.LayerChart)
        styled = loaded.properties(width=310, height=190, title="Presentation only")
        styled.layer[0].mark.color = "blue"
        ds.save(styled, str(tmp_path / "styled"), format="json", background="light")
        assert len(ds.metadata.read(tmp_path / "styled.json", what="statistics")) == 1

        changed = loaded.to_dict()
        changed["layer"][0]["encoding"]["y"]["aggregate"] = "mean"
        for key in ("$schema", "background", "config", "datasets"):
            changed.pop(key, None)
        with pytest.raises(ValueError, match="preserved statistical context changed"):
            ds.save(alt.LayerChart.from_dict(changed), str(tmp_path / "changed"), format="json", background="light")

    def test_same_record_in_distinct_contexts_has_distinct_guards(self, tmp_path):
        import dysonsphere as ds

        data = pl.DataFrame({"g": ["A"] * 4 + ["B"] * 4, "v": [1.0, 2, 3, 4, 2, 3, 4, 5]})
        left = alt.Chart(data).mark_point().encode(x="g:N", y="v:Q") + ds.stats.comparisons(
            data, "g", "v", [("A", "B")], categories=["A", "B"]
        )
        right = alt.Chart(data).mark_bar().encode(x="g:N", y="mean(v):Q") + ds.stats.comparisons(
            data, "g", "v", [("A", "B")], categories=["A", "B"]
        )
        ds.save(alt.hconcat(left, right), str(tmp_path / "contexts"), format="json", background="light")
        block = json.loads((tmp_path / "contexts.json").read_text())["usermeta"]["dysonsphere"]
        assert len(block["statistics"]) == 1
        assert len({binding["context"] for binding in block["statisticsBindings"].values()}) == 2

    def test_loaded_statistics_preflight_all_backgrounds_before_writing(self, tmp_path):
        import dysonsphere as ds

        data = pl.DataFrame({"g": ["A"] * 4 + ["B"] * 4, "v": [1.0, 2, 3, 4, 2, 3, 4, 5]})
        chart = alt.Chart(data).mark_point().encode(x="g:N", y="v:Q") + ds.stats.comparisons(
            data, "g", "v", [("A", "B")], categories=["A", "B"]
        )
        ds.save(chart, str(tmp_path / "source"), format="json", background="light")
        loaded = ds.load(tmp_path / "source.json")
        assert isinstance(loaded, alt.LayerChart)
        calls = 0

        def variant():
            nonlocal calls
            calls += 1
            if not alt.theme.options["darkmode"]:
                return loaded
            changed = loaded.to_dict()
            changed["layer"][0]["data"]["values"][0]["v"] = 99
            for key in ("$schema", "background", "config", "datasets"):
                changed.pop(key, None)
            return alt.LayerChart.from_dict(changed)

        (tmp_path / "out_light.json").write_text("untouched")
        with pytest.raises(ValueError, match="preserved statistical context changed"):
            ds.save(variant, str(tmp_path / "out"), format="json", background=["light", "dark"])
        assert calls == 2
        assert (tmp_path / "out_light.json").read_text() == "untouched"
        assert not (tmp_path / "out_dark.json").exists()

    def test_statistics_with_external_data_context_is_unsupported(self, tmp_path):
        import dysonsphere as ds

        data = pl.DataFrame({"g": ["A"] * 4 + ["B"] * 4, "v": [1.0, 2, 3, 4, 2, 3, 4, 5]})
        base = alt.Chart("https://example.invalid/data.json").mark_point().encode(x="g:N", y="v:Q")
        chart = base + ds.stats.comparisons(data, "g", "v", [("A", "B")], categories=["A", "B"])
        with pytest.raises(ValueError, match="external data"):
            ds.save(chart, str(tmp_path / "external"), format="json", background="light")

    def test_statistics_context_rejects_lookup_and_runtime_parameters(self):
        from dysonsphere.metadata import _statistics_context

        spec: dict[str, Any] = {
            "datasets": {"lookup": [{"id": 1, "z": 10}]},
            "data": {"values": [{"id": 1, "y": 2}]},
            "transform": [{"lookup": "id", "from": {"data": {"name": "lookup"}, "key": "id", "fields": ["z"]}}],
            "mark": "point",
        }
        with pytest.raises(ValueError, match="lookup transforms"):
            _statistics_context(spec, spec)
        external = deepcopy(spec)
        external["transform"][0]["from"]["data"] = {"url": "https://example.invalid/data.csv"}
        with pytest.raises(ValueError, match="lookup transforms"):
            _statistics_context(external, external)

        selected = {
            "data": {"values": [{"x": 1}]},
            "params": [{"name": "brush", "select": {"type": "interval", "encodings": ["x"]}}],
            "transform": [{"filter": {"param": "brush"}}],
            "mark": "point",
        }
        with pytest.raises(ValueError, match="runtime parameters"):
            _statistics_context(selected, selected)
        for key, value in (("params", None), ("selection", {})):
            malformed = {"data": {"values": [{"x": 1}]}, "mark": "point", key: value}
            with pytest.raises(ValueError, match="runtime parameters"):
                _statistics_context(malformed, malformed)

    def test_statistics_context_expression_boundary(self):
        from dysonsphere.metadata import _statistics_context

        static: dict[str, Any] = {
            "data": {"values": [{"x": 1}]},
            "transform": [{"calculate": "isValid(datum.x) ? abs(datum.x) : 0", "as": "clean"}],
            "mark": "point",
        }
        assert re.fullmatch(r"[0-9a-f]{64}", _statistics_context(static, static))
        for expression in (
            "now()",
            "random()",
            "data('other')[0].x",
            "brush.x",
            'datum[random() > 0.5 ? "x" : "y"]',
            'datum[now() > 0 ? "x" : "y"]',
            "datum[brush.field]",
        ):
            dynamic = deepcopy(static)
            dynamic["transform"][0]["calculate"] = expression
            with pytest.raises(ValueError, match="deterministic datum"):
                _statistics_context(dynamic, dynamic)
        for expression in ("datum['x']", "datum[datum.key]", "datum.x * 1e-3 + 0x10"):
            allowed = deepcopy(static)
            allowed["transform"][0]["calculate"] = expression
            assert re.fullmatch(r"[0-9a-f]{64}", _statistics_context(allowed, allowed))

    @pytest.mark.parametrize(
        "spec, message",
        [
            (
                {"data": {"values": [{"x": 1}]}, "mark": {"type": "text", "text": {"expr": "now()"}}},
                "deterministic datum",
            ),
            (
                {"data": {"values": [{"x": 1}]}, "mark": {"type": "point", "x": {"expr": "random()"}}},
                "deterministic datum",
            ),
            (
                {"data": {"values": [{"x": 1}]}, "transform": [{"sample": 1}], "mark": "point"},
                "sample transforms",
            ),
        ],
    )
    def test_statistics_context_rejects_dynamic_mark_and_sample(self, spec, message):
        from dysonsphere.metadata import _statistics_context

        with pytest.raises(ValueError, match=message):
            _statistics_context(spec, spec)

    def test_load_inlines_named_lookup_dataset(self, tmp_path):
        import dysonsphere as ds

        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
            "datasets": {"main": [{"id": 1, "y": 2}], "lookup": [{"id": 1, "z": 10}]},
            "data": {"name": "main"},
            "transform": [{"lookup": "id", "from": {"data": {"name": "lookup"}, "key": "id", "fields": ["z"]}}],
            "mark": "point",
            "encoding": {"x": {"field": "z", "type": "quantitative"}, "y": {"field": "y", "type": "quantitative"}},
        }
        path = tmp_path / "lookup.json"
        path.write_text(json.dumps(spec))
        loaded = ds.load(path, applyTheme=False)
        assert isinstance(loaded, alt.Chart)
        loaded_spec = loaded.to_dict()
        recovered = list(loaded_spec["datasets"].values())
        assert spec["datasets"]["main"] in recovered
        lookup_data = loaded_spec["transform"][0]["from"]["data"]
        assert lookup_data.get("values") == spec["datasets"]["lookup"]

    def test_cleared_live_marker_does_not_bind_to_same_imported_record(self, tmp_path):
        import dysonsphere as ds

        data = pl.DataFrame({"g": ["A"] * 4 + ["B"] * 4, "v": [1.0, 2, 3, 4, 2, 3, 4, 5]})

        def built():
            return alt.Chart(data).mark_point().encode(x="g:N", y="v:Q") + ds.stats.comparisons(
                data, "g", "v", [("A", "B")], categories=["A", "B"]
            )

        ds.save(built(), str(tmp_path / "source"), format="json", background="light")
        ds.load(tmp_path / "source.json")  # retain identical imported content
        live = built()
        ds.stats.clear_stats()
        ds.save(live, str(tmp_path / "cleared"), format="json", background="light")
        block = ds.metadata.read(tmp_path / "cleared.json", what="metadata")
        assert "statistics" not in block and "statisticsBindings" not in block
        assert "__dsstatistics_owner_" not in (tmp_path / "cleared.json").read_text()
        assert isinstance(ds.load(tmp_path / "cleared.json"), alt.LayerChart)

    def test_load_validation_is_transactional_for_registry_and_theme(self, tmp_path):
        from jsonschema import ValidationError

        import dysonsphere as ds
        from dysonsphere import _statistics

        data = pl.DataFrame({"g": ["A"] * 4 + ["B"] * 4, "v": [1.0, 2, 3, 4, 2, 3, 4, 5]})
        ds.theme(width=180)
        chart = alt.Chart(data).mark_point().encode(x="g:N", y="v:Q") + ds.stats.comparisons(
            data, "g", "v", [("A", "B")], categories=["A", "B"]
        )
        ds.save(chart, str(tmp_path / "valid"), format="json", background="light")
        before_registry = dict(_statistics._LOADED_REPORTS)
        ds.theme(width=999)

        malformed = json.loads((tmp_path / "valid.json").read_text())
        malformed["usermeta"]["dysonsphere"]["statisticsBindings"] = None
        malformed["usermeta"]["dysonsphere"]["statistics"] = None
        (tmp_path / "malformed.json").write_text(json.dumps(malformed))
        with pytest.raises(ValueError, match="require a statistics record list"):
            ds.load(tmp_path / "malformed.json")
        assert _statistics._LOADED_REPORTS == before_registry and alt.theme.options["width"] == 999

        invalid = json.loads((tmp_path / "valid.json").read_text())
        invalid["layer"][0]["mark"] = {"type": "not-a-mark"}
        (tmp_path / "invalid.json").write_text(json.dumps(invalid))
        with pytest.raises((ValidationError, ValueError)):
            ds.load(tmp_path / "invalid.json")
        assert _statistics._LOADED_REPORTS == before_registry and alt.theme.options["width"] == 999

    def test_owner_walkers_ignore_user_rows_and_preserve_named_data_options(self, tmp_path):
        import dysonsphere as ds

        lookalike = "__dsstatistics_owner_" + "a" * 32
        data = pl.DataFrame(
            {
                "name": [lookalike] * 8,
                "payload": [{"data": {"name": "user-value"}}] * 8,
                "g": ["A"] * 4 + ["B"] * 4,
                "v": [1.0, 2, 3, 4, 2, 3, 4, 5],
            }
        )
        chart = alt.Chart(data).mark_point().encode(x="g:N", y="v:Q") + ds.stats.comparisons(
            data, "g", "v", [("A", "B")], categories=["A", "B"]
        )
        ds.save(chart, str(tmp_path / "rows"), format="json", background="light")
        recovered = ds.metadata.read(tmp_path / "rows.json", what="data")
        assert recovered["name"].to_list() == [lookalike] * 8
        assert recovered["payload"].to_list() == [{"data": {"name": "user-value"}}] * 8

        spec = json.loads((tmp_path / "rows.json").read_text())
        spec["layer"][0]["data"]["format"] = {"type": "json"}
        (tmp_path / "format.json").write_text(json.dumps(spec))
        with pytest.raises(ValueError, match="preserved statistical context changed"):
            ds.load(tmp_path / "format.json")

    def test_metadata_disabled_strips_loaded_owners_permanently(self, tmp_path):
        import dysonsphere as ds

        data = pl.DataFrame({"g": ["A"] * 4 + ["B"] * 4, "v": [1.0, 2, 3, 4, 2, 3, 4, 5]})
        chart = alt.Chart(data).mark_point().encode(x="g:N", y="v:Q") + ds.stats.comparisons(
            data, "g", "v", [("A", "B")], categories=["A", "B"]
        )
        ds.save(chart, str(tmp_path / "source"), format="json", background="light")
        loaded = ds.load(tmp_path / "source.json")
        assert isinstance(loaded, alt.LayerChart)
        ds.save(loaded, str(tmp_path / "bare"), format="json", saveMetadata=False)
        text = (tmp_path / "bare.json").read_text()
        assert "usermeta" not in text and "__dsstatistics_owner_" not in text
        loaded_bare = ds.load(tmp_path / "bare.json")
        assert isinstance(loaded_bare, alt.LayerChart)
        ds.save(loaded_bare, str(tmp_path / "later"), format="json", background="light")
        assert ds.metadata.read(tmp_path / "later.json", what="statistics") == []

    def test_loaded_statistics_reproducible_across_separate_loads(self, tmp_path, monkeypatch):
        import dysonsphere as ds

        monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
        data = pl.DataFrame({"g": ["A"] * 4 + ["B"] * 4, "v": [1.0, 2, 3, 4, 2, 3, 4, 5]})
        chart = alt.Chart(data).mark_point().encode(x="g:N", y="v:Q") + ds.stats.comparisons(
            data, "g", "v", [("A", "B")], categories=["A", "B"]
        )
        ds.save(chart, str(tmp_path / "source"), format="json", background="light")

        def resave(stem):
            loaded = ds.load(tmp_path / "source.json")
            assert isinstance(loaded, alt.LayerChart)
            ds.save(loaded, str(tmp_path / stem), format=["json", "svg", "png"], background="light", ppi=144)

        resave("first")
        resave("second")
        for suffix in ("json", "svg", "png"):
            assert (tmp_path / f"first.{suffix}").read_bytes() == (tmp_path / f"second.{suffix}").read_bytes()

    def test_spec_checksum_binds_different_records_to_their_components(self, tmp_path):
        import dysonsphere as ds

        groups = pl.DataFrame({"g": ["A"] * 5 + ["B"] * 5, "v": [1.0, 2, 3, 4, 5, 3, 4, 5, 6, 7]})
        xy = pl.DataFrame({"x": [1.0, 2, 3, 4, 5], "y": [1.1, 2.2, 2.8, 4.1, 5.2]})
        left = alt.Chart(groups).mark_point().encode(x="g:N", y="v:Q") + ds.stats.comparisons(
            groups, "g", "v", [("A", "B")], categories=["A", "B"]
        )
        right = alt.Chart(xy).mark_point().encode(x="x:Q", y="y:Q") + ds.stats.correlation(xy, "x", "y")
        ds.save(alt.hconcat(left, right), str(tmp_path / "owners"), format="json", background="light")
        path = tmp_path / "owners.json"
        original = json.loads(path.read_text())
        assert ds.metadata.verify(path).specValid is True

        names: list[tuple[dict[str, object], str]] = []

        def collect(value):
            if isinstance(value, dict):
                name = value.get("name")
                if isinstance(name, str) and name.startswith("__dsstatistics_owner_"):
                    names.append((value, name))
                for child in value.values():
                    collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)

        collect(original)
        assert len(names) == 2
        names[0][0]["name"], names[1][0]["name"] = names[1][1], names[0][1]
        path.write_text(json.dumps(original))
        assert ds.metadata.verify(path).specValid is False

    def test_read_no_metadata_raises(self, tmp_path):
        import dysonsphere as ds

        chart = alt.Chart(pl.DataFrame({"x": [1, 2], "y": [1.0, 2.0]})).mark_point().encode(x="x:Q", y="y:Q")
        ds.save(chart, str(tmp_path / "bare"), saveMetadata=False, background=["light"])
        with pytest.raises(ValueError, match="no dysonsphere metadata"):
            ds.metadata.read(str(tmp_path / "bare.json"))

    def test_read_data_rebuilds_full_dataframe(self, tmp_path):
        import dysonsphere as ds

        # include a column the chart never plots — it must still round-trip
        orig = pl.DataFrame({"g": ["A", "A", "B", "B"], "v": [1.0, 2.0, 3.0, 4.0], "extra": [10, 20, 30, 40]})
        chart = alt.Chart(orig).mark_boxplot().encode(x="g:N", y="v:Q")
        ds.save(chart, str(tmp_path / "d"), format="json", background=["light"])
        got = ds.metadata.read(str(tmp_path / "d.json"), what="data")
        assert isinstance(got, pl.DataFrame)
        assert set(got.columns) == {"g", "v", "extra"}  # whole frame, not just plotted cols
        assert got.sort(["g", "v"]).equals(orig.sort(["g", "v"]))

    def test_read_data_json_only(self, saved):
        import dysonsphere as ds

        with pytest.raises(ValueError, match="needs the Vega-Lite JSON"):
            ds.metadata.read(str(saved / "t.svg"), what="data")

    def _data_json(self, tmp_path):
        import dysonsphere as ds

        orig = pl.DataFrame({"g": ["A", "A", "B", "B"], "v": [1.0, 2.0, 3.0, 4.0]})
        ds.save(alt.Chart(orig).mark_point().encode(x="g:N", y="v:Q"), str(tmp_path / "d"), format="json")
        return str(tmp_path / "d.json")

    def test_read_data_output_pandas(self, tmp_path):
        import pandas as pd

        import dysonsphere as ds

        got = ds.metadata.read(self._data_json(tmp_path), what="data", output="pandas")
        assert isinstance(got, pd.DataFrame) and list(got.columns) == ["g", "v"] and len(got) == 4

    def test_read_data_output_duckdb(self, tmp_path):
        import duckdb

        import dysonsphere as ds

        got = ds.metadata.read(self._data_json(tmp_path), what="data", output="duckdb")
        assert isinstance(got, duckdb.DuckDBPyRelation) and len(got.fetchall()) == 4

    def test_read_data_output_records(self, tmp_path):
        import dysonsphere as ds

        got = ds.metadata.read(self._data_json(tmp_path), what="data", output="records")
        assert isinstance(got, list) and got[0] == {"g": "A", "v": 1.0}  # raw list[dict], no deps

    def test_read_data_invalid_output(self, tmp_path):
        import dysonsphere as ds

        with pytest.raises(ValueError, match="output must be one of"):
            ds.metadata.read(self._data_json(tmp_path), what="data", output="dask")

    def test_read_data_filters_internal_sidecars(self, tmp_path):
        # Every dysonsphere composite chart embeds internal sidecar datasets; read(what="data")
        # must filter them (via the sentinel) and return exactly ONE user frame per chart.  This
        # is the safety net: a newly-untagged internal data source makes one of these fail.
        import numpy as np

        import dysonsphere as ds

        rng = np.random.default_rng(0)
        df = pl.DataFrame({"g": ["A"] * 15 + ["B"] * 15 + ["C"] * 15, "v": rng.normal(0, 1, 45)})
        dfx = pl.DataFrame({"x": rng.uniform(0, 10, 30), "y": rng.normal(0, 1, 30)})
        dlog = pl.DataFrame({"x": [1.0, 10, 100, 1000] * 3, "y": [1.0, 10, 100, 1000] * 3})
        cats = ["A", "B", "C"]
        box = alt.Chart(df).mark_boxplot().encode(x="g:N", y="v:Q")
        pts = alt.Chart(dfx).mark_point().encode(x="x:Q", y="y:Q")
        logc = alt.Chart(dlog).mark_point().encode(x="x:Q", y=alt.Y("y:Q", scale=alt.Scale(type="log")))
        charts = {
            "mark_strip": (ds.mark_strip(df, "g", "v", cats), {"g", "v"}),
            "mark_violin": (ds.mark_violin(df, "g", "v", cats), {"g", "v"}),
            "mark_table": (ds.mark_table(df, cellPalette={"v": "greens"}), {"g", "v"}),
            "add_comparisons": (box + ds.stats.comparisons(df, "g", "v", [("A", "B")], categories=cats), {"g", "v"}),
            "add_comparisons_reference": (
                box + ds.stats.comparisons(df, "g", "v", reference="A", categories=cats),
                {"g", "v"},
            ),
            "add_correlation": (pts + ds.stats.correlation(dfx, "x", "y"), {"x", "y"}),
            "rule": (box + ds.rule(y=1.5, label="thr"), {"g", "v"}),
            "text": (box + ds.text("hi", position="topLeft"), {"g", "v"}),
            "shade": (box + ds.shade(categories=cats), {"g", "v"}),
            "add_multilabel": (ds.add_multilabel(box, categories=cats), {"g", "v"}),
            "add_log_ticks": (ds.add_log_ticks(logc, dlog, "y"), {"x", "y"}),
        }
        for name, (chart, cols) in charts.items():
            ds.save(chart, str(tmp_path / name), format="json", background=["light"])
            got = ds.metadata.read(str(tmp_path / f"{name}.json"), what="data")
            assert isinstance(got, pl.DataFrame), f"{name}: expected one user frame, got {type(got).__name__}"
            assert cols.issubset(set(got.columns)), f"{name}: missing user cols, got {got.columns}"

    @pytest.fixture
    def multi_frame_json(self, tmp_path):
        import dysonsphere as ds

        d1 = pl.DataFrame({"x": [1, 2, 3, 4], "y": [1.0, 2, 3, 4]})
        d2 = pl.DataFrame({"x": [1, 4], "yhat": [1.1, 3.9]})
        chart = alt.Chart(d1).mark_point().encode(x="x:Q", y="y:Q") + alt.Chart(d2).mark_line().encode(
            x="x:Q", y="yhat:Q"
        )
        ds.save(chart, str(tmp_path / "m"), format="json", background=["light"])
        return str(tmp_path / "m.json")

    def test_read_data_multi_frame_raises(self, multi_frame_json):
        import dysonsphere as ds

        with pytest.raises(ValueError, match="user datasets"):  # refuses to guess
            ds.metadata.read(multi_frame_json, what="data")

    def test_read_data_all_returns_dict(self, multi_frame_json):
        import dysonsphere as ds

        got = ds.metadata.read(multi_frame_json, what="data", dataset="all")
        assert isinstance(got, dict) and len(got) == 2
        colsets = sorted(tuple(sorted(f.columns)) for f in got.values())
        assert colsets == [("x", "y"), ("x", "yhat")]  # both user frames, no internal

    def test_read_data_all_single_frame_still_dict(self, tmp_path):
        # dataset="all" is predictable: even a 1-frame file returns a dict, not a bare frame
        import dysonsphere as ds

        got = ds.metadata.read(self._data_json(tmp_path), what="data", dataset="all")
        assert isinstance(got, dict) and len(got) == 1

    def test_read_data_by_name(self, multi_frame_json):
        import dysonsphere as ds

        names = list(ds.metadata.read(multi_frame_json, what="data", dataset="all"))
        one = ds.metadata.read(multi_frame_json, what="data", dataset=names[0])
        assert isinstance(one, pl.DataFrame)

    @pytest.mark.parametrize("as_path", [False, True])
    def test_read_report_save_writes_txt(self, saved, tmp_path, as_path):
        import dysonsphere as ds

        outdir = tmp_path / "reports"
        target = outdir if as_path else str(outdir)
        ds.metadata.read(saved / "t.png", saveReport=target)
        txts = list(outdir.glob("dysonsphere_report_*.txt"))
        assert len(txts) == 1 and txts[0].read_text(encoding="utf-8").startswith("Statistics")

    def test_read_report_true_uses_cwd_and_false_writes_nothing(self, saved, tmp_path, monkeypatch):
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.chdir(cwd)
        import dysonsphere as ds

        ds.metadata.read(saved / "t.png", saveReport=True)
        assert len(list(cwd.glob("dysonsphere_report_*.txt"))) == 1

        clean = tmp_path / "no_report"
        clean.mkdir()
        monkeypatch.chdir(clean)
        ds.metadata.read(saved / "t.png", saveReport=False)
        assert list(clean.iterdir()) == []

    def test_load_rejects_removed_theme_key(self, tmp_path):
        # v2.x files bake the old `transparentBackground` key into their theme block. The v3.0
        # alias removal means applyTheme replays it into theme(), which now raises a clear
        # TypeError - a documented break; raw=True (or re-export) is the workaround.
        import dysonsphere as ds

        df = pl.DataFrame({"x": [1.0, 2.0], "y": [1.0, 2.0]})
        chart = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q")
        ds.save(chart, str(tmp_path / "old"), format="json", background="light")
        spec = json.loads((tmp_path / "old.json").read_text(encoding="utf-8"))
        theme_block = spec["usermeta"]["dysonsphere"]["theme"]
        theme_block["transparentBackground"] = theme_block.pop("transparent")  # simulate an old file
        (tmp_path / "old.json").write_text(json.dumps(spec), encoding="utf-8")
        with pytest.raises(TypeError, match="transparentBackground"):
            ds.load(str(tmp_path / "old.json"))
        # raw=True touches no globals and applies no theme, so the old file still loads.
        assert ds.load(str(tmp_path / "old.json"), raw=True) is not None


# ── PNG metadata helpers ──────────────────────────────────────────────────────


def _make_minimal_png() -> bytes:
    """1×1 white RGB PNG for use in metadata tests."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff"))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _read_png_chunks(png: bytes) -> list[tuple[bytes, bytes]]:
    """Return (type, data) for every chunk in the PNG."""
    chunks = []
    pos = 8  # skip signature
    while pos < len(png):
        length = struct.unpack(">I", png[pos : pos + 4])[0]
        tag = png[pos + 4 : pos + 8]
        data = png[pos + 8 : pos + 8 + length]
        chunks.append((tag, data))
        pos += 4 + 4 + length + 4
    return chunks


class TestInjectPngMetadata:
    def test_itxt_chunk_present(self):
        png = _inject_png_metadata(_make_minimal_png(), "hello")
        types = [t for t, _ in _read_png_chunks(png)]
        assert b"iTXt" in types

    def test_itxt_placed_after_ihdr(self):
        png = _inject_png_metadata(_make_minimal_png(), "hello")
        types = [t for t, _ in _read_png_chunks(png)]
        assert types[0] == b"IHDR"
        assert types[1] == b"iTXt"

    def test_description_keyword_and_text(self):
        desc = "Generated with test.py by user on 20260630."
        png = _inject_png_metadata(_make_minimal_png(), desc)
        for tag, data in _read_png_chunks(png):
            if tag == b"iTXt":
                null = data.index(b"\x00")
                keyword = data[:null].decode("utf-8")
                # skip keyword\0 + compression_flag + compression_method + lang\0 + translated\0
                text = data[null + 5 :].decode("utf-8")
                assert keyword == "Description"
                assert text == desc
                return
        pytest.fail("no iTXt chunk found")

    def test_unicode_description_roundtrips(self):
        desc = "café — by dkung 2026"
        png = _inject_png_metadata(_make_minimal_png(), desc)
        for tag, data in _read_png_chunks(png):
            if tag == b"iTXt":
                null = data.index(b"\x00")
                text = data[null + 5 :].decode("utf-8")
                assert text == desc
                return
        pytest.fail("no iTXt chunk found")

    def test_all_chunk_crcs_valid(self):
        png = _inject_png_metadata(_make_minimal_png(), "crc check")
        pos = 8
        while pos < len(png):
            length = struct.unpack(">I", png[pos : pos + 4])[0]
            tag = png[pos + 4 : pos + 8]
            data = png[pos + 8 : pos + 8 + length]
            stored = struct.unpack(">I", png[pos + 8 + length : pos + 12 + length])[0]
            assert (zlib.crc32(tag + data) & 0xFFFFFFFF) == stored, f"bad CRC in {tag}"
            pos += 4 + 4 + length + 4

    def test_existing_chunks_unchanged(self):
        original = _make_minimal_png()
        result = _inject_png_metadata(original, "test")
        orig_chunks = _read_png_chunks(original)
        result_chunks = _read_png_chunks(result)
        # result has one extra chunk (iTXt); all original chunks must be present and unchanged
        non_itxt = [(t, d) for t, d in result_chunks if t != b"iTXt"]
        assert non_itxt == orig_chunks


class TestStatsQueueRobustness:
    """The marker mechanism: save() embeds only the records whose annotations are in the
    chart being saved, so stale records can't contaminate it; plus the provenance ids."""

    def _stats_layer(self, seed=0):
        import numpy as np

        import dysonsphere as ds

        rng = np.random.default_rng(seed)
        df = pl.DataFrame({"g": ["A"] * 20 + ["B"] * 20, "v": np.r_[rng.normal(0, 1, 20), rng.normal(2, 1, 20)]})
        chart = alt.Chart(df).mark_boxplot().encode(x="g:N", y="v:Q") + ds.stats.comparisons(
            df, "g", "v", [("A", "B")], categories=["A", "B"]
        )
        return chart

    def _um(self, tmp_path, name="out"):
        return json.loads((tmp_path / f"{name}.json").read_text())["usermeta"]["dysonsphere"]

    def test_unsaved_stats_do_not_contaminate(self, simple_chart, tmp_path):
        import dysonsphere as ds

        _ = self._stats_layer()  # build a stats chart but NEVER save it → record only queued
        ds.save(simple_chart, str(tmp_path / "plain"), format="json", background=["light"])
        assert "statistics" not in self._um(tmp_path, "plain")  # the stale record must not leak

    def test_saved_chart_gets_its_own_stats(self, tmp_path):
        import dysonsphere as ds

        ds.save(self._stats_layer(), str(tmp_path / "s"), format="json", background=["light"])
        assert "statistics" in self._um(tmp_path, "s")

    def test_marker_stripped_from_output(self, tmp_path):
        import dysonsphere as ds

        ds.save(self._stats_layer(), str(tmp_path / "s"), format=["svg", "json"], background=["light"])
        # The layer-name marker (a "name" field) must be stripped; check precisely, since the
        # internal-data sentinel COLUMN "__dysonsphere__" legitimately remains and shares the prefix.
        assert '"name": "__dysonsphere_' not in (tmp_path / "s.json").read_text()
        assert "__dysonsphere_" not in (tmp_path / "s.svg").read_text()  # neither marker nor sentinel renders

    def test_provenance_has_checksum_and_export(self, simple_chart, tmp_path):
        import dysonsphere as ds

        ds.save(simple_chart, str(tmp_path / "out"), format="json", background=["light"])
        prov = self._um(tmp_path)["provenance"]
        assert prov["vegaliteChecksum"].startswith("sha256:") and len(prov["vegaliteChecksum"]) == len("sha256:") + 64
        assert prov["exportIdentifier"].count("-") == 4  # uuid4 shape

    def test_shared_export_but_distinct_checksum(self, simple_chart, tmp_path):
        import dysonsphere as ds

        ds.save(simple_chart, str(tmp_path / "b"), format="json", background=["light", "dark"])
        pl_ = self._um(tmp_path, "b_light")["provenance"]
        pd_ = self._um(tmp_path, "b_dark")["provenance"]
        assert pl_["exportIdentifier"] == pd_["exportIdentifier"]  # one export event
        assert pl_["vegaliteChecksum"] != pd_["vegaliteChecksum"]  # different specs

    def test_checksum_revalidates(self, simple_chart, tmp_path):
        import hashlib

        import dysonsphere as ds

        ds.save(simple_chart, str(tmp_path / "out"), format="json", background=["light"])
        spec = json.loads((tmp_path / "out.json").read_text())
        stored = spec["usermeta"]["dysonsphere"]["provenance"]["vegaliteChecksum"]
        clean = {k: v for k, v in spec.items() if k != "usermeta"}
        canon = json.dumps(clean, sort_keys=True, separators=(",", ":"))
        assert stored == "sha256:" + hashlib.sha256(canon.encode()).hexdigest()

    def test_provenance_has_data_checksum(self, simple_chart, tmp_path):
        import dysonsphere as ds

        ds.save(simple_chart, str(tmp_path / "out"), format="json", background=["light"])
        sums = self._um(tmp_path)["provenance"]["dataChecksum"]
        assert isinstance(sums, list) and sums  # non-empty list
        assert all(s.startswith(_ROW_HASH_PREFIX) and len(s) == len(_ROW_HASH_PREFIX) + 64 for s in sums)

    def test_data_checksum_matches_across_specs(self, tmp_path):
        # The core value prop: same data, DIFFERENT specs → identical dataChecksum.
        import dysonsphere as ds

        df = pl.DataFrame({"x": ["A", "B", "C"], "y": [1.0, 2.0, 3.0]})
        points = alt.Chart(df).mark_point().encode(x="x:N", y="y:Q")
        bars = alt.Chart(df).mark_bar().encode(x="y:Q", y="x:N")  # different mark AND encoding
        ds.save(points, str(tmp_path / "p"), format="json", background=["light"])
        ds.save(bars, str(tmp_path / "b"), format="json", background=["light"])
        assert (
            self._um(tmp_path, "p")["provenance"]["vegaliteChecksum"]
            != (self._um(tmp_path, "b")["provenance"]["vegaliteChecksum"])
        )  # specs differ
        assert (
            self._um(tmp_path, "p")["provenance"]["dataChecksum"]
            == self._um(tmp_path, "b")["provenance"]["dataChecksum"]
        )  # data is identical

    def test_data_checksum_differs_for_different_data(self, tmp_path):
        import dysonsphere as ds

        a = alt.Chart(pl.DataFrame({"x": ["A", "B"], "y": [1.0, 2.0]})).mark_point().encode(x="x:N", y="y:Q")
        b = alt.Chart(pl.DataFrame({"x": ["A", "B"], "y": [1.0, 9.0]})).mark_point().encode(x="x:N", y="y:Q")
        ds.save(a, str(tmp_path / "a"), format="json", background=["light"])
        ds.save(b, str(tmp_path / "b"), format="json", background=["light"])
        assert (
            self._um(tmp_path, "a")["provenance"]["dataChecksum"]
            != self._um(tmp_path, "b")["provenance"]["dataChecksum"]
        )

    def test_data_checksum_order_independent(self, tmp_path):
        import dysonsphere as ds

        rows = [{"x": "A", "y": 1.0}, {"x": "B", "y": 2.0}, {"x": "C", "y": 3.0}]
        a = alt.Chart(pl.DataFrame(rows)).mark_point().encode(x="x:N", y="y:Q")
        b = alt.Chart(pl.DataFrame(rows[::-1])).mark_point().encode(x="x:N", y="y:Q")  # rows shuffled
        ds.save(a, str(tmp_path / "a"), format="json", background=["light"])
        ds.save(b, str(tmp_path / "b"), format="json", background=["light"])
        assert (
            self._um(tmp_path, "a")["provenance"]["dataChecksum"]
            == self._um(tmp_path, "b")["provenance"]["dataChecksum"]
        )

    def test_data_checksum_shared_across_variants(self, simple_chart, tmp_path):
        # Data is identical regardless of darkmode, so dataChecksum matches (unlike vegaliteChecksum).
        import dysonsphere as ds

        ds.save(simple_chart, str(tmp_path / "b"), format="json", background=["light", "dark"])
        pl_ = self._um(tmp_path, "b_light")["provenance"]
        pd_ = self._um(tmp_path, "b_dark")["provenance"]
        assert pl_["vegaliteChecksum"] != pd_["vegaliteChecksum"]  # specs differ by theme
        assert pl_["dataChecksum"] == pd_["dataChecksum"]  # data is the same

    def test_data_checksum_excludes_internal_sidecars(self, tmp_path):
        # Adding a dysonsphere annotation layer (which embeds internal sidecar data) must NOT
        # change the dataChecksum — only the user's frame is hashed.
        import dysonsphere as ds

        df = pl.DataFrame({"g": ["A", "A", "B", "B"], "v": [1.0, 1.5, 3.0, 3.5]})
        plain = alt.Chart(df).mark_boxplot().encode(x="g:N", y="v:Q")
        annotated = plain + ds.stats.comparisons(df, "g", "v", [("A", "B")], categories=["A", "B"])
        ds.save(plain, str(tmp_path / "plain"), format="json", background=["light"])
        ds.save(annotated, str(tmp_path / "ann"), format="json", background=["light"])
        assert (
            self._um(tmp_path, "plain")["provenance"]["dataChecksum"]
            == self._um(tmp_path, "ann")["provenance"]["dataChecksum"]
        )

    def test_data_checksum_multiframe(self, tmp_path):
        import dysonsphere as ds

        left = alt.Chart(pl.DataFrame({"x": ["A", "B"], "y": [1.0, 2.0]})).mark_point().encode(x="x:N", y="y:Q")
        right = alt.Chart(pl.DataFrame({"x": ["C", "D"], "y": [3.0, 4.0]})).mark_bar().encode(x="x:N", y="y:Q")
        ds.save(left | right, str(tmp_path / "h"), format="json", background=["light"])
        sums = self._um(tmp_path, "h")["provenance"]["dataChecksum"]
        assert len(sums) == 2 and sums == sorted(sums)  # one per frame, sorted

    def test_data_checksum_revalidates(self, simple_chart, tmp_path):
        import dysonsphere as ds
        from dysonsphere.metadata import _data_checksum

        ds.save(simple_chart, str(tmp_path / "out"), format="json", background=["light"])
        spec = json.loads((tmp_path / "out.json").read_text())
        stored = spec["usermeta"]["dysonsphere"]["provenance"]["dataChecksum"]
        assert stored == _data_checksum(spec)  # re-derive from the written spec

    def test_record_data_checksum_distinguishes_sources(self, tmp_path):
        # Two correlations from DIFFERENT dataframes → two records with distinct dataChecksums,
        # and the one built on the inlined base frame matches provenance.dataChecksum.
        import numpy as np

        import dysonsphere as ds

        rng = np.random.default_rng(0)
        x = rng.uniform(0, 10, 30)
        dfA = pl.DataFrame({"x": x, "y": 0.9 * x + rng.normal(0, 1, 30)})
        dfB = pl.DataFrame({"x": x, "y": -0.5 * x + rng.normal(0, 1, 30)})
        ds.stats.clear_stats()
        chart = (
            alt.Chart(dfA).mark_point().encode(x="x:Q", y="y:Q")
            + ds.stats.correlation(dfA, "x", "y")
            + ds.stats.correlation(dfB, "x", "y")
        )
        ds.save(chart, str(tmp_path / "c"), format="json", background=["light"])
        block = self._um(tmp_path, "c")
        sums = [r["dataChecksum"] for r in block["statistics"]]
        assert len(sums) == 2 and sums[0] != sums[1]  # distinct sources, both kept
        assert block["provenance"]["dataChecksum"][0] in sums  # base frame record == provenance

    def test_comparisons_record_carries_data_checksum(self, tmp_path):
        import dysonsphere as ds

        df = pl.DataFrame({"g": ["A", "A", "B", "B"], "v": [1.0, 1.5, 3.0, 3.5]})
        ds.stats.clear_stats()
        chart = alt.Chart(df).mark_boxplot().encode(x="g:N", y="v:Q") + ds.stats.comparisons(
            df, "g", "v", [("A", "B")], categories=["A", "B"]
        )
        ds.save(chart, str(tmp_path / "s"), format="json", background=["light"])
        rec = self._um(tmp_path, "s")["statistics"][0]
        assert rec["dataChecksum"] and rec["dataChecksum"].startswith(_ROW_HASH_PREFIX)

    def test_clear_stats_empties_queue(self):
        import dysonsphere as ds
        from dysonsphere._statistics import _REPORTS

        self._stats_layer()
        assert len(_REPORTS) >= 1
        ds.stats.clear_stats()
        assert len(_REPORTS) == 0


class TestSourceDateEpoch:
    """`SOURCE_DATE_EPOCH` pins the timestamp and the run id, making exports byte-reproducible."""

    def _prov(self, tmp_path, name="out"):
        spec = json.loads((tmp_path / f"{name}.json").read_text())
        return spec["usermeta"]["dysonsphere"]["provenance"]

    def test_unset_and_blank_read_as_none(self, monkeypatch):
        monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
        assert _source_date_epoch() is None
        monkeypatch.setenv("SOURCE_DATE_EPOCH", "   ")
        assert _source_date_epoch() is None

    def test_parses_and_pins_timestamp(self, monkeypatch):
        monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
        assert _source_date_epoch() == 1700000000
        assert _resolve_timestamp() == "2023-11-14T22:13:20Z"

    def test_malformed_raises(self, monkeypatch):
        monkeypatch.setenv("SOURCE_DATE_EPOCH", "not-a-number")
        with pytest.raises(ValueError, match="integer count of UTC seconds"):
            _source_date_epoch()

    def test_out_of_range_raises_clearly(self, monkeypatch):
        monkeypatch.setenv("SOURCE_DATE_EPOCH", str(10**18))
        with pytest.raises(ValueError, match="out of range"):
            _resolve_timestamp()

    def test_repeated_save_is_byte_identical(self, simple_chart, monkeypatch, tmp_path):
        import dysonsphere as ds

        monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
        ds.save(simple_chart, str(tmp_path / "a"), format=["json", "svg"], background=["light"])
        ds.save(simple_chart, str(tmp_path / "b"), format=["json", "svg"], background=["light"])
        for ext in ("json", "svg"):
            assert (tmp_path / f"a.{ext}").read_bytes() == (tmp_path / f"b.{ext}").read_bytes()

    def test_unpinned_saves_differ(self, simple_chart, monkeypatch, tmp_path):
        import dysonsphere as ds

        monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
        ds.save(simple_chart, str(tmp_path / "a"), format="json", background=["light"])
        ds.save(simple_chart, str(tmp_path / "b"), format="json", background=["light"])
        assert self._prov(tmp_path, "a")["exportIdentifier"] != self._prov(tmp_path, "b")["exportIdentifier"]

    def test_variants_still_share_one_id(self, simple_chart, monkeypatch, tmp_path):
        import dysonsphere as ds

        monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
        ds.save(simple_chart, str(tmp_path / "v"), format="json", background=["light", "dark"])
        light, dark = self._prov(tmp_path, "v_light"), self._prov(tmp_path, "v_dark")
        assert light["exportIdentifier"] == dark["exportIdentifier"]  # still one export event
        assert light["vegaliteChecksum"] != dark["vegaliteChecksum"]

    def test_distinct_charts_do_not_collide(self, simple_chart, monkeypatch, tmp_path):
        """Two figures pinned to one epoch must keep distinct ids - the id is content-derived."""
        import dysonsphere as ds

        monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
        df = pl.DataFrame({"x": ["A", "B", "C"], "y": [1.0, 2.0, 3.0]})
        ds.save(simple_chart, str(tmp_path / "p"), format="json", background=["light"])
        ds.save(alt.Chart(df).mark_bar().encode(x="x:N", y="y:Q"), str(tmp_path / "b"), format="json")
        assert self._prov(tmp_path, "p")["exportIdentifier"] != self._prov(tmp_path, "b")["exportIdentifier"]

    def test_id_is_a_uuid_shape(self, simple_chart, monkeypatch, tmp_path):
        import dysonsphere as ds

        monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
        ds.save(simple_chart, str(tmp_path / "u"), format="json", background=["light"])
        uuid.UUID(self._prov(tmp_path, "u")["exportIdentifier"])  # parses, so the field shape is unchanged


class TestNonFiniteJson:
    """`NaN`/`Infinity` are Python `json` extensions, not JSON - the written spec must not carry them."""

    @staticmethod
    def _chart_with_nan():
        df = pl.DataFrame({"g": ["a", "b", "c"], "v": [1.0, float("nan"), 3.0]})
        return df, alt.Chart(df).mark_point().encode(x="g:N", y="v:Q")

    @staticmethod
    def _strict_load(txt):
        """Parse the way a browser's JSON.parse or serde_json would - no bare constants."""

        def reject(token):
            raise ValueError(f"bare {token}")

        return json.loads(txt, parse_constant=reject)

    def test_written_json_is_strict_valid(self, tmp_path):
        import dysonsphere as ds

        _, chart = self._chart_with_nan()
        ds.save(chart, str(tmp_path / "n"), format="json", background=["light"])
        txt = (tmp_path / "n.json").read_text()
        assert "NaN" not in txt
        rows = next(iter(self._strict_load(txt)["datasets"].values()))
        assert [r["v"] for r in rows] == [1.0, None, 3.0]  # null, and the finite floats untouched

    def test_finite_floats_survive_the_round_trip(self, tmp_path):
        """A Float64 column must not come back as Int64 - only non-finite values are rewritten."""
        import dysonsphere as ds

        df, chart = self._chart_with_nan()
        ds.save(chart, str(tmp_path / "r"), format="json", background=["light"])
        back = ds.metadata.read(str(tmp_path / "r.json"), what="data")
        assert back.dtypes == df.dtypes

    def test_checksum_still_revalidates(self, tmp_path):
        """The spec is made JSON-safe BEFORE hashing, so the stored checksum matches the file."""
        import dysonsphere as ds

        _, chart = self._chart_with_nan()
        ds.save(chart, str(tmp_path / "c"), format="json", background=["light"])
        spec = json.loads((tmp_path / "c.json").read_text())
        from dysonsphere.metadata import _spec_checksum

        recomputed = _spec_checksum(spec)
        assert spec["usermeta"]["dysonsphere"]["provenance"]["vegaliteChecksum"] == recomputed

    def test_renders_still_succeed(self, tmp_path):
        import dysonsphere as ds

        _, chart = self._chart_with_nan()
        ds.save(chart, str(tmp_path / "v"), format=["svg", "png"], background=["light"])
        assert (tmp_path / "v.svg").stat().st_size > 0 and (tmp_path / "v.png").stat().st_size > 0


class TestVerify:
    """`verify()` re-checks a saved figure against its own embedded checksums."""

    @pytest.fixture
    def saved(self, simple_chart, tmp_path):
        import dysonsphere as ds

        ds.save(simple_chart, str(tmp_path / "fig"), format=["json", "svg", "png"], background=["light"])
        return tmp_path / "fig"

    @pytest.fixture
    def source_df(self):
        return pl.DataFrame({"x": ["A", "B", "C"], "y": [1.0, 2.0, 3.0]})

    def test_clean_json_passes(self, saved):
        import dysonsphere as ds

        r = ds.metadata.verify(f"{saved}.json")
        assert r.specValid is True
        assert r.dataMatches is None  # no df supplied - not a failure
        assert r.ok

    def test_matching_dataframe(self, saved, source_df):
        import dysonsphere as ds

        assert ds.metadata.verify(f"{saved}.json", data=source_df).dataMatches is True

    def test_wrong_dataframe_fails(self, saved):
        import dysonsphere as ds

        other = pl.DataFrame({"x": ["A", "B", "C"], "y": [9.0, 9.0, 9.0]})
        r = ds.metadata.verify(f"{saved}.json", data=other)
        assert r.dataMatches is False and not r.ok

    def test_row_order_does_not_matter(self, saved, source_df):
        import dysonsphere as ds

        shuffled = source_df.sample(fraction=1.0, shuffle=True, seed=7)
        assert ds.metadata.verify(f"{saved}.json", data=shuffled).dataMatches is True

    def test_pandas_accepted(self, saved, source_df):
        import dysonsphere as ds

        assert ds.metadata.verify(f"{saved}.json", data=source_df.to_pandas()).dataMatches is True

    @pytest.mark.parametrize("ext", ["svg", "png"])
    def test_data_verifiable_without_a_spec(self, saved, source_df, ext):
        """SVG/PNG carry the checksums but not the spec - unknown, not failed."""
        import dysonsphere as ds

        r = ds.metadata.verify(f"{saved}.{ext}", data=source_df)
        assert r.specValid is None  # could not run
        assert r.dataMatches is True and r.ok

    def test_detects_a_tampered_spec(self, saved, tmp_path):
        import dysonsphere as ds

        spec = json.loads((tmp_path / "fig.json").read_text())
        spec["mark"] = {"type": "bar"}  # someone edited the chart after export
        (tmp_path / "edited.json").write_text(json.dumps(spec, indent=2))
        r = ds.metadata.verify(str(tmp_path / "edited.json"))
        assert r.specValid is False and not r.ok

    def test_multiframe_order_independent(self, tmp_path):
        import dysonsphere as ds

        d1 = pl.DataFrame({"g": ["a", "b"], "v": [1.0, 2.0]})
        d2 = pl.DataFrame({"k": ["x", "y"], "n": [7, 8]})
        chart = alt.hconcat(
            alt.Chart(d1).mark_point().encode(x="g:N", y="v:Q"),
            alt.Chart(d2).mark_bar().encode(x="k:N", y="n:Q"),
        )
        ds.save(chart, str(tmp_path / "m"), format="json", background=["light"])
        assert ds.metadata.verify(str(tmp_path / "m.json"), data=[d1, d2]).dataMatches is True
        assert ds.metadata.verify(str(tmp_path / "m.json"), data=[d2, d1]).dataMatches is True
        assert ds.metadata.verify(str(tmp_path / "m.json"), data=[d1]).dataMatches is False  # incomplete

    def test_surfaces_identity_fields(self, saved):
        import dysonsphere as ds

        r = ds.metadata.verify(f"{saved}.json")
        assert r.exportIdentifier is not None and r.timestamp is not None
        uuid.UUID(r.exportIdentifier)
        assert r.timestamp.endswith("Z")

    def test_rejects_a_file_without_metadata(self, tmp_path):
        import dysonsphere as ds

        (tmp_path / "plain.json").write_text('{"mark":"point"}')
        with pytest.raises(ValueError, match="no dysonsphere metadata"):
            ds.metadata.verify(str(tmp_path / "plain.json"))


class TestVerifyCompare:
    """A list of figures is compared instead of checked; same number means same figure."""

    @pytest.fixture
    def frames(self):
        return (
            pl.DataFrame({"x": ["A", "B", "C"], "y": [1.0, 2.0, 3.0]}),
            pl.DataFrame({"x": ["A", "B", "C"], "y": [9.0, 8.0, 7.0]}),
        )

    def _bar(self, df):
        return alt.Chart(df).mark_bar().encode(x="x:N", y="y:Q")

    @pytest.fixture
    def saved(self, frames, tmp_path):
        import dysonsphere as ds

        a, b = frames
        ds.save(self._bar(a), str(tmp_path / "f1"), format=["json", "png"], background=["light"])
        ds.save(self._bar(a), str(tmp_path / "f2"), format="json", background=["light"])
        ds.save(self._bar(b), str(tmp_path / "f3"), format="json", background=["light"])
        return tmp_path

    def test_groups_figures_that_share_an_identity(self, saved):
        import dysonsphere as ds

        r = ds.metadata.verify([str(saved / "f1.json"), str(saved / "f2.json"), str(saved / "f3.json")])
        assert r.groups is not None and r.matches is not None
        by_dim = {k: v for k, v in r.groups.items() if v is not None}
        assert set(by_dim) == {"spec", "data", "save"}
        spec = list(by_dim["spec"].values())
        assert spec[0] == spec[1] != spec[2], "f1 and f2 are the same chart, f3 is not"
        assert list(by_dim["data"].values()) == spec
        assert len(set(by_dim["save"].values())) == 3, "three separate saves"
        assert r.matches == {"spec": False, "data": False, "save": False}

    def test_all_matching_reports_true(self, saved):
        # One save written to two formats agrees on everything.
        import dysonsphere as ds

        r = ds.metadata.verify([str(saved / "f1.json"), str(saved / "f1.png")])
        assert r.matches == {"spec": True, "data": True, "save": True}

    def test_a_chart_in_memory_has_no_save_identity(self, saved, frames):
        import dysonsphere as ds

        r = ds.metadata.verify([str(saved / "f1.json"), self._bar(frames[0])])
        assert r.groups is not None and r.matches is not None
        assert r.matches["spec"] is True
        assert r.matches["data"] is True
        assert r.matches["save"] is None, "a chart was never exported"
        assert r.groups["save"] is None

    def test_what_selects_the_questions(self, saved):
        import dysonsphere as ds

        r = ds.metadata.verify([str(saved / "f1.json"), str(saved / "f3.json")], what="data")
        assert r.matches is not None
        assert set(r.matches) == {"data"}
        assert r.matches["data"] is False
        assert r.ok is False

    def test_ok_ignores_unavailable_comparisons(self, saved, frames):
        import dysonsphere as ds

        r = ds.metadata.verify([str(saved / "f1.json"), self._bar(frames[0])], what="save")
        assert r.matches == {"save": None}
        assert r.ok is True

    def test_group_numbers_never_collide(self, saved):
        # Numbers are assigned after grouping on the full checksum, so two different figures
        # cannot share one however short the labels look.
        import dysonsphere as ds

        r = ds.metadata.verify([str(saved / "f1.json"), str(saved / "f2.json"), str(saved / "f3.json")])
        assert r.groups is not None and r.groups["spec"] is not None
        by_number: dict[int, set[str]] = {}
        for label, number in r.groups["spec"].items():
            by_number.setdefault(number, set()).add(label)
        assert by_number[r.groups["spec"][str(saved / "f3.json")]] == {str(saved / "f3.json")}

    def test_statistics_markers_do_not_make_identical_charts_differ(self, tmp_path):
        # stats.comparisons tags its layer with a marker whose name carries a counter that
        # increments per build. save() strips markers before hashing, so an in-memory chart has
        # to as well - otherwise two identical charts, and a chart against its own export, differ.
        import numpy as np

        import dysonsphere as ds

        rng = np.random.default_rng(0)
        cats = ["A", "B"]
        df = pl.DataFrame({"g": [c for c in cats for _ in range(8)], "v": rng.normal(0, 1, 16).tolist()})

        def built():
            return ds.mark_strip(df, "g", "v", cats) + ds.stats.comparisons(
                df, "g", "v", pairs=[("A", "B")], test="ttest_ind"
            )

        ds.save(built(), str(tmp_path / "s"), format="json", background=["light"])

        def spec_matches(items):
            matches = ds.metadata.verify(items, what="spec").matches
            assert matches is not None
            return matches["spec"]

        assert spec_matches([built(), built()]) is True
        assert spec_matches([str(tmp_path / "s.json"), built()]) is True
        # and a genuinely different chart is still reported as different
        assert spec_matches([built(), ds.mark_strip(df, "g", "v", cats)]) is False

    def test_duplicate_paths_stay_distinct(self, saved):
        # groups is keyed by label, so the same path twice would overwrite itself and the result
        # would no longer describe the list that was passed.
        import dysonsphere as ds

        one = str(saved / "f1.json")
        r = ds.metadata.verify([one, one, str(saved / "f3.json")], what="spec")
        assert r.groups is not None and r.groups["spec"] is not None
        assert len(r.groups["spec"]) == 3, "three items in, three entries out"

    def test_comparing_reads_recorded_values_not_the_file_contents(self, saved, frames):
        # Comparing a PNG with a JSON is only possible because it reads what each file recorded.
        # The cost is that an edited file still compares as the chart it claims to be - checking
        # one figure on its own is what catches that.
        import json

        import dysonsphere as ds

        original = saved / "f1.json"
        spec = json.loads(original.read_text())
        spec["mark"] = "point"
        edited = saved / "edited.json"
        edited.write_text(json.dumps(spec))

        assert ds.metadata.verify(str(edited), data=frames[0]).specValid is False, "the edit is detectable"
        r = ds.metadata.verify([str(original), str(edited)], what="spec")
        assert r.matches is not None
        assert r.matches["spec"] is True, "but comparing trusts the recorded identity"

    def test_rejects_a_dataframe_when_comparing(self, saved, frames):
        # data= checks one figure against its data; silently ignoring it while comparing a list
        # would answer a question the caller did not ask.
        import dysonsphere as ds

        with pytest.raises(ValueError, match="does not apply when comparing"):
            ds.metadata.verify([str(saved / "f1.json"), str(saved / "f2.json")], data=frames[0])

    def test_rejects_an_empty_what(self, saved):
        import dysonsphere as ds

        with pytest.raises(ValueError, match="must name at least one"):
            ds.metadata.verify([str(saved / "f1.json"), str(saved / "f2.json")], what=[])

    def test_rejects_an_item_that_is_neither_path_nor_chart(self, saved):
        import dysonsphere as ds

        with pytest.raises(TypeError, match="Item 1 is a int"):
            ds.metadata.verify([str(saved / "f1.json"), 42])

    def test_accepts_paths_charts_and_every_format(self, saved, frames):
        # Mixed input is the point: a JSON, a PNG, an SVG and a live chart in one call.
        import dysonsphere as ds

        r = ds.metadata.verify(
            [str(saved / "f1.json"), str(saved / "f1.png"), self._bar(frames[0])],
            what=["spec", "data"],
        )
        assert r.matches == {"spec": True, "data": True}

    def test_rejects_a_single_item_and_a_bad_question(self, saved):
        import dysonsphere as ds

        with pytest.raises(ValueError, match="at least two figures"):
            ds.metadata.verify([str(saved / "f1.json")])
        with pytest.raises(ValueError, match="unknown name"):
            ds.metadata.verify([str(saved / "f1.json"), str(saved / "f2.json")], what="colour")

    def test_checking_one_figure_still_works(self, saved, frames):
        import dysonsphere as ds

        r = ds.metadata.verify(str(saved / "f1.json"), data=frames[0])
        assert r.ok and r.specValid is True and r.dataMatches is True
        assert r.matches is None and r.groups is None

    def test_path_is_the_file_when_checking_and_none_when_comparing(self, saved):
        # `path` names the single file that was checked; a comparison has no single file, so it
        # is None rather than a joined string of every label.
        import dysonsphere as ds

        assert ds.metadata.verify(str(saved / "f1.json")).path == str(saved / "f1.json")
        assert ds.metadata.verify([str(saved / "f1.json"), str(saved / "f2.json")]).path is None
