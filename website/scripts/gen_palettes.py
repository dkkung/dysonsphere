#!/usr/bin/env python
"""Dump every dysonsphere palette to a JSON the site can render as live swatches.

Writes website/src/generated/palettes.json: an ordered list of
``{"name": str, "kind": "sequential"|"diverging", "colors": [hex, ...]}`` for the Palettes browser
(a pure client-side component - no Pyodide needed to preview color).

Run from the repo/worktree root:

    uv run python website/scripts/gen_palettes.py
"""

from __future__ import annotations

import json
from pathlib import Path

import dysonsphere as ds

OUT = Path("website/src/generated/palettes.json")


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    palettes = []
    for name, colors in ds.colors.items():
        # By stop count: diverging ramps carry 13 (neutral midpoint), sequential ramps 12; the
        # remaining short palettes (nucleotides, proteins, the matplotlib sets) are qualitative.
        if len(colors) == 13:
            kind = "diverging"
        elif len(colors) == 12:
            kind = "sequential"
        else:
            kind = "qualitative"
        palettes.append({"name": name, "kind": kind, "colors": list(colors)})
    OUT.write_text(json.dumps(palettes), encoding="utf-8")
    print(f"wrote {len(palettes)} palettes to {OUT}")


if __name__ == "__main__":
    main()
