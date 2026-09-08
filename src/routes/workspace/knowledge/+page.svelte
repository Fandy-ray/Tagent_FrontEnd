<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';

	import { listNotebooks, type NotebookSummary } from '$lib/apis/opennotebook';
	import WorkspacePanel from '$lib/components/workspace/WorkspacePanel.svelte';

	let query = $state('');
	let loading = $state(true);
	let notebooks = $state<NotebookSummary[]>([]);
	let error = $state('');

	const filtered = $derived(
		query.trim()
			? notebooks.filter((item) => item.name.toLowerCase().includes(query.trim().toLowerCase()))
			: notebooks
	);

	const openNotebook = (id?: string) => {
		const params = new URLSearchParams($page.url.searchParams);
		params.set('from', 'workspace');
		if (id) {
			params.set('notebook', id);
			params.set('collection', id);
		}
		void goto(`/notebook?${params.toString()}`);
	};

	onMount(() => {
		void listNotebooks()
			.then((items) => {
				notebooks = items;
			})
			.catch(() => {
				error = '读不到 OpenNoteBook 笔记本列表，请确认服务已启动。';
				notebooks = [];
			})
			.finally(() => {
				loading = false;
			});
	});
</script>

<WorkspacePanel
	title="知识库"
	count={loading ? null : filtered.length}
	searchPlaceholder="搜索知识库"
	bind:query
	primaryAction="创建知识库"
	emptyTitle="未找到任何知识库"
	emptyHint="请先启动 OpenNoteBook，或调整搜索词后再试。"
	onPrimary={() => openNotebook()}
>
	{#if loading}
		<div class="flex items-center justify-center py-16 text-sm text-gray-500">加载中…</div>
	{:else if filtered.length > 0}
		<div class="divide-y divide-white/[0.04]">
			{#each filtered as notebook (notebook.id)}
				<button
					type="button"
					class="flex w-full items-center justify-between px-4 py-3 text-left transition hover:bg-white/[0.03]"
					onclick={() => openNotebook(notebook.id)}
				>
					<div class="min-w-0">
						<div class="truncate text-sm font-medium text-white">{notebook.name}</div>
						<div class="truncate text-xs text-gray-500">
							{notebook.note_count ?? 0} 条笔记 · 点击进入 OpenNoteBook
						</div>
					</div>
				</button>
			{/each}
		</div>
	{:else}
		<div class="flex flex-col items-center justify-center px-6 py-20 text-center">
			<div class="mb-3 text-3xl">😕</div>
			<div class="mb-1 text-lg font-medium text-white">未找到任何知识库</div>
			<div class="max-w-md text-xs text-gray-500">
				{error || '请先启动 OpenNoteBook，或调整搜索词后再试。'}
			</div>
		</div>
	{/if}
</WorkspacePanel>
