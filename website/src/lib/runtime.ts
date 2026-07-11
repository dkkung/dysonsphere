// Shared Pyodide runtime for the playground and Chart Studio.
//
// Boots once per page session (singleton promise) and is reused by every consumer, so opening
// the playground warms up Chart Studio and vice versa. The runtime loads dysonsphere (+ polars,
// scipy, altair) from PyPI via micropip; the browser HTTP cache makes later boots fast.
//
// The Python side exposes three entry points:
//   _run_chart(code, dark)      - exec a user snippet that defines `chart`, return the spec JSON.
//   _load_table(name, text)     - write an uploaded CSV/TSV/JSON into the runtime's virtual
//                                 filesystem under its real filename AND parse it, returning the
//                                 column schema as JSON (used by Chart Studio). Because the file
//                                 exists in the FS, the emitted `pl.read_csv("file.csv")` snippet
//                                 runs verbatim - shown code and executed code are the same.
//   _read_export(name)          - ds.read(name, what="metadata") on a saved JSON/SVG/PNG already
//                                 written into the FS (the studio's export-import tools); the
//                                 JS side also exposes a raw FS writeFile for those uploads.
// Site render args (darkmode / transparent) are applied just before serializing,
// never shown in user code.

const PYODIDE_URL = 'https://cdn.jsdelivr.net/pyodide/v314.0.2/full/';

export interface DsRuntime {
	runChart(code: string, dark: boolean): string;
	loadTable(name: string, text: string, format: 'csv' | 'tsv' | 'json'): string;
	/** Write a file (text or binary) into the runtime's virtual FS under its real name. */
	writeFile(name: string, data: Uint8Array | string): void;
	/** Bundle a vega_datasets table into the FS as <name>.csv; returns the schema JSON. */
	loadDataset(name: string): string;
	/** ds.read(name, what="metadata") -> the embedded dysonsphere block as a JSON string. */
	readExport(name: string): string;
	/** Palette names of the INSTALLED library (the PyPI release, which can lag the site). */
	listPalettes(): string[];
}

type StatusListener = (message: string) => void;

let bootPromise: Promise<DsRuntime> | null = null;
let lastStatus = '';
const listeners = new Set<StatusListener>();

function announce(message: string) {
	lastStatus = message;
	listeners.forEach((fn) => fn(message));
}

/** Subscribe to boot progress messages; immediately replays the latest one. */
export function onRuntimeStatus(fn: StatusListener): () => void {
	listeners.add(fn);
	if (lastStatus) fn(lastStatus);
	return () => listeners.delete(fn);
}

/** True once the runtime is booted (never blocks). */
export function runtimeReady(): boolean {
	return ready;
}
let ready = false;

import sitePalettes from '../generated/palettes.json';

const PY_BOOTSTRAP = `
import json
import altair as alt
import polars as pl

_studio_tables = {}

def _run_chart(code, dark):
    # __tables__ gives Chart Studio's internal snippets access to uploaded data; the code the
    # user SEES reads their file from disk instead (pl.read_csv(...)), which is the honest form.
    #
    # Match the site theme: invert ink for dark and draw transparent so the page provides
    # contrast. Injected by monkeypatching ds.theme during exec (the same technique as
    # scripts/gen_examples.py) so the args apply no matter where the snippet calls theme() -
    # never part of the user's shown code.
    import functools
    import dysonsphere as ds
    real_theme = ds.theme

    @functools.wraps(real_theme)
    def patched_theme(*args, **kwargs):
        kwargs["darkmode"] = dark
        kwargs["transparent"] = True
        return real_theme(*args, **kwargs)

    patched_theme()  # baseline, in case the snippet never calls ds.theme()
    ds.theme = patched_theme
    try:
        ns = {"__tables__": _studio_tables}
        exec(code, ns)
    finally:
        ds.theme = real_theme
    ch = ns.get("chart")
    if ch is None:
        raise RuntimeError("Define a variable named 'chart' (a dysonsphere/Altair chart).")
    spec = ch.to_dict()
    ds.clear_stats()  # statistics records are per-run; never leak across renders
    return json.dumps(spec)

def _read_export(name):
    # The embedded dysonsphere block (provenance/statistics/theme/report) from a saved
    # JSON, SVG, or PNG - ds.read parses all three; the file was written into the FS first.
    import dysonsphere as ds
    block = ds.read(name, what="metadata")
    if not block:
        raise RuntimeError("No dysonsphere metadata block found in this file.")
    return json.dumps(block, ensure_ascii=False)

def _schema_json(df):
    schema = [
        {"name": c, "dtype": str(t), "kind": (
            "quantitative" if t.is_numeric() else
            "temporal" if t.is_temporal() else "nominal"),
         "nUnique": df[c].n_unique()}
        for c, t in df.schema.items()
    ]
    return json.dumps({"rows": df.height, "columns": schema})

def _load_table(name, text, format):
    import io
    from pathlib import Path
    # The file lands in the virtual FS under its real name, so the emitted
    # pl.read_csv(name) / pl.read_json(name) line runs exactly as shown.
    Path(name).write_text(text, encoding="utf-8")
    if format == "json":
        df = pl.read_json(text.encode())
    else:
        df = pl.read_csv(io.StringIO(text), separator="\\t" if format == "tsv" else ",")
    _studio_tables[name] = df
    return _schema_json(df)

def _load_dataset(name):
    # Bundle a vega_datasets classic into the FS as <name>.csv, so the emitted
    # pl.read_csv("<name>.csv") line runs exactly as shown.
    import dysonsphere as ds
    from vega_datasets import data
    df = ds.ensure_polars(getattr(data, name)())
    df.write_csv(f"{name}.csv")
    _studio_tables[f"{name}.csv"] = df
    return _schema_json(df)
`;

/**
 * Boot (or reuse) the shared runtime. Progress is announced through onRuntimeStatus so every
 * consumer sees the same messages regardless of who triggered the boot.
 */
export function getRuntime(): Promise<DsRuntime> {
	if (bootPromise) return bootPromise;
	bootPromise = (async () => {
		announce('Loading Pyodide (WebAssembly runtime)…');
		const { loadPyodide } = await import(/* @vite-ignore */ PYODIDE_URL + 'pyodide.mjs');
		const pyodide = await loadPyodide({ indexURL: PYODIDE_URL });

		announce('Installing dysonsphere + polars + scipy (first load, tens of MB)…');
		await pyodide.loadPackage('micropip');
		// dysonsphere >= 3.1.0 declares vl-convert-python (the save() renderer) as a runtime
		// dependency, and it has no WebAssembly wheel - a plain `micropip.install("dysonsphere")`
		// fails outright. Install dysonsphere without deps and pull the importable ones
		// explicitly; vl_convert is imported lazily only when save() renders, which the studio
		// never does. vega-datasets so example snippets (the classic datasets) run unchanged.
		await pyodide.runPythonAsync(`
import micropip
await micropip.install(["altair", "numpy", "polars", "pyarrow", "scipy", "vega-datasets"])
await micropip.install("dysonsphere", deps=False)
`);

		await pyodide.runPythonAsync(PY_BOOTSTRAP);
		// Bridge the release gap: palettes the site knows but the installed PyPI release
		// lacks are registered through dysonsphere's own custom-palette mechanism (a
		// [palettes] table in dysonsphere.toml in the FS cwd), then loaded with a theme()
		// call - so the Studio renders them exactly like built-ins until the release
		// catches up, and the dropdown pruning keeps them.
		const installed = new Set<string>(
			JSON.parse(pyodide.runPython('import json, dysonsphere; json.dumps(list(dysonsphere.colors))')),
		);
		const missing = (sitePalettes as { name: string; colors: string[] }[]).filter((p) => !installed.has(p.name));
		if (missing.length) {
			const toml =
				'[palettes]\n' +
				missing.map((p) => `${p.name} = [${p.colors.map((c) => `"${c}"`).join(', ')}]`).join('\n') +
				'\n';
			pyodide.FS.writeFile('dysonsphere.toml', toml);
			pyodide.runPython('import dysonsphere; dysonsphere.theme()');
		}
		const runChartPy = pyodide.globals.get('_run_chart');
		const loadTablePy = pyodide.globals.get('_load_table');
		const readExportPy = pyodide.globals.get('_read_export');
		const loadDatasetPy = pyodide.globals.get('_load_dataset');

		ready = true;
		announce('Ready.');
		return {
			runChart: (code: string, dark: boolean) => runChartPy(code, dark) as string,
			loadTable: (name: string, text: string, format: 'csv' | 'tsv' | 'json') =>
				loadTablePy(name, text, format) as string,
			writeFile: (name: string, data: Uint8Array | string) => pyodide.FS.writeFile(name, data),
			loadDataset: (name: string) => loadDatasetPy(name) as string,
			readExport: (name: string) => readExportPy(name) as string,
			listPalettes: () =>
				JSON.parse(pyodide.runPython('import json, dysonsphere; json.dumps(list(dysonsphere.colors))')),
		};
	})();
	bootPromise.catch(() => {
		// Allow a retry after a failed boot (e.g. offline first visit).
		bootPromise = null;
		ready = false;
	});
	return bootPromise;
}
