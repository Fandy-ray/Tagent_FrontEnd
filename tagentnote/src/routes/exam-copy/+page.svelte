<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';

	onMount(() => {
		void goto(resolve(`/exam?${$page.url.search.replace(/^\?/, '')}`), { replaceState: true });
	});
</script>

<div class="flex min-h-screen items-center justify-center bg-gray-950 text-gray-300">
	正在进入测评…
</div>
