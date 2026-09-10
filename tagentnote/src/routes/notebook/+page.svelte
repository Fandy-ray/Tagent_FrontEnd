<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { env } from '$env/dynamic/public';
	import { onMount } from 'svelte';

	import { listNotebookKnowledge } from '$lib/apis/opennotebook';
	import { findCollection, type KnowledgeCollection } from '$lib/data/knowledge';

	const DEFAULT_NOTEBOOK_URL = 'http://localhost:8502/notebooks';

	const normalizeNotebookUrl = (raw: string) => {
		const trimmed = raw.trim().replace(/\/$/, '');

		if (trimmed === 'http://localhost:8502' || trimmed === 'https://localhost:8502') {
			return `${trimmed}/notebooks`;
		}

		return raw.trim() || DEFAULT_NOTEBOOK_URL;
	};

	const openNotebookUrl = normalizeNotebookUrl(
		env.PUBLIC_OPENNOTEBOOK_URL || DEFAULT_NOTEBOOK_URL
	);

	let iframeKey = $state(0);
	let status = $state<'checking' | 'ready' | 'offline'>('checking');

	// 深链里只带 id，名字要回 OpenNoteBook 取，本地不存任何副本。
	let collections = $state<KnowledgeCollection[]>([]);

	const sourceFile = $derived($page.url.searchParams.get('file'));
	const sourceCollection = $derived(
		findCollection($page.url.searchParams.get('collection') ?? '', collections)
	);
	const sourceFileTitle = $derived(
		sourceCollection?.files.find((file) => file.id === sourceFile)?.title ??
			sourceFile
	);

	const returnPath = $derived(
		$page.url.searchParams.get('from') === 'qa'
			? `/qa?model=${encodeURIComponent($page.url.searchParams.get('model') ?? '')}`
			: $page.url.searchParams.get('from') === 'exam'
				? `/exam?model=${encodeURIComponent($page.url.searchParams.get('model') ?? '')}`
				: '/agent-select'
	);

	const checkNotebook = async () => {
		status = 'checking';

		try {
			const controller = new AbortController();
			const timer = window.setTimeout(() => controller.abort(), 2500);
			const origin = new URL(openNotebookUrl, window.location.origin).origin;
			await fetch(origin, { mode: 'no-cors', signal: controller.signal });
			window.clearTimeout(timer);
			status = 'ready';
		} catch {
			status = 'offline';
		}
	};

	const refreshIframe = () => {
		iframeKey += 1;
		void checkNotebook();
	};

	const returnToSource = () => {
		void goto(returnPath);
	};

	onMount(() => {
		void checkNotebook();
		void listNotebookKnowledge()
			.then((items) => {
				collections = items;
			})
			.catch(() => {
				collections = [];
			});
	});
</script>

<svelte:head>
	<title>知识笔记本 | TAgent</title>
</svelte:head>

<main class="relative h-screen w-screen overflow-hidden bg-[#080b0f]">
	{#key iframeKey}
		<iframe
			title="OpenNoteBook 知识工作空间"
			src={openNotebookUrl}
			class="block h-full w-full border-0 bg-[#171717]"
			allow="clipboard-read; clipboard-write"
		></iframe>
	{/key}

	{#if sourceCollection}
		<div
			class="absolute top-4 left-1/2 z-40 w-[min(92vw,36rem)] -translate-x-1/2 rounded-xl border border-cyan-400/20 bg-[#11161d]/95 px-4 py-3 text-sm text-gray-200 backdrop-blur"
		>
			{#if sourceFileTitle}
				请在笔记本
				<span class="text-cyan-300">{sourceCollection.name}</span>
				中打开：
				<span class="font-medium text-white">{sourceFileTitle}</span>
			{:else}
				本次答疑检索的是笔记本
				<span class="text-cyan-300">{sourceCollection.name}</span>
			{/if}
		</div>
	{/if}

	{#if status !== 'ready'}
		<div class="absolute inset-0 z-40 flex items-center justify-center bg-[#080b0f]/92 px-6">
			<div class="w-full max-w-lg rounded-2xl border border-white/10 bg-[#11161d] p-6 text-gray-200">
				<p class="text-xs font-medium uppercase tracking-[0.18em] text-cyan-400">
					笔记本
				</p>
				<h1 class="mt-2 text-xl font-semibold text-white">
					{status === 'checking' ? '正在连接 OpenNoteBook…' : '未检测到 OpenNoteBook'}
				</h1>
				<p class="mt-3 text-sm leading-6 text-gray-400">
					笔记本页通过 iframe 嵌入外部服务，默认地址为
					<code class="text-cyan-200">{openNotebookUrl}</code>。
					请先启动 OpenNoteBook，再刷新本页。
				</p>
				<p class="mt-2 text-sm leading-6 text-gray-500">
					本地部署见
					<a
						class="text-cyan-300 underline underline-offset-2"
						href="https://gitee.com/kevin-zhengscuter/fixed_open_notebook"
						target="_blank"
						rel="noreferrer">fixed_open_notebook</a
					>。
				</p>
				<div class="mt-5 flex flex-wrap gap-3">
					<button
						type="button"
						class="rounded-xl bg-white px-4 py-2 text-sm font-medium text-gray-900 transition hover:bg-gray-200"
						onclick={refreshIframe}
					>
						重新检测
					</button>
					<button
						type="button"
						class="rounded-xl border border-white/15 px-4 py-2 text-sm text-gray-300 transition hover:bg-white/10"
						onclick={returnToSource}
					>
						返回
					</button>
				</div>
			</div>
		</div>
	{/if}

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
