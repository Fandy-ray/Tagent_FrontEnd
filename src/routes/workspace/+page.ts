import { redirect } from '@sveltejs/kit';

export function load({ url }: { url: URL }) {
	const search = url.searchParams.toString();
	throw redirect(302, search ? `/workspace/models?${search}` : '/workspace/models');
}
