import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { codeFromHash, exampleFromHash, exampleSourceUrl, loadExampleSource } from './exampleSource.ts';
import { wireCodeToggle } from './codeToggle.ts';

const website = resolve(dirname(fileURLToPath(import.meta.url)), '../..');

test('source URL and new/legacy Studio links work under both bases', async () => {
	for (const base of ['/', '/dysonsphere/']) {
		assert.equal(exampleSourceUrl('rao_hic', base), `${base}example-source/rao_hic.py`);
		let requested;
		const code = await loadExampleSource('rao_hic', base, async (url) => {
			requested = url;
			return { ok: true, text: async () => 'φ\n' };
		});
		assert.equal(requested, `${base}example-source/rao_hic.py`);
		assert.equal(code, 'φ\n');
	}
	assert.equal(exampleFromHash('#example=rao_hic'), 'rao_hic');
	assert.equal(exampleFromHash('#example=rao_hic&x=y'), null);
	assert.equal(exampleFromHash('#example=..%2Fsecret'), null);
	assert.throws(() => exampleSourceUrl('../secret', '/'), /Invalid example/);
	const encoded = encodeURIComponent(Buffer.from('chart = "μ"\n').toString('base64'));
	assert.equal(codeFromHash(`#code=${encoded}`), 'chart = "μ"\n');
	assert.equal(codeFromHash('#code=!!!'), null);
});

test('failed fetch reports status and a later request can retry', async () => {
	await assert.rejects(loadExampleSource('rao_hic', '/', async () => ({ ok: false, status: 503 })), /503/);
	assert.equal(await loadExampleSource('rao_hic', '/', async () => ({ ok: true, text: async () => 'complete' })), 'complete');
});

function element(hidden = false) {
	return {
		hidden, textContent: '', dataset: {}, attributes: {}, listeners: {}, children: {},
		querySelector(selector) { return this.children[selector]; },
		addEventListener(event, fn) { this.listeners[event] = fn; },
		click() { this.listeners.click?.(); },
		setAttribute(name, value) { this.attributes[name] = value; },
	};
}
function pane() {
	const root = element();
	root.dataset.example = 'rao_hic';
	const btn = element();
	btn.children['[data-when="chart"]'] = element();
	btn.children['[data-when="code"]'] = element(true);
	root.children = {
		'[data-role="toggle"]': btn,
		'[data-pane="chart"]': element(),
		'[data-pane="code"]': element(true),
		'[data-role="source-status"]': element(),
		'[data-role="source-retry"]': element(true),
		'[data-role="source-code"]': element(),
	};
	return root;
}
const settle = () => new Promise((resolve) => setImmediate(resolve));

test('toggle fetches on click, reuses text, handles in-flight navigation and retry', async () => {
	const root = pane();
	const btn = root.children['[data-role="toggle"]'];
	const retry = root.children['[data-role="source-retry"]'];
	const status = root.children['[data-role="source-status"]'];
	const code = root.children['[data-role="source-code"]'];
	let attempts = 0;
	let finish;
	const load = () => {
		attempts++;
		if (attempts === 1) return new Promise((resolve, reject) => { finish = () => reject(new Error('offline')); });
		return Promise.resolve('all source\n');
	};
	wireCodeToggle(root, '/', load);
	wireCodeToggle(root, '/', load);
	assert.equal(attempts, 0);
	btn.click();
	assert.equal(attempts, 1);
	assert.equal(status.textContent, 'Loading code…');
	btn.click(); // Hide while pending; no second request or forced re-open.
	btn.click();
	assert.equal(attempts, 1);
	finish();
	await settle();
	assert.equal(root.children['[data-pane="code"]'].hidden, false);
	assert.equal(status.textContent, 'Could not load code.');
	assert.equal(retry.hidden, false);
	retry.click();
	await settle();
	assert.equal(attempts, 2);
	assert.equal(code.textContent, 'all source\n');
	assert.equal(retry.hidden, true);
	btn.click();
	btn.click();
	assert.equal(attempts, 2);
	assert.equal(btn.attributes['aria-pressed'], 'true');
});

test('static source loads byte-for-byte at root and project base', async () => {
	const source = await readFile(resolve(website, 'examples/rao_hic.py'), 'utf8');
	for (const base of ['/', '/dysonsphere/']) {
		const fetched = await loadExampleSource('rao_hic', base, async (url) => {
			assert.equal(url, `${base}example-source/rao_hic.py`);
			return { ok: true, text: () => readFile(resolve(website, 'dist/example-source/rao_hic.py'), 'utf8') };
		});
		assert.equal(fetched, source);
	}
});

test('built assets contain exact source while gallery HTML omits source and base64 links', async () => {
	const names = (await readdir(resolve(website, 'examples'))).filter((name) => name.endsWith('.py'));
	assert.ok(names.includes('rao_hic.py') && names.includes('tabula_muris_pancreas.py'));
	for (const name of names) {
		const source = await readFile(resolve(website, `examples/${name}`));
		const asset = await readFile(resolve(website, `dist/example-source/${name}`));
		assert.deepEqual(asset, source, name);
	}
	const html = await readFile(resolve(website, 'dist/gallery/landmarks/index.html'), 'utf8');
	assert.match(html, /#example=rao_hic/);
	assert.doesNotMatch(html, /#code=/);
	assert.doesNotMatch(html, /import altair as alt/);
	assert.ok(Buffer.byteLength(html) < 100_000);
	assert.doesNotMatch(html, /class="expressive-code"/);
	const guide = await readFile(resolve(website, 'dist/guides/getting-started/index.html'), 'utf8');
	assert.match(guide, /data-language="python"/); // Visible examples keep highlighted code.
});
