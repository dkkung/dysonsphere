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
from dysonsphere.palettes import _CMOCEAN_PALETTES, _MATPLOTLIB_DISCRETE_PALETTES, _MATPLOTLIB_PALETTES

OUT = Path("website/src/generated/palettes.json")
ACCENTS_OUT = Path("website/src/generated/accents.json")


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    palettes = []
    for name, colors in ds.palettes.colors.items():
        # By stop count: diverging ramps carry 13 (neutral midpoint), sequential ramps 12; the
        # remaining short palettes (nucleotides, proteins, the matplotlib sets) are qualitative.
        # The assembled qualitative palettes are hue-cycling, not ramps.
        if name in {"cat1", "cat2", "cat3"} | _MATPLOTLIB_DISCRETE_PALETTES:
            kind = "qualitative"
        elif len(colors) == 13:
            kind = "diverging"
        elif len(colors) == 12:
            kind = "sequential"
        else:
            kind = "qualitative"
        source = (
            "cmocean" if name in _CMOCEAN_PALETTES else "matplotlib" if name in _MATPLOTLIB_PALETTES else "dysonsphere"
        )
        palettes.append({"name": name, "kind": kind, "source": source, "colors": list(colors)})
    OUT.write_text(json.dumps(palettes), encoding="utf-8")
    print(f"wrote {len(palettes)} palettes to {OUT}")
    light = ds.palettes._ACCENT_LIGHT
    dark = ds.palettes._ACCENT_DARK
    accents = [{"name": name, "light": light[name], "dark": dark[name]} for name in light if name != "gray"]
    ACCENTS_OUT.write_text(json.dumps(accents), encoding="utf-8")
    print(f"wrote {len(accents)} accents to {ACCENTS_OUT}")


if __name__ == "__main__":
    main()
