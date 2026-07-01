import json
import re
import struct
import zlib

import altair as alt
import polars as pl
import pytest

from dysonsphere.export import save
from dysonsphere.metadata import _inject_png_metadata
from dysonsphere.theme import theme

_PROV_ORDER = ["vegaliteChecksum", "exportIdentifier", "user", "script", "timestamp", "python", "altair", "dysonsphere"]


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
        return ds.mark_strip(df, "g", "v", cats) + ds.add_comparisons(df, "g", "v", test="anova", categories=cats)

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
        chart = alt.Chart(df).mark_point().encode(x="x:Q", y="y:Q") + ds.add_correlation(df, "x", "y")
        save(chart, str(tmp_path / "out"), background=["light"])
        rec = self._usermeta(tmp_path)["dysonsphere"]["statistics"][0]
        assert rec["kind"] == "correlation" and rec["method"] == "pearson"
        assert isinstance(rec["coefficient"]["value"], float) and rec["fit"]["slope"] is not None

    def test_no_statistics_key_without_add_comparisons(self, simple_chart, tmp_path):
        save(simple_chart, str(tmp_path / "out"), background=["light"])
        assert "statistics" not in self._usermeta(tmp_path)["dysonsphere"]

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

    def test_theme_baked_as_ds_theme_args(self, stats_chart, tmp_path):
        import dysonsphere as ds

        ds.theme(chartWidth=180, sigFigs=2)
        save(stats_chart, str(tmp_path / "out"), background=["light"])
        theme = self._usermeta(tmp_path)["dysonsphere"]["theme"]
        assert theme["chartWidth"] == 180 and theme["sigFigs"] == 2
        assert "tickWidth" not in theme  # only _BUILTIN_DEFAULTS keys (valid ds.theme() kwargs)


class TestReadLoad:
    @pytest.fixture
    def saved(self, tmp_path):
        import numpy as np

        import dysonsphere as ds

        ds.theme(chartWidth=180, sigFigs=2, saveFormat=["svg", "png", "json"])
        rng = np.random.default_rng(0)
        df = pl.DataFrame({"g": ["A"] * 30 + ["B"] * 30, "v": np.r_[rng.normal(0, 1, 30), rng.normal(2, 1, 30)]})
        chart = alt.Chart(df).mark_boxplot().encode(x="g:N", y="v:Q") + ds.add_comparisons(
            df, "g", "v", [("A", "B")], categories=["A", "B"]
        )
        ds.save(chart, str(tmp_path / "t"), background=["light"])
        return tmp_path

    def test_read_report_from_each_format(self, saved):
        import dysonsphere as ds

        for name in ("t.json", "t.svg", "t.png"):
            r = ds.read(str(saved / name))  # what="report" default
            assert isinstance(r, str) and r.startswith("Statistics")

    def test_read_statistics_exact_floats(self, saved):
        import dysonsphere as ds

        stats = ds.read(str(saved / "t.png"), what="statistics")
        assert isinstance(stats, list)
        p = stats[0]["comparisons"]["pairs"][0]["pvalue"]
        assert isinstance(p, float) and 0 < p < 1e-6  # exact, not the floored display value

    def test_read_metadata_has_all_keys(self, saved):
        import dysonsphere as ds

        m = ds.read(str(saved / "t.svg"), what="metadata")
        assert isinstance(m, dict)
        assert set(m) == {"provenance", "statistics", "theme", "report"}
        assert m["theme"]["chartWidth"] == 180
        # report is a container keyed by section, not a bare string
        assert list(m["report"]) == ["statistics", "provenance"]  # consistent order across formats
        assert m["report"]["statistics"].startswith("Statistics")
        assert m["report"]["provenance"].startswith("Provenance")

    def test_read_report_rerenders_without_embedded_prose(self, tmp_path):
        import numpy as np

        import dysonsphere as ds

        df = pl.DataFrame({"g": ["A"] * 20 + ["B"] * 20, "v": np.r_[np.zeros(20), np.ones(20)]})
        chart = alt.Chart(df).mark_boxplot().encode(x="g:N", y="v:Q") + ds.add_comparisons(
            df, "g", "v", [("A", "B")], pvalues=[0.01], categories=["A", "B"]
        )
        ds.save(chart, str(tmp_path / "u"), embedReport=False, background=["light"])
        # no embedded prose, but statistics are present → read re-renders the table
        r = ds.read(str(tmp_path / "u.png"))
        assert isinstance(r, str) and r.startswith("Statistics")

    def test_report_provenance_sentence(self, saved):
        import dysonsphere as ds

        m = ds.read(str(saved / "t.png"), what="metadata")
        assert isinstance(m, dict)
        prov = m["report"]["provenance"]
        assert prov.startswith("Provenance\n") and "Generated by " in prov
        assert m["provenance"]["dysonsphere"] in prov  # renders the actual version

    def test_stats_free_chart_reads_provenance(self, tmp_path):
        import dysonsphere as ds

        chart = alt.Chart(pl.DataFrame({"x": [1, 2, 3], "y": [1.0, 2.0, 3.0]})).mark_point().encode(x="x:Q", y="y:Q")
        ds.save(chart, str(tmp_path / "bare"), background=["light"])
        m = ds.read(str(tmp_path / "bare.json"), what="metadata")
        assert isinstance(m, dict)
        assert list(m["report"]) == ["provenance"]  # no statistics section, but provenance is there
        r = ds.read(str(tmp_path / "bare.svg"))  # what="report" — no longer blank
        assert isinstance(r, str) and r.startswith("Provenance")

    def test_read_invalid_what_raises(self, saved):
        import dysonsphere as ds

        with pytest.raises(ValueError, match="what must be"):
            ds.read(str(saved / "t.json"), what="bogus")

    def test_read_unsupported_extension_raises(self, tmp_path):
        import dysonsphere as ds

        (tmp_path / "x.txt").write_text("hi")
        with pytest.raises(ValueError, match="supports .png"):
            ds.read(str(tmp_path / "x.txt"))

    def test_load_returns_composable_object(self, saved):
        import dysonsphere as ds

        obj = ds.load(str(saved / "t.json"))
        assert isinstance(obj, alt.LayerChart)
        assert isinstance(obj + alt.Chart().mark_point(), alt.LayerChart)  # composes

    def test_load_reapplies_theme(self, saved):
        import dysonsphere as ds

        ds.theme(chartWidth=999)  # clobber
        ds.load(str(saved / "t.json"))  # applyTheme=True default
        assert alt.theme.options["chartWidth"] == 180  # restored from the baked theme

    def test_load_apply_theme_false_leaves_theme(self, saved):
        import dysonsphere as ds

        ds.theme(chartWidth=999)
        ds.load(str(saved / "t.json"), applyTheme=False)
        assert alt.theme.options["chartWidth"] == 999  # untouched

    def test_load_raw_returns_spec_dict(self, saved):
        import dysonsphere as ds

        ds.theme(chartWidth=999)
        spec = ds.load(str(saved / "t.json"), raw=True)
        assert isinstance(spec, dict) and "config" in spec  # raw spec, theme config intact
        assert alt.theme.options["chartWidth"] == 999  # globals untouched

    def test_load_requires_json(self, saved):
        import dysonsphere as ds

        with pytest.raises(ValueError, match="Vega-Lite JSON"):
            ds.load(str(saved / "t.png"))

    def test_read_no_metadata_raises(self, tmp_path):
        import dysonsphere as ds

        chart = alt.Chart(pl.DataFrame({"x": [1, 2], "y": [1.0, 2.0]})).mark_point().encode(x="x:Q", y="y:Q")
        ds.save(chart, str(tmp_path / "bare"), saveMetadata=False, background=["light"])
        with pytest.raises(ValueError, match="no dysonsphere metadata"):
            ds.read(str(tmp_path / "bare.json"))

    def test_read_report_save_writes_txt(self, saved, tmp_path):
        import dysonsphere as ds

        outdir = tmp_path / "reports"
        ds.read(str(saved / "t.png"), save=str(outdir))
        txts = list(outdir.glob("dysonsphere_report_*.txt"))
        assert len(txts) == 1 and txts[0].read_text(encoding="utf-8").startswith("Statistics")


# ── _fix_tick_alignment() ─────────────────────────────────────────────────────


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
        chart = alt.Chart(df).mark_boxplot().encode(x="g:N", y="v:Q") + ds.add_comparisons(
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
        assert "__dysonsphere_" not in (tmp_path / "s.json").read_text()
        assert "__dysonsphere_" not in (tmp_path / "s.svg").read_text()

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

    def test_clear_stats_empties_queue(self):
        import dysonsphere as ds
        from dysonsphere.statistics import _REPORTS

        self._stats_layer()
        assert len(_REPORTS) >= 1
        ds.clear_stats()
        assert len(_REPORTS) == 0
