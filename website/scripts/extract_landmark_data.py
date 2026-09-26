#!/usr/bin/env python
"""Rebuild or verify the published-data extracts used by the landmark examples.

The chart examples run from inline data and need no source files or network. Verification reads
local source files. To refresh Rao's small region JSON with indexed requests, run
``uv run --with hic-straw==1.3.1 python website/scripts/extract_landmark_data.py
--fetch-rao /tmp/rao-region.json``. This reads only the needed byte ranges from the 54.7 GB UCSC
mirror, not the full file. Then pass that JSON plus the local Tabula CSV to the normal command.
``--write`` updates only the Rao block; Tabula is verify-only.

Sources:
- Rao et al. 2014 GM12878 Hi-C, GSE63525, UCSC hg19 mirror; Figure 6B region (10 kb).
- Tabula Muris 2018 pancreas FACS annotation CSV, authors' repository (BSD 3-Clause).
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import pprint
from importlib import metadata
from pathlib import Path
from typing import Any, cast

import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "website" / "examples"

RAO_URL = "https://hgdownload.soe.ucsc.edu/gbdb/hg19/bbi/hic/GSE63525_GM12878_insitu_primary+replicate_combined.hic"
RAO_SHA256 = "6224f2008fece6f750270a6c7311c2549c1af0fa734892e174047d1bd8356c8a"
RAO_ETAG = "cbefd3966-594578385481d"
RAO_LAST_MODIFIED = "Mon, 07 Oct 2019 20:01:13 GMT"
RAO_CONTENT_LENGTH = 54_743_873_894
RAO_CHROMOSOME = "chr4"
RAO_START_BP = 20_550_000
RAO_END_BP = 22_550_000
RAO_BIN_SIZE_BP = 10_000
TABULA_SHA256 = "d3d0f85af8aa8d4fc270ff83e9427fcaf0d76a604585f8733db6da47a52a36ba"

BLOCK_START = "# BEGIN EXTRACTED DATA"
BLOCK_END = "# END EXTRACTED DATA"


def _digest(path: Path, algorithm: str) -> str:
    hasher = hashlib.new(algorithm)
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _check_digest(path: Path, algorithm: str, expected: str) -> None:
    actual = _digest(path, algorithm)
    if actual != expected:
        raise ValueError(f"{path}: {algorithm} {actual}, expected {expected}")


def _fetch_rao_region(path: Path) -> None:
    """Fetch one Rao figure locus with indexed .hic queries, not a whole-file download."""
    try:
        hicstraw = cast(Any, importlib.import_module("hicstraw"))
    except ImportError as error:
        raise RuntimeError(
            "Install the temporary extractor with `uv run --with hic-straw==1.3.1`."}]}},{
        ) from error

    hic = hicstraw.HiCFile(RAO_URL)
    if hic.getGenomeID() != "hg19" or RAO_BIN_SIZE_BP not in hic.getResolutions():
        raise ValueError("The Rao .hic source genome or resolution does not match the pinned extraction.")
    raw_matrix = hic.getMatrixZoomData("4", "4", "observed", "NONE", "BP", RAO_BIN_SIZE_BP)
    kr_matrix = hic.getMatrixZoomData("4", "4", "observed", "KR", "BP", RAO_BIN_SIZE_BP)
    chromosome_index = next(chrom.index for chrom in hic.getChromosomes() if chrom.name == "4")
    weights = np.asarray(kr_matrix.getNormVector(chromosome_index), dtype=float)
    local_weights = weights[RAO_START_BP // RAO_BIN_SIZE_BP : RAO_END_BP // RAO_BIN_SIZE_BP]
    n_bins = (RAO_END_BP - RAO_START_BP) // RAO_BIN_SIZE_BP
    if local_weights.size != n_bins or not np.isfinite(local_weights).all() or (local_weights <= 0).any():
        raise ValueError("The Figure 6B locus has unexpected or invalid KR normalization values.")

    def records(matrix: Any, *, integer_counts: bool) -> dict[tuple[int, int], float]:
        result: dict[tuple[int, int], float] = {}
        for record in matrix.getRecords(RAO_START_BP, RAO_END_BP, RAO_START_BP, RAO_END_BP):
            x, y, count = int(record.binX), int(record.binY), float(record.counts)
            if not (RAO_START_BP <= x < RAO_END_BP and RAO_START_BP <= y < RAO_END_BP):
                continue
            if x > y or not np.isfinite(count) or count < 0 or (integer_counts and not count.is_integer()):
                raise ValueError("The Rao .hic query returned an invalid contact value or non-upper-triangle record.")
            if (x, y) in result:
                raise ValueError("The Rao .hic query returned a duplicate contact record.")
            result[(x, y)] = count
        return result

    raw_counts = records(raw_matrix, integer_counts=True)
    kr_counts = records(kr_matrix, integer_counts=False)
    checks = 0
    for (x, y), count in raw_counts.items():
        i, j = x // RAO_BIN_SIZE_BP, y // RAO_BIN_SIZE_BP
        if count and not np.isclose(count / (weights[i] * weights[j]), kr_counts.get((x, y), np.nan), rtol=1e-5):
            raise ValueError("Raw counts divided by the KR vector do not match the .hic KR records.")
        checks += int(bool(count))

    payload = {
        "source_url": RAO_URL,
        "paper_doi": "10.1016/j.cell.2014.11.021",
        "paper_locus": "Figure 6B",
        "source_dataset": "GSE63525 GM12878 in situ primary + replicate combined",
        "source_etag": RAO_ETAG,
        "source_last_modified": RAO_LAST_MODIFIED,
        "source_content_length": RAO_CONTENT_LENGTH,
        "hicstraw_version": metadata.version("hic-straw"),
        "genome": hic.getGenomeID(),
        "chromosome": RAO_CHROMOSOME,
        "start": RAO_START_BP,
        "end": RAO_END_BP,
        "bin_size": RAO_BIN_SIZE_BP,
        "normalization": "KR",
        "normalization_operation": "raw_count / (kr_vector[i] * kr_vector[j])",
        "kr_vector": [float(value) for value in local_weights],
        "raw_upper_records": [
            [(x - RAO_START_BP) // RAO_BIN_SIZE_BP, (y - RAO_START_BP) // RAO_BIN_SIZE_BP, int(count)]
            for (x, y), count in sorted(raw_counts.items())
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    print(f"Indexed raw/KR records checked: {checks}")
    print(f"Wrote {path} ({path.stat().st_size} bytes; SHA-256 {_digest(path, 'sha256')})")


def _extract_rao(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    _check_digest(path, "sha256", RAO_SHA256)
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "source_url": RAO_URL,
        "paper_doi": "10.1016/j.cell.2014.11.021",
        "paper_locus": "Figure 6B",
        "source_dataset": "GSE63525 GM12878 in situ primary + replicate combined",
        "source_etag": RAO_ETAG,
        "source_last_modified": RAO_LAST_MODIFIED,
        "source_content_length": RAO_CONTENT_LENGTH,
        "genome": "hg19",
        "chromosome": RAO_CHROMOSOME,
        "start": RAO_START_BP,
        "end": RAO_END_BP,
        "bin_size": RAO_BIN_SIZE_BP,
        "normalization": "KR",
        "normalization_operation": "raw_count / (kr_vector[i] * kr_vector[j])",
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise ValueError(f"Rao region JSON has unexpected {key}: {payload.get(key)!r}")

    n_bins = (RAO_END_BP - RAO_START_BP) // RAO_BIN_SIZE_BP
    weights = np.asarray(payload["kr_vector"], dtype=float)
    if weights.shape != (n_bins,) or not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError("The Rao region must have one finite positive KR value for each 10 kb bin.")
    raw_records = payload["raw_upper_records"]
    counts = np.zeros((n_bins, n_bins), dtype=np.int64)
    seen: set[tuple[int, int]] = set()
    for record in raw_records:
        if len(record) != 3:
            raise ValueError("Each Rao raw contact record must be [upper_i, upper_j, count].")
        i, j, count = record
        if not (isinstance(i, int) and isinstance(j, int) and isinstance(count, int)):
            raise ValueError("Rao raw contact indexes and counts must be integers.")
        if not (0 <= i <= j < n_bins) or count < 0 or (i, j) in seen:
            raise ValueError("Rao raw contacts must be unique, nonnegative upper-triangle records.")
        seen.add((i, j))
        counts[i, j] = count
    symmetric = counts + counts.T - np.diag(np.diag(counts))
    balanced = symmetric / (weights[:, None] * weights[None, :])
    positive = balanced[symmetric > 0]
    if len(raw_records) != 20_032 or not len(positive):
        raise ValueError(f"Unexpected Rao sparse matrix record count: {len(raw_records)}")
    saturation = float(np.quantile(positive, 0.995))
    literals = {
        "REGION_START_BP": RAO_START_BP,
        "REGION_END_BP": RAO_END_BP,
        "BIN_SIZE_BP": RAO_BIN_SIZE_BP,
        "KR_VECTOR": weights.tolist(),
        "RAW_UPPER_RECORDS": raw_records,
    }
    summary = {
        "bins": n_bins,
        "valid_bins": int(np.isfinite(weights).sum()),
        "upper_records": len(raw_records),
        "nonzero_cells": int((symmetric > 0).sum()),
        "zero_cells": int((symmetric == 0).sum()),
        "saturation_kr": saturation,
        "saturated_cells": int((positive > saturation).sum()),
    }
    return literals, summary


def _extract_tabula(path: Path) -> tuple[dict[str, Any], dict[str, int]]:
    _check_digest(path, "sha256", TABULA_SHA256)
    frame = pl.read_csv(path)
    required = {"cell", "cell_ontology_class", "tSNE_1", "tSNE_2"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Tabula Muris CSV is missing columns: {sorted(required - set(frame.columns))}")
    if frame.height != 1_564 or frame["cell"].n_unique() != frame.height:
        raise ValueError("Expected 1,564 unique Tabula Muris cell rows")
    if any(frame[column].null_count() for column in required):
        raise ValueError("A plotted Tabula Muris column contains missing values")

    counts = frame.group_by("cell_ontology_class").len().to_dicts()
    ordered = sorted(counts, key=lambda row: (-int(row["len"]), str(row["cell_ontology_class"])))
    cell_types = [str(row["cell_ontology_class"]) for row in ordered]
    type_counts = [int(row["len"]) for row in ordered]
    type_ids = [cell_types.index(str(value)) for value in frame["cell_ontology_class"].to_list()]
    x_values = [float(value) for value in frame["tSNE_1"].to_list()]
    y_values = [float(value) for value in frame["tSNE_2"].to_list()]
    if not np.isfinite(np.asarray(x_values + y_values, dtype=float)).all():
        raise ValueError("Tabula Muris t-SNE coordinates must be finite")

    literals = {
        "CELL_TYPES": cell_types,
        "CELL_TYPE_COUNTS": type_counts,
        "CELL_TYPE_IDS": type_ids,
        "TSNE_X": x_values,
        "TSNE_Y": y_values,
    }
    return literals, {"cells": frame.height, "cell_types": len(cell_types)}


def _read_literals(path: Path, names: set[str]) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in names:
                found[target.id] = ast.literal_eval(node.value)
    missing = names - found.keys()
    if missing:
        raise ValueError(f"{path}: missing literal assignments: {', '.join(sorted(missing))}")
    return found


def _write_block(path: Path, assignments: dict[str, Any]) -> None:
    original = path.read_text(encoding="utf-8")
    if original.count(BLOCK_START) != 1 or original.count(BLOCK_END) != 1:
        raise ValueError(f"{path}: expected one extracted-data marker pair")
    before, rest = original.split(BLOCK_START, 1)
    _, after = rest.split(BLOCK_END, 1)
    block = "\n".join(
        f"{name} = {pprint.pformat(value, width=110, compact=True, sort_dicts=False)}"
        for name, value in assignments.items()
    )
    path.write_text(f"{before}{BLOCK_START}\n{block}\n{BLOCK_END}{after}", encoding="utf-8")


def _verify_or_write(path: Path, expected: dict[str, Any], write: bool) -> None:
    if write:
        _write_block(path, expected)
    actual = _read_literals(path, set(expected))
    if actual != expected:
        raise ValueError(f"{path}: inline data differs from the verified source extraction")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-rao", type=Path, help="write the bounded Rao .hic region JSON to this path")
    parser.add_argument("--rao", type=Path, help="local SHA-verified Rao Figure 6B region JSON")
    parser.add_argument("--tabula", type=Path, help="local original pancreas FACS CSV")
    parser.add_argument("--write", action="store_true", help="rewrite the Rao data block only")
    args = parser.parse_args()

    if args.fetch_rao is not None:
        if args.rao is not None or args.tabula is not None or args.write:
            parser.error("--fetch-rao is a separate command; do not combine it with verification arguments")
        _fetch_rao_region(args.fetch_rao)
        return
    if args.rao is None or args.tabula is None:
        parser.error("pass --rao and --tabula, or run the separate --fetch-rao command")

    rao, rao_summary = _extract_rao(args.rao)
    tabula, tabula_summary = _extract_tabula(args.tabula)
    _verify_or_write(EXAMPLES / "rao_hic.py", rao, args.write)
    _verify_or_write(EXAMPLES / "tabula_muris_pancreas.py", tabula, False)

    print(
        f"Rao {RAO_CHROMOSOME}:{RAO_START_BP}-{RAO_END_BP} hg19, {RAO_BIN_SIZE_BP // 1000} kb: "
        f"{rao_summary['bins']} bins, {rao_summary['valid_bins']} valid KR values; "
        f"{rao_summary['upper_records']} upper records, {rao_summary['nonzero_cells']} nonzero cells, "
        f"{rao_summary['zero_cells']} true zero contacts; log scale p99.5={rao_summary['saturation_kr']:.3g}, "
        f"{rao_summary['saturated_cells']} cells clipped"
    )
    print(f"Tabula Muris verified unchanged: {tabula_summary['cells']} cells, {tabula_summary['cell_types']} classes")
    if args.write:
        print("Updated Rao data block; Tabula data was verify-only.")


if __name__ == "__main__":
    main()
