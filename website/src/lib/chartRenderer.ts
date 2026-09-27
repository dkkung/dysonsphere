import { needsTextCorrections } from './fixSuperscripts.ts';

type RecordValue = Record<string, unknown>;
const record = (value: unknown): value is RecordValue => value !== null && typeof value === 'object' && !Array.isArray(value);

const labelChannels = new Set([
	'x', 'y', 'color', 'fill', 'stroke', 'size', 'shape', 'opacity', 'fillOpacity',
	'strokeOpacity', 'strokeWidth', 'strokeDash', 'row', 'column', 'facet', 'text',
]);

function discreteField(value: unknown, inheritedType?: unknown): boolean {
	if (Array.isArray(value)) return value.some(item => discreteField(item, inheritedType));
	if (!record(value)) return false;
	const type = value.type ?? inheritedType;
	return ('field' in value && type !== 'quantitative' && type !== 'temporal') ||
		discreteField(value.condition, type);
}

// A labelExpr can synthesize text at render time. Only certify number-to-number ternary maps
// (including Rao's array-wrapped numeric labels); everything else stays on SVG.
function numericLabelExpr(expr: string): boolean {
	const replaced = expr.replace(/(['"])(?:\d+(?:\.\d+)?|\.\d+)\1/g, '0').replace(/\bdatum\.value\b/g, '0');
	return !/[A-Za-z_'"`]/.test(replaced) && /^[\d\s.?:=<>!+\-*/()[\],]+$/.test(replaced);
}

/** Choose SVG only when an SVG-only correction might affect this spec. */
export function chartRenderer(spec: unknown, inward = false): 'svg' | 'canvas' {
	if (!record(spec)) return 'svg';
	if (inward || record(spec.usermeta) && record(spec.usermeta.dysonsphere) &&
		record(spec.usermeta.dysonsphere.theme) && spec.usermeta.dysonsphere.theme.tickDirection === 'in') return 'svg';
	const config = record(spec.config) ? spec.config : {};
	const axis = record(config.axis) ? config.axis : {};
	if (Number(axis.offset ?? 0) !== 0) return 'svg';

	let fallback = false;
	const datasets = record(spec.datasets) ? spec.datasets : {};
	const inlineData = (data: unknown): boolean => record(data) &&
		(Array.isArray(data.values) || typeof data.name === 'string' && Array.isArray(datasets[data.name]));
	const visit = (value: unknown, transforms = false, source: unknown = undefined): void => {
		if (fallback || !value || typeof value !== 'object') return;
		if (Array.isArray(value)) {
			for (const item of value) visit(item, transforms, source);
			return;
		}
		const node = value as RecordValue;
		if (typeof node.name === 'string' && node.name.startsWith('__dsfigure_label_')) fallback = true;
		const nextTransforms = transforms || Array.isArray(node.transform);
		const nextSource = 'data' in node ? node.data : source;
		const unknownLabels = nextTransforms || !inlineData(nextSource);
		// Axis, legend and facet labels can come from fields just like text marks.
		if (unknownLabels && (record(node.facet) || record(node.encoding) &&
			Object.entries(node.encoding).some(([channel, encoding]) =>
				labelChannels.has(channel) && discreteField(encoding)))) fallback = true;
		const mark = record(node.mark) ? node.mark.type : node.mark;
		if (mark === 'text') {
			const text = record(node.encoding) ? node.encoding.text : undefined;
			// Generated or external fields may contain unseen scripts/statistics. Inline rows
			// (including named datasets) are inspected by the text detector below.
			if (record(text) && typeof text.field === 'string' &&
				unknownLabels) fallback = true;
		}
		for (const [key, item] of Object.entries(node)) {
			if (key === 'usermeta' || key === 'description' || key === '$schema') continue;
			if (key === 'labelExpr' && typeof item === 'string') {
				if (!numericLabelExpr(item)) fallback = true;
			} else if (typeof item === 'string') {
				if (needsTextCorrections(item)) fallback = true;
			} else {
				visit(item, nextTransforms, nextSource);
			}
		}
	};
	visit(spec);
	return fallback ? 'svg' : 'canvas';
}
