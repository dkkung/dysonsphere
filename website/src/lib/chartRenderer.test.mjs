import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { chartRenderer } from './chartRenderer.ts';
import { needsTextCorrections } from './fixSuperscripts.ts';
import { CANVAS_RENDERER, canvasGeometry, chartPointer } from './chartCanvas.ts';
import { chartNaturalSize, fitChartToWidth, scaleChart } from './scaleChart.ts';
import { embedChart, clearChart, chartView } from './embedChart.ts';
import { renderModule } from 'vega';

const spec = (name) => JSON.parse(readFileSync(new URL(`../../public/charts/${name}-light.json`, import.meta.url)));

test('normal charts and Rao select Canvas; SVG correction cases stay SVG', () => {
	for (const name of ['rao_hic', 'beeswarm', 'preview_bars', 'preview_ramp']) {
		assert.equal(chartRenderer(spec(name)), 'canvas', name);
	}
	for (const name of ['subscripts', 'violin_sample_size', 'assemble']) {
		assert.equal(chartRenderer(spec(name)), 'svg', name);
	}
	assert.equal(chartRenderer(spec('rao_hic'), true), 'svg');
	assert.equal(chartRenderer({ config: { axis: { offset: 4.5 } } }), 'svg');
	assert.equal(chartRenderer({ usermeta: { dysonsphere: { theme: { tickDirection: 'in' } } } }), 'svg');
	assert.equal(chartRenderer({ layer: [{ name: '__dsfigure_label_1' }] }), 'svg');
});

test('dynamic expressions can generate labels even when source rows are plain', () => {
	const axis = (labelExpr) => ({ encoding: { x: { axis: { labelExpr } } } });
	assert.equal(chartRenderer(axis("datum.value == 1 ? ['21.1'] : datum.value")), 'canvas');
	assert.equal(chartRenderer(axis("datum.value == 1 ? ['P = 0.01'] : datum.value")), 'svg');
	assert.equal(chartRenderer(axis("format(datum.value, '.1f') + '⁻¹'")), 'svg');
	assert.equal(chartRenderer(axis('datum.value + suffix')), 'svg');
	assert.equal(chartRenderer({ transform: [{ calculate: "'P = ' + datum.x", as: 'label' }],
		mark: 'text', encoding: { text: { field: 'label' } } }), 'svg');
	assert.equal(chartRenderer({ data: { values: [{ label: 'q__x' }] },
		mark: 'text', encoding: { text: { field: 'label' } } }), 'svg');
	assert.equal(chartRenderer({ data: { values: [{ label: 'control' }] },
		mark: 'text', encoding: { text: { field: 'label' } } }), 'canvas');
	assert.equal(chartRenderer({ datasets: { labels: [{ label: 'control' }] }, data: { name: 'labels' },
		mark: 'text', encoding: { text: { field: 'label' } } }), 'canvas');
	for (const data of [{ url: '/labels.json' }, { name: 'unresolved' }]) {
		assert.equal(chartRenderer({ data, mark: 'text', encoding: { text: { field: 'label' } } }), 'svg');
	}
	assert.equal(chartRenderer({ mark: 'text', encoding: { text: { field: 'label' } } }), 'svg');
	assert.equal(chartRenderer({ title: 'n = 12' }), 'svg');
	assert.equal(needsTextCorrections('P = 0.01'), true);
	assert.equal(needsTextCorrections('q__x = 10^3'), true);
	assert.equal(needsTextCorrections('model__alpha'), false);
});

test('unknown category labels use SVG for axes, legends and facet headers', () => {
	for (const data of [{ url: '/labels.json' }, { name: 'unresolved' }]) {
		for (const channel of ['x', 'y', 'color', 'shape', 'size', 'row', 'column']) {
			for (const type of ['nominal', 'ordinal', undefined]) {
				assert.equal(chartRenderer({ data, mark: 'point', encoding: {
					[channel]: { field: 'label', ...(type ? { type } : {}) },
				} }), 'svg', `${channel}:${type}`);
			}
		}
		assert.equal(chartRenderer({ data, facet: { field: 'label', type: 'nominal' },
			spec: { mark: 'point' } }), 'svg');
		assert.equal(chartRenderer({ data, layer: [{ mark: 'point', encoding: {
			color: { condition: { test: 'datum.keep', field: 'label', type: 'nominal' }, value: 'gray' },
		} }] }), 'svg');
		assert.equal(chartRenderer({ data, mark: 'point', encoding: {
			x: { field: 'x', type: 'quantitative' }, color: { field: 'y', type: 'quantitative' },
			tooltip: { field: 'label', type: 'nominal' },
		} }), 'canvas');
	}
	const encoding = { x: { field: 'label', type: 'nominal' }, color: { field: 'label', type: 'nominal' } };
	const values = [{ label: 'control' }];
	assert.equal(chartRenderer({ data: { values }, mark: 'point', encoding }), 'canvas');
	assert.equal(chartRenderer({ datasets: { labels: values }, data: { name: 'labels' },
		layer: [{ mark: 'point', encoding }] }), 'canvas');
	assert.equal(chartRenderer({ data: { values }, transform: [{ calculate: 'datum.label', as: 'label' }],
		mark: 'point', encoding }), 'svg');
});

test('registered renderer scales backing pixels and pointer mapping', () => {
	assert.ok(renderModule(CANVAS_RENDERER)?.renderer);
	assert.deepEqual(canvasGeometry(140, 80, 3.5, 2), {
		cssWidth: 490, cssHeight: 280, pixelWidth: 980, pixelHeight: 560, ratio: 7,
	});
	assert.deepEqual(chartPointer(360, 230, 10, 20, 3.5), { clientX: 110, clientY: 80 });
});

test('registered handler maps picks and event streams but keeps tooltip at screen pointer', () => {
	const canvas = { tagName: 'CANVAS', dataset: { dsZoom: '3.5' }, clientLeft: 0, clientTop: 0,
		getBoundingClientRect: () => ({ left: 10, top: 20 }), addEventListener() {} };
	let picked, tip, dispatched;
	const Handler = renderModule(CANVAS_RENDERER).handler;
	const handler = new Handler(null, (_h, event, _item, value) => {
		tip = [event.clientX, event.clientY, value];
	});
	handler.scene({}).initialize({ childNodes: [canvas] }, [0, 0]);
	handler.pick = (_scene, x, y) => {
		picked = [x, y];
		return { tooltip: 'hit' };
	};
	handler.on('pointermove', (event, item) => { dispatched = [event.clientX, event.clientY, item.tooltip]; });
	handler.pointermove({ clientX: 360, clientY: 230, preventDefault() {} });
	assert.deepEqual(picked, [100, 60]);
	assert.deepEqual(dispatched, [110, 80, 'hit']);
	assert.deepEqual(tip, [360, 230, 'hit']);
});

test('path-mark tooltip resolves in chart space and positions in screen space', () => {
	const canvas = { tagName: 'CANVAS', dataset: { dsZoom: '3.5' }, clientLeft: 0, clientTop: 0,
		getBoundingClientRect: () => ({ left: 10, top: 20 }), addEventListener() {} };
	const Handler = renderModule(CANVAS_RENDERER).handler;
	for (const kind of ['line', 'area', 'trail']) {
		let tip;
		const handler = new Handler(null, (_h, event, item, value) => {
			tip = { xy: [event.clientX, event.clientY], item, value };
		});
		handler.scene({}).initialize({ childNodes: [canvas] }, [0, 0]);
		const hit = { x: 100, y: 60, tooltip: `${kind} datum`, strokeWidth: 3, size: 3 };
		const other = { x: 200, y: 60, tooltip: 'wrong datum', strokeWidth: 3, size: 3 };
		const item = { tooltip: 'whole path', mark: { marktype: kind, items: [hit, other] } };
		handler.pick = () => item;
		handler.pointermove({ clientX: 360, clientY: 230, preventDefault() {} });
		assert.deepEqual(tip?.xy, [360, 230], kind);
		assert.equal(tip?.item, hit, kind);
		assert.equal(tip?.value, `${kind} datum`, kind);
	}
});

test('shared embed serializes updates, discards stale requests and finalizes navigation', async () => {
	const el = { isConnected: true, dataset: {}, replaceChildren() {} };
	const finalized = [];
	const embedded = [];
	let release;
	const blocked = new Promise((resolve) => { release = resolve; });
	const embed = async (_el, spec) => {
		embedded.push(spec.title);
		return { view: { resize() {} }, finalize: () => finalized.push(spec.title) };
	};
	const opts = { actions: false, embed };
	const old = embedChart(el, () => blocked, opts);
	const latest = embedChart(el, () => ({ title: 'latest' }), opts);
	release({ title: 'stale' });
	await Promise.all([old, latest]);
	assert.deepEqual(embedded, ['latest']);
	assert.ok(chartView(el));
	const next = embedChart(el, { title: 'next' }, opts); // Studio passes a resolved spec.
	await next;
	assert.deepEqual(finalized, ['latest']);
	clearChart(el);
	assert.deepEqual(finalized, ['latest', 'next']);
	assert.equal(chartView(el), undefined);
});

test('shared sizing is idempotent for SVG, Canvas and Studio width fitting', () => {
	globalThis.window = { devicePixelRatio: 2 };
	globalThis.getComputedStyle = () => ({ getPropertyValue: () => '3.5' });
	const attrs = {};
	const svg = { viewBox: { baseVal: { width: 120, height: 75 } }, setAttribute: (key, val) => { attrs[key] = val; } };
	const svgEl = { querySelector: (s) => s === 'svg' ? svg : null };
	scaleChart(svgEl);
	scaleChart(svgEl);
	assert.deepEqual(attrs, { width: '420', height: '262.5' });
	let redraws = 0;
	const view = { container: () => el, initialize: (node) => {
		assert.equal(node, el);
		return { runAsync: async () => { redraws++; } };
	} };
	const canvas = { dataset: { dsNaturalWidth: '120', dsNaturalHeight: '75', dsDpr: '2' },
		getBoundingClientRect: () => ({ width: 120 }) };
	const el = { dataset: {}, closest: () => null,
		querySelector: (s) => s === 'canvas.marks' ? canvas : null };
	assert.deepEqual(chartNaturalSize(el), { width: 120, height: 75 });
	scaleChart(el, 3.5, view);
	scaleChart(el, 3.5, view);
	assert.equal(redraws, 1);
	fitChartToWidth(el, 240, view);
	assert.equal(el.dataset.dsZoom, '2');
	assert.equal(redraws, 2);
	window.devicePixelRatio = 3;
	scaleChart(el, 2, view);
	assert.equal(redraws, 3);
	el.clientWidth = 248;
	scaleChart(el, 3.5, view);
	assert.equal(el.dataset.dsZoom, String(248 / 120));
	assert.equal(redraws, 4);
	assert.ok(Math.abs(canvasGeometry(120, 75, Number(el.dataset.dsZoom), 3).cssWidth - 248) < 1e-6);
	// A shrink-wrapped Vega embed must fit its stable parent, not its initial canvas.
	el.clientWidth = 158; // natural canvas + 38px action gutter
	el.closest = () => ({ parentElement: { clientWidth: 300 } });
	scaleChart(el, 3.5, view);
	assert.ok(Math.abs(Number(el.dataset.dsZoom) - 262 / 120) < 1e-6);
	assert.equal(redraws, 5);
	delete globalThis.window;
	delete globalThis.getComputedStyle;
});
