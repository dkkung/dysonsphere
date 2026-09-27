// Scale a rendered chart by resizing its <svg> natively, instead of CSS `zoom` on the wrapper.
//
// dysonsphere charts are authored at the library's publication defaults (100x100 px, small
// fonts/marks), so the site scales the whole render up uniformly. That used to be
// `zoom: var(--ds-chart-zoom)` on the vega-embed wrapper. Firefox mis-maps SVG gradients inside
// a zoomed subtree: a continuous legend's colour bar sampled only the top ~15% of its ramp (an
// australis bar rendered green->cyan with no purple or blue), while the marks beside it were
// correct because they carry flat per-element fills. Chromium and WebKit are unaffected, so it
// looked like a spec bug rather than a rendering one.
//
// Vega's SVG carries a viewBox, so setting width/height scales it natively - no CSS scaling in
// the tree at all, gradients resolve correctly in every engine, and the layout box follows the
// render (which `transform: scale()` would not do). The viewBox is the source of truth for the
// natural size, so re-applying never compounds.
//
// The factor still comes from the --ds-chart-zoom custom property, so every per-context override
// (the landing hero, the palette preview) keeps working unchanged.

/** Natural (unscaled) dimensions of either display renderer. */
export function chartNaturalSize(el: HTMLElement): { width: number; height: number } | null {
	const canvas = el.querySelector<HTMLCanvasElement>('canvas.marks');
	if (canvas) {
		const width = Number(canvas.dataset.dsNaturalWidth), height = Number(canvas.dataset.dsNaturalHeight);
		return width > 0 && height > 0 ? { width, height } : null;
	}
	const box = el.querySelector('svg')?.viewBox?.baseVal;
	return box && box.width > 0 && box.height > 0 ? { width: box.width, height: box.height } : null;
}

export type ResizableView = {
	container: () => HTMLElement;
	initialize: (element: HTMLElement) => { runAsync: () => Promise<unknown> };
};

/** Scale a chart; Canvas redraws at zoom × devicePixelRatio for sharpness and correct picking. */
export function scaleChart(el: HTMLElement, factor?: number, view?: ResizableView): void {
	const natural = chartNaturalSize(el);
	if (!natural) return;
	const requested = factor ?? parseFloat(getComputedStyle(el).getPropertyValue('--ds-chart-zoom'));
	if (!(requested > 0)) return;
	const canvas = el.querySelector<HTMLCanvasElement>('canvas.marks');
	if (canvas) {
		// Starlight limits media to max-width:100%. Fit before drawing instead of letting
		// CSS squeeze x while the canvas height and pointer scale remain at full zoom.
		const style = getComputedStyle(el);
		const figure = el.closest('figure.ds-chart');
		// vega-embed makes the chart element shrink-wrap its current canvas; its width
		// cannot be the available width. The figure's parent is the stable layout cell.
		const parentWidth = figure?.parentElement?.clientWidth ?? 0;
		const gutter = Math.max(0, el.clientWidth - canvas.getBoundingClientRect().width);
		const available = parentWidth > 0 ? parentWidth - gutter : el.clientWidth -
			(parseFloat(style.paddingLeft) || 0) - (parseFloat(style.paddingRight) || 0);
		const zoom = available > 0 ? Math.min(requested, available / natural.width) : requested;
		const dpr = window.devicePixelRatio || 1;
		if (el.dataset.dsZoom !== String(zoom) || canvas.dataset.dsDpr !== String(dpr)) {
			el.dataset.dsZoom = String(zoom);
			// Vega's view.resize() only resizes its renderer when layout geometry changes.
			// Site zoom changes pixels, not layout, so reinitialize the public View at
			// the same container to rebuild its renderer and handler at this resolution.
			if (view) void view.initialize(view.container()).runAsync();
		}
	} else {
		const svg = el.querySelector('svg');
		svg?.setAttribute('width', String(natural.width * requested));
		svg?.setAttribute('height', String(natural.height * requested));
	}
}

/** Scale the chart so it spans `available` px wide (size-matched comparisons). */
export function fitChartToWidth(el: HTMLElement, available: number, view?: ResizableView): void {
	const natural = chartNaturalSize(el);
	if (!natural || available <= 0) return;
	scaleChart(el, available / natural.width, view);
}

/** Recheck backing resolution after browser zoom or moving to a screen with another DPR. */
export function watchChartResolution(callback: () => void): () => void {
	let query: MediaQueryList | null = null;
	const changed = () => { attach(); callback(); };
	const attach = () => {
		query?.removeEventListener('change', changed);
		query = matchMedia(`(resolution: ${window.devicePixelRatio || 1}dppx)`);
		query.addEventListener('change', changed);
	};
	attach();
	window.addEventListener('resize', changed);
	return () => {
		query?.removeEventListener('change', changed);
		window.removeEventListener('resize', changed);
	};
}
