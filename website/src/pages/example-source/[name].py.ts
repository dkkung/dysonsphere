import type { APIRoute, GetStaticPaths } from 'astro';

// Build plain-text assets from the same registry used by Example.astro and gen_examples.py.
const sources = import.meta.glob('../../../examples/*.py', {
	query: '?raw',
	import: 'default',
	eager: true,
}) as Record<string, string>;

export const getStaticPaths: GetStaticPaths = () =>
	Object.entries(sources).map(([path, source]) => ({
		params: { name: path.split('/').pop()!.slice(0, -3) },
		props: { source },
	}));

export const GET: APIRoute = ({ props }) =>
	new Response(props.source as string, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
