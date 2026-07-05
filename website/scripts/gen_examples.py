#!/usr/bin/env python
"""Execute every example under website/examples/ and write light + dark Vega-Lite specs.

The example registry: each ``website/examples/<name>.py`` is a complete, copy-runnable snippet
that defines a variable named ``chart`` (the same contract as the playground). This script executes
each file twice - once with ``darkmode=False`` and once with ``darkmode=True``, both with
``transparentBackground=True`` - and writes ``website/public/charts/<name>-light.json`` /
``<name>-dark.json`` for the Chart/Example components to render live.

The SAME source file is imported raw (vite ``?raw``) by ``Example.astro`` as the shown snippet, so
the displayed code and the rendered chart can never drift apart.

The site render args (``darkmode`` / ``transparentBackground``) are injected by monkeypatching
``ds.theme`` during exec - they never appear in the snippet, which stays exactly what a user
would write.

Run from the repo/worktree root:

    uv run --with vega-datasets python website/scripts/gen_examples.py [name ...]

With no arguments every example is rebuilt; with names, just those.
"""

from __future__ import annotations

import functools
import json
import sys
from pathlib import Path

import altair as alt

import dysonsphere as ds

EXAMPLES = Path("website/examples")
OUT = Path("website/public/charts")

_real_theme = ds.theme


def build(path: Path, dark: bool) -> dict:
    """Execute one example file and return the chart's Vega-Lite spec dict."""

    @functools.wraps(_real_theme)
    def patched_theme(*args, **kwargs):
        kwargs["darkmode"] = dark
        kwargs["transparentBackground"] = True
        return _real_theme(*args, **kwargs)

    # Baseline in case the snippet never calls ds.theme(); the patch covers it when it does.
    patched_theme()
    ds.theme = patched_theme
    try:
        ns: dict = {}
        exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), ns)
    finally:
        ds.theme = _real_theme
    chart = ns.get("chart")
    if chart is None:
        raise SystemExit(f"{path}: does not define a variable named 'chart'")
    spec = chart.to_dict()
    # The stats registry is per-process; clear between examples so records never cross charts.
    ds.clear_stats()
    return spec


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    names = sys.argv[1:]
    paths = sorted(EXAMPLES.glob("*.py"))
    if names:
        paths = [p for p in paths if p.stem in names]
        missing = set(names) - {p.stem for p in paths}
        if missing:
            raise SystemExit(f"no such example(s): {', '.join(sorted(missing))}")
    if not paths:
        raise SystemExit(f"no examples found under {EXAMPLES}")
    failures = []
    for path in paths:
        for mode, dark in (("light", False), ("dark", True)):
            try:
                spec = build(path, dark)
            except SystemExit:
                raise
            except Exception as e:  # keep going; report all broken examples at the end
                failures.append(f"{path.stem} ({mode}): {e}")
                break
            (OUT / f"{path.stem}-{mode}.json").write_text(json.dumps(spec), encoding="utf-8")
        else:
            print(f"built {path.stem}")
    # Restore a clean global theme for anything importing after us.
    alt.theme.enable("default")
    if failures:
        raise SystemExit("FAILED:\n  " + "\n  ".join(failures))


if __name__ == "__main__":
    main()
