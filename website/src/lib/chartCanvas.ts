import * as vega from 'vega';

// Vega exports these classes and methods at runtime; its current declarations omit most
// renderer/handler methods and the CanvasRenderer export. Describe only the hooks used here.
type Bounds = { left: number; top: number; width: number; height: number };
const RendererBase = (vega as unknown as { CanvasRenderer: new (...args: any[]) => {
	resize(width: number, height: number, origin: readonly number[], scaleFactor?: number): void;
	canvas(): HTMLCanvasElement | null;
	context(): CanvasRenderingContext2D;
	element(): Element | null;
} }).CanvasRenderer;
const HandlerBase = vega.CanvasHandler as unknown as new (...args: any[]) => {
	canvas(): HTMLCanvasElement;
	pickEvent(event: Event): unknown;
	fire(type: string, event: Event, touch?: boolean): void;
	handleTooltip(event: Event, item: unknown, show: boolean): void;
	getItemBoundingClientRect(item: unknown): Bounds | undefined;
};

// Vega's DOM Canvas renderer fixes its bitmap at natural chart size × DPR. The documented
// renderer registry and subclass hooks let us draw at site zoom × DPR without rescaling the
// bitmap in CSS. Keep the chart's coordinate system unchanged for Vega's native interactions.
export const CANVAS_RENDERER = 'ds-canvas';

function zoomFor(el: Element | null): number {
	const value = Number(el?.closest('[data-ds-zoom]')?.getAttribute('data-ds-zoom'));
	return value > 0 ? value : 1;
}

export function canvasGeometry(width: number, height: number, zoom: number, dpr: number) {
	const ratio = zoom * dpr;
	return { cssWidth: width * zoom, cssHeight: height * zoom,
		pixelWidth: Math.round(width * ratio), pixelHeight: Math.round(height * ratio), ratio };
}

class SiteCanvasRenderer extends RendererBase {
	resize(width: number, height: number, origin: readonly number[], scaleFactor?: number): this {
		super.resize(width, height, origin, scaleFactor);
		const canvas = this.canvas() as HTMLCanvasElement | null;
		if (!canvas || !canvas.parentNode) return this;
		const zoom = zoomFor(this.element());
		const dpr = window.devicePixelRatio || 1;
		const size = canvasGeometry(width, height, zoom, dpr);
		canvas.width = size.pixelWidth;
		canvas.height = size.pixelHeight;
		canvas.style.width = `${size.cssWidth}px`;
		canvas.style.height = `${size.cssHeight}px`;
		canvas.style.maxWidth = 'none'; // fit is computed before drawing, never by CSS stretching
		canvas.dataset.dsNaturalWidth = String(width);
		canvas.dataset.dsNaturalHeight = String(height);
		canvas.dataset.dsDpr = String(dpr);
		canvas.dataset.dsZoom = String(zoom);
		const ctx = this.context() as CanvasRenderingContext2D & { pixelRatio: number };
		ctx.pixelRatio = size.ratio; // Vega's Canvas mark/picking code reads this context value.
		ctx.setTransform(size.ratio, 0, 0, size.ratio,
			size.ratio * origin[0], size.ratio * origin[1]);
		return this;
	}
}

// Native hit testing reads pointer positions in chart coordinates. Normalize the screen
// position before it reaches Vega, and return scaled bounds for the tooltip anchor.
export function chartPointer(clientX: number, clientY: number, left: number, top: number, zoom: number) {
	return { clientX: left + (clientX - left) / zoom, clientY: top + (clientY - top) / zoom };
}

class SiteCanvasHandler extends HandlerBase {
	private originals: WeakMap<object, Event>;

	constructor(loader: unknown, tooltip?: (handler: unknown, event: Event, item: unknown, value: unknown) => void) {
		const originals = new WeakMap<object, Event>();
		super(loader, tooltip && function (this: unknown, handler: unknown, event: Event, item: unknown, value: unknown) {
			// Vega resolves path-mark items using chart coordinates, but tooltip placement
			// needs the original screen event. Restore it only at the callback boundary.
			return tooltip.call(this, handler, originals.get(event) ?? event, item, value);
		});
		this.originals = originals;
	}

	private normalize<T extends Event>(event: T): T {
		const canvas = this.canvas() as HTMLCanvasElement;
		const rect = canvas.getBoundingClientRect();
		const zoom = Number(canvas.dataset.dsZoom) || 1;
		const point = (value: MouseEvent) => chartPointer(value.clientX, value.clientY, rect.left, rect.top, zoom);
		const pointer = event as MouseEvent;
		const xy = point(pointer);
		// Proxy native accessors with the original as receiver; native DOM methods must also
		// stay bound to the real event. Vega adds vegaType/item/vega to this same object.
		const normalized = new Proxy(event, {
			get(target, prop) {
				if (prop === 'clientX') return xy.clientX;
				if (prop === 'clientY') return xy.clientY;
				if (prop === 'changedTouches') {
					const touches = (target as TouchEvent).changedTouches;
					return touches && Array.from(touches, (touch) => {
						const coords = point(touch as unknown as MouseEvent);
						return new Proxy(touch, { get(t, key) {
							if (key === 'clientX') return coords.clientX;
							if (key === 'clientY') return coords.clientY;
							return Reflect.get(t, key, t);
						} });
					});
				}
				const value = Reflect.get(target, prop, target);
				return typeof value === 'function' ? value.bind(target) : value;
			},
			set(target, prop, value) { return Reflect.set(target, prop, value, target); },
		}) as T;
		this.originals.set(normalized, event);
		return normalized;
	}

	pickEvent(event: MouseEvent) {
		return super.pickEvent(this.normalize(event));
	}

	fire(type: string, event: MouseEvent, touch?: boolean) {
		// Vega event streams use event.vega.x/y as well as mark picking; both need chart
		// coordinates. The tooltip callback separately receives the original screen event.
		return super.fire(type, this.normalize(event), touch);
	}

	handleTooltip(event: MouseEvent, item: unknown, show: boolean) {
		return super.handleTooltip(event, item, show);
	}

	getItemBoundingClientRect(item: unknown) {
		const bounds = super.getItemBoundingClientRect(item);
		if (!bounds) return bounds;
		const canvas = this.canvas() as HTMLCanvasElement;
		const rect = canvas.getBoundingClientRect();
		const zoom = Number(canvas.dataset.dsZoom) || 1;
		const left = rect.left + (bounds.left - rect.left) * zoom;
		const top = rect.top + (bounds.top - rect.top) * zoom;
		const width = bounds.width * zoom, height = bounds.height * zoom;
		return { x: left, y: top, left, top, width, height, right: left + width, bottom: top + height };
	}
}

vega.renderModule(CANVAS_RENDERER, {
	renderer: SiteCanvasRenderer,
	headless: RendererBase,
	handler: SiteCanvasHandler,
} as unknown as Parameters<typeof vega.renderModule>[1]);
