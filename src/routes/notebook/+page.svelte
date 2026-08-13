<script lang="ts">
	import { goto } from '$app/navigation';
        import { page } from '$app/stores';
	import { env } from '$env/dynamic/public';

	const openNotebookUrl =
		env.PUBLIC_OPENNOTEBOOK_URL || 'http://localhost:8502/notebooks';

	let iframeKey = 0;

const returnPath = $derived(
	$page.url.searchParams.get('from') === 'qa'
		? `/qa?model=${encodeURIComponent(
				$page.url.searchParams.get('model') ?? 'deepseek'
			)}`
		: '/agent-select'
);

	const refreshIframe = () => {
		iframeKey += 1;
	};

	const returnToSource = () => {
	void goto(returnPath);
};
</script>

<svelte:head>
	<title>OpenNoteBook | TAgent</title>
</svelte:head>

<main class="relative h-screen w-screen overflow-hidden bg-[#080b0f]">
	{#key iframeKey}
		<iframe
			title="OpenNoteBook 知识工作空间"
			src={openNotebookUrl}
			class="block h-full w-full border-0 bg-white"
			allow="clipboard-read; clipboard-write"
		></iframe>
	{/key}

	<div
		class="fixed bottom-5 right-5 z-50 flex items-center overflow-hidden rounded-xl border border-white/15 bg-[#11161d]/95 shadow-2xl shadow-black/50 backdrop-blur-xl"
	>
		<button
			type="button"
			class="flex h-11 items-center gap-2 border-r border-white/10 px-4 text-sm text-gray-300 transition hover:bg-white/10 hover:text-white focus:outline-none focus-visible:bg-white/10"
			onclick={returnToSource}
			title="返回"
		>
			<svg
				class="size-4"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				<path d="m15 18-6-6 6-6"></path>
			</svg>

			<span>返回</span>
		</button>

		<button
			type="button"
			class="flex h-11 items-center gap-2 border-r border-white/10 px-4 text-sm text-gray-300 transition hover:bg-white/10 hover:text-white focus:outline-none focus-visible:bg-white/10"
			onclick={refreshIframe}
			title="刷新 OpenNoteBook"
		>
			<svg
				class="size-4"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				<path d="M20 11a8.1 8.1 0 0 0-15.5-2M4 4v5h5"></path>
				<path d="M4 13a8.1 8.1 0 0 0 15.5 2M20 20v-5h-5"></path>
			</svg>

			<span>刷新</span>
		</button>

		<a
			href={openNotebookUrl}
			target="_blank"
			rel="noreferrer"
			class="flex h-11 items-center gap-2 px-4 text-sm text-cyan-300 transition hover:bg-cyan-400/10 hover:text-cyan-200 focus:outline-none focus-visible:bg-cyan-400/10"
			title="在新页面中打开 OpenNoteBook"
		>
			<svg
				class="size-4"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				<path d="M15 3h6v6"></path>
				<path d="M10 14 21 3"></path>
				<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
			</svg>

			<span>新页面打开</span>
		</a>
	</div>
</main>