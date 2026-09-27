import vegaEmbed from 'vega-embed';
import { CANVAS_RENDERER } from './chartCanvas.ts';
import { chartRenderer } from './chartRenderer.ts';
import { alignFigureLabels, alignGridToContent, flipTicksInward, italicizeStatSymbols, typesetScripts } from './fixSuperscripts.ts';
import type { ResizableView } from './scaleChart.ts';

type ChartSpec = Record<string, any>;
type Embedded = { finalize: () => void; view: ResizableView };
type State = { generation: number; pending: Promise<void>; result?: Embedded };
const states = new WeakMap<HTMLElement, State>();

export function chartView(el: HTMLElement): ResizableView | undefined {
	return states.get(el)?.result?.view;
}

export function clearChart(el: HTMLElement): void {
	const state = states.get(el);
	if (!state) return;
	state.generation++;
	state.result?.finalize();
	state.result = undefined;
	el.replaceChildren();
}

/** Serialize embeds into one element so a slow prior render cannot overwrite a newer request. */
export function embedChart(
	el: HTMLElement,
	load: (() => Promise<ChartSpec> | ChartSpec) | ChartSpec,
	options: { actions: boolean; inward?: boolean; background?: string; flipBeforeText?: boolean;
		afterRender?: () => void; embed?: typeof vegaEmbed },
): Promise<void> {
	let state = states.get(el);
	if (!state) {
		state = { generation: 0, pending: Promise.resolve() };
		states.set(el, state);
	}
	const current = state;
	const id = ++current.generation;
	// Start the fetch immediately, so independent charts load concurrently. Ignore stale results.
	const spec = Promise.resolve().then(() => typeof load === 'function' ? load() : load);
	current.pending = current.pending.catch(() => {}).then(async () => {
		const resolved = await spec;
		if (id !== current.generation || !el.isConnected) return;
		current.result?.finalize();
		current.result = undefined;
		el.replaceChildren();
		const renderer = chartRenderer(resolved, options.inward);
		const opaque = Boolean(resolved.background ?? resolved.config?.background);
		const result = await (options.embed ?? vegaEmbed)(el, resolved, {
			actions: options.actions,
			renderer: (renderer === 'svg' ? 'svg' : CANVAS_RENDERER) as 'svg' | 'canvas',
			...(opaque ? {} : { background: options.background ?? 'transparent' }),
		});
		if (id !== current.generation || !el.isConnected) {
			result.finalize();
			return;
		}
		current.result = result;
		if (renderer === 'svg') {
			alignGridToContent(el, resolved);
			alignFigureLabels(el);
			const inward = options.inward || resolved.usermeta?.dysonsphere?.theme?.tickDirection === 'in';
			if (inward && options.flipBeforeText) flipTicksInward(el);
			typesetScripts(el);
			italicizeStatSymbols(el);
			if (inward && !options.flipBeforeText) flipTicksInward(el);
		}
		options.afterRender?.();
	});
	return current.pending;
}
