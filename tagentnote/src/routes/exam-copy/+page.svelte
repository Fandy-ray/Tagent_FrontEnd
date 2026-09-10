<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';

	onMount(() => {
		void goto(`/exam${$page.url.search}`, { replaceState: true });
	});
</script>

<div class="flex min-h-screen items-center justify-center bg-gray-950 text-gray-300">
	正在进入测评…
</div>
