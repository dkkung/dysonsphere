import { loadExampleSource } from './exampleSource.ts';

// Each pane fetches once on first open, reuses its text on later opens, and retries failures.
export function wireCodeToggle(
	el: HTMLElement,
	base: string,
	loadSource: typeof loadExampleSource = loadExampleSource,
): void {
	if (el.dataset.wired) return;
	const btn = el.querySelector<HTMLButtonElement>('[data-role="toggle"]');
	const chartPane = el.querySelector<HTMLElement>('[data-pane="chart"]');
	const codePane = el.querySelector<HTMLElement>('[data-pane="code"]');
	const status = el.querySelector<HTMLElement>('[data-role="source-status"]');
	const retry = el.querySelector<HTMLButtonElement>('[data-role="source-retry"]');
	const sourceCode = el.querySelector<HTMLElement>('[data-role="source-code"]');
	if (!btn || !chartPane || !codePane || !status || !retry || !sourceCode) return;
	el.dataset.wired = '1';
	let loading: Promise<void> | null = null;
	let loaded = false;
	function load() {
		if (loaded || loading) return;
		status!.textContent = 'Loading code…';
		retry!.hidden = true;
		loading = loadSource(el.dataset.example!, base)
			.then((source) => {
				sourceCode!.textContent = source;
				status!.textContent = '';
				loaded = true;
			})
			.catch(() => {
				status!.textContent = 'Could not load code.';
				retry!.hidden = false;
			})
			.finally(() => { loading = null; });
	}
	retry.addEventListener('click', load);
	btn.addEventListener('click', () => {
		const showCode = codePane.hidden;
		codePane.hidden = !showCode;
		chartPane.hidden = showCode;
		btn.setAttribute('aria-pressed', String(showCode));
		btn.querySelector<HTMLElement>('[data-when="chart"]')!.hidden = showCode;
		btn.querySelector<HTMLElement>('[data-when="code"]')!.hidden = !showCode;
		if (showCode) load();
	});
}
