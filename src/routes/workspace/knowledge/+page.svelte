<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';

	import { listNotebooks } from '$lib/apis/opennotebook';
	import Badge from '$lib/components/workspace/common/Badge.svelte';
	import ConfirmDialog from '$lib/components/workspace/common/ConfirmDialog.svelte';
	import ItemMenu from '$lib/components/workspace/common/ItemMenu.svelte';
	import WorkspaceShell from '$lib/components/workspace/WorkspaceShell.svelte';
	import {
		deleteKnowledge,
		downloadJson,
		filterByView,
		listKnowledge,
		matchQuery,
		relativeTime,
		type WorkspaceKnowledge,
		type WorkspaceView
	} from '$lib/data/workspaceResources';

	type KnowledgeCard = WorkspaceKnowledge & { localId?: string; notebookOnly?: boolean };

	let query = $state('');
	let viewOption = $state<WorkspaceView>(
		(typeof localStorage !== 'undefined'
			? (localStorage.workspaceViewOption as WorkspaceView)
			: '') || ''
	);
	let loading = $state(true);
	let items = $state<KnowledgeCard[]>([]);
	let confirmShow = $state(false);
	let pendingDeleteId = $state<string | null>(null);

	const withParams = (path: string) => {
		const params = new URLSearchParams();
		const model = $page.url.searchParams.get('model');
		const chat = $page.url.searchParams.get('chat');
		if (model) params.set('model', model);
		if (chat) params.set('chat', chat);
		const search = params.toString();
		return search ? `${path}?${search}` : path;
	};

	const filtered = $derived(
		filterByView(items, viewOption).filter((k) =>
			matchQuery(`${k.name} ${k.description ?? ''}`, query)
		)
	);

	const loadAll = async () => {
		const local = listKnowledge().map((k) => ({ ...k, localId: k.id, notebookOnly: false }));
		const linkedNotebookIds = new Set(
			local.map((k) => k.notebookId).filter((id): id is string => Boolean(id))
		);
		try {
			const notebooks = await listNotebooks();
			const extras: KnowledgeCard[] = notebooks
				.filter((nb) => !linkedNotebookIds.has(nb.id))
				.map((nb) => ({
					id: `nb-${nb.id}`,
					name: nb.name,
					description: nb.description || '',
					notebookId: nb.id,
					docs: [],
					writeAccess: true,
					owner: 'you' as const,
					createdAt: Date.now(),
					updatedAt: Date.now(),
					notebookOnly: true
				}));
			items = [...local, ...extras].sort((a, b) => b.updatedAt - a.updatedAt);
		} catch {
			items = local;
		}
	};

	const openItem = (item: KnowledgeCard) => {
		if (item.notebookOnly && item.notebookId && !item.localId) {
			const params = new URLSearchParams($page.url.searchParams);
			params.set('notebook', item.notebookId);
			params.set('from', 'workspace');
			void goto(`/notebook?${params.toString()}`);
			return;
		}
		void goto(withParams(`/workspace/knowledge/${encodeURIComponent(item.id)}`));
	};

	onMount(() => {
		void loadAll().finally(() => {
			loading = false;
		});
	});
</script>

<WorkspaceShell
	title="知识库"
	count={loading ? null : filtered.length}
	searchPlaceholder="搜索知识库"
	bind:query
	bind:viewOption
	primaryHref={withParams('/workspace/knowledge/create')}
	primaryLabel="创建知识库"
	showEmpty={!loading && filtered.length === 0}
	emptyTitle="未找到任何知识库"
>
	{#if loading}
		<div class="flex items-center justify-center py-16 text-sm text-gray-500">加载中…</div>
	{:else}
		<div class="grid grid-cols-1 gap-2 p-3 sm:grid-cols-2">
			{#each filtered as item (item.id)}
				<!-- svelte-ignore a11y_click_events_have_key_events -->
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div
					class="group relative cursor-pointer rounded-2xl border border-gray-800/80 bg-gray-850/40 p-4 transition hover:bg-gray-850"
					onclick={() => openItem(item)}
				>
					<div class="mb-2 flex items-start justify-between gap-2">
						<Badge content="集合" type="success" />
						{#if !item.notebookOnly}
							<div onclick={(e) => e.stopPropagation()}>
								<ItemMenu
									items={[
										{
											label: '导出',
											onClick: () => downloadJson(`${item.id}.json`, item)
										},
										{
											label: '删除',
											danger: true,
											onClick: () => {
												pendingDeleteId = item.id;
												confirmShow = true;
											}
										}
									]}
								/>
							</div>
						{/if}
					</div>
					<div class="truncate text-sm font-medium text-white">{item.name}</div>
					{#if item.description}
						<div class="mt-1 line-clamp-2 text-xs text-gray-500">{item.description}</div>
					{/if}
					<div class="mt-3 text-[11px] text-gray-600">
						{relativeTime(item.updatedAt)}
						{#if item.notebookOnly}
							· OpenNoteBook
						{/if}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</WorkspaceShell>

<ConfirmDialog
	bind:show={confirmShow}
	title="删除知识库？"
	message="此操作无法撤销。"
	onConfirm={() => {
		if (pendingDeleteId) {
			deleteKnowledge(pendingDeleteId);
			pendingDeleteId = null;
			void loadAll();
		}
	}}
/>
