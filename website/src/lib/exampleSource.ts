// The same URL works in local development and under the GitHub Pages project base.
export function exampleSourceUrl(name: string, base: string): string {
	if (!/^[a-z0-9_]+$/.test(name)) throw new Error('Invalid example name');
	return `${base}example-source/${name}.py`;
}

export async function loadExampleSource(
	name: string,
	base: string,
	fetchSource: typeof fetch = fetch,
): Promise<string> {
	const response = await fetchSource(exampleSourceUrl(name, base));
	if (!response.ok) throw new Error(`Could not load example source (${response.status})`);
	return response.text();
}

// Preserve the existing base64 UTF-8 Studio links alongside #example= links.
export function codeFromHash(hash: string): string | null {
	const match = hash.match(/#code=([^&]+)/);
	if (!match) return null;
	try {
		const bytes = Uint8Array.from(atob(decodeURIComponent(match[1])), (c) => c.charCodeAt(0));
		return new TextDecoder().decode(bytes);
	} catch {
		return null;
	}
}

export function exampleFromHash(hash: string): string | null {
	const match = hash.match(/^#example=([^&]+)$/);
	if (!match) return null;
	try {
		const name = decodeURIComponent(match[1]);
		return /^[a-z0-9_]+$/.test(name) ? name : null;
	} catch {
		return null;
	}
}
