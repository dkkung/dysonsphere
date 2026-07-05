// Shared Pyodide runtime for the playground and Chart Studio.
//
// Boots once per page session (singleton promise) and is reused by every consumer, so opening
// the playground warms up Chart Studio and vice versa. The runtime loads dysonsphere (+ polars,
// scipy, altair) from PyPI via micropip; the browser HTTP cache makes later boots fast.
//
// The Python side exposes two entry points:
//   _run_chart(code, dark)      - exec a user snippet that defines `chart`, return the spec JSON.
//   _load_table(name, text)     - parse uploaded CSV/TSV/JSON text into a named polars DataFrame,
//                                 return its column schema as JSON (used by Chart Studio).
// Site render args (darkmode / transparentBackground) are applied just before serializing,
// never shown in user code.

const PYODIDE_URL = 'https://cdn.jsdelivr.net/pyodide/v314.0.2/full/';

export interface DsRuntime {
	runChart(code: string, dark: boolean): string;
	loadTable(name: string, text: string, format: 'csv' | 'tsv' | 'json'): string;
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

const PY_BOOTSTRAP = `
import json
import altair as alt
import polars as pl

_studio_tables = {}

def _run_chart(code, dark):
    # __tables__ gives Chart Studio's internal snippets access to uploaded data; the code the
    # user SEES reads their file from disk instead (pl.read_csv(...)), which is the honest form.
    ns = {"__tables__": _studio_tables}
    exec(code, ns)
    ch = ns.get("chart")
    if ch is None:
        raise RuntimeError("Define a variable named 'chart' (a dysonsphere/Altair chart).")
    # Match the site theme: invert ink for dark and draw transparent so the page provides
    # contrast. Applied just before serializing - never part of the user's snippet.
    alt.theme.options["darkmode"] = dark
    alt.theme.options["transparentBackground"] = True
    return json.dumps(ch.to_dict())

def _load_table(name, text, format):
    import io
    if format == "json":
        df = pl.read_json(text.encode())
    else:
        df = pl.read_csv(io.StringIO(text), separator="\\t" if format == "tsv" else ",")
    _studio_tables[name] = df
    schema = [
        {"name": c, "dtype": str(t), "kind": (
            "quantitative" if t.is_numeric() else
            "temporal" if t.is_temporal() else "nominal")}
        for c, t in df.schema.items()
    ]
    return json.dumps({"rows": df.height, "columns": schema})
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
		const micropip = pyodide.pyimport('micropip');
		// vega-datasets so example snippets (which use the classic datasets) run unchanged.
		await micropip.install(['dysonsphere', 'vega-datasets']);

		await pyodide.runPythonAsync(PY_BOOTSTRAP);
		const runChartPy = pyodide.globals.get('_run_chart');
		const loadTablePy = pyodide.globals.get('_load_table');

		ready = true;
		announce('Ready.');
		return {
			runChart: (code: string, dark: boolean) => runChartPy(code, dark) as string,
			loadTable: (name: string, text: string, format: 'csv' | 'tsv' | 'json') =>
				loadTablePy(name, text, format) as string,
		};
	})();
	bootPromise.catch(() => {
		// Allow a retry after a failed boot (e.g. offline first visit).
		bootPromise = null;
		ready = false;
	});
	return bootPromise;
}
