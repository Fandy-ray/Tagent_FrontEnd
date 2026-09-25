<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';

	import ConfirmDialog from '$lib/components/workspace/common/ConfirmDialog.svelte';
	import ItemMenu from '$lib/components/workspace/common/ItemMenu.svelte';
	import WorkspaceShell from '$lib/components/workspace/WorkspaceShell.svelte';
	import {
		deleteTool,
		downloadJson,
		filterByView,
		listTools,
		matchQuery,
		upsertTool,
		type WorkspaceTool,
		type WorkspaceView
	} from '$lib/data/workspaceResources';

	let query = $state('');
	let viewOption = $state<WorkspaceView>(
		(typeof localStorage !== 'undefined'
			? (localStorage.workspaceViewOption as WorkspaceView)
			: '') || ''
	);
	let tools = $state<WorkspaceTool[]>([]);
	let fileInput: HTMLInputElement | null = $state(null);
	let confirmShow = $state(false);
	let pendingDeleteId = $state<string | null>(null);
	let manifestShow = $state(false);
	let manifestText = $state('');

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
		filterByView(tools, viewOption).filter((t) =>
			matchQuery(`${t.name} ${t.id} ${t.description ?? ''}`, query)
		)
	);

	const reload = () => {
		tools = listTools();
	};

	const cloneTool = (t: WorkspaceTool) => {
		sessionStorage.setItem(
			'tool',
			JSON.stringify({
				...t,
				id: `${t.id}-copy`,
				name: `${t.name} (副本)`
			})
		);
		void goto(withParams('/workspace/tools/create'));
	};

	const showManifest = (t: WorkspaceTool) => {
		manifestText = JSON.stringify(t.meta?.manifest ?? {}, null, 2);
		manifestShow = true;
	};

	const onImport = () => fileInput?.click();

	const handleImportFile = async (e: Event) => {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		try {
			const data = JSON.parse(await file.text()) as WorkspaceTool[] | WorkspaceTool;
			const items = Array.isArray(data) ? data : [data];
			for (const item of items) {
				if (!item?.id || !item?.name) continue;
				upsertTool({
					...item,
					owner: item.owner === 'shared' ? 'shared' : 'you',
					createdAt: item.createdAt || Date.now(),
					updatedAt: Date.now()
				});
			}
			reload();
		} catch {
			/* ignore */
		}
		input.value = '';
	};

	onMount(reload);
</script>

<input
	bind:this={fileInput}
	type="file"
	accept="application/json,.json"
	class="hidden"
	onchange={handleImportFile}
/>

<WorkspaceShell
	title="工具"
	count={filtered.length}
	searchPlaceholder="搜索工具"
	bind:query
	bind:viewOption
	primaryHref={withParams('/workspace/tools/create')}
	primaryLabel="新建工具"
	importLabel="导入"
	{onImport}
	showEmpty={filtered.length === 0}
	emptyTitle="未找到工具"
	emptyHint="请尝试调整您的搜索词或过滤器以找到您需要的内容。"
>
	<div class="divide-y divide-white/[0.04]">
		{#each filtered as tool (tool.id)}
			<div class="flex items-center gap-3 px-4 py-3">
				<div class="min-w-0 flex-1">
					<div class="truncate text-sm font-medium text-white">{tool.name}</div>
					<div class="truncate text-xs text-gray-500">
						{tool.description || tool.id}
					</div>
				</div>
				<ItemMenu
					items={[
						{
							label: '编辑',
							onClick: () =>
								void goto(withParams(`/workspace/tools/edit?id=${encodeURIComponent(tool.id)}`))
						},
						{ label: '克隆', onClick: () => cloneTool(tool) },
						{ label: '导出', onClick: () => downloadJson(`${tool.id}.json`, tool) },
						{ label: '查看 Manifest', onClick: () => showManifest(tool) },
						{
							label: '删除',
							danger: true,
							onClick: () => {
								pendingDeleteId = tool.id;
								confirmShow = true;
							}
						}
					]}
				/>
			</div>
		{/each}
	</div>

	{#snippet footer()}
		<div class="my-16">
			<div class="mb-1 line-clamp-1 text-xl font-medium text-white">由 Open WebUI 社区开发</div>
			<a
				class="mb-2 flex w-full cursor-pointer items-center justify-between rounded-xl px-3.5 py-1.5 transition hover:bg-gray-850"
				href="https://openwebui.com/tools"
				target="_blank"
				rel="noopener noreferrer"
			>
				<div class="self-center">
					<div class="line-clamp-1 font-medium text-gray-100">发现更多工具</div>
					<div class="line-clamp-1 text-sm text-gray-500">发现、下载并探索更多自定义工具</div>
				</div>
				<svg
					class="size-4 text-gray-500"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					aria-hidden="true"
				>
					<path d="m9 18 6-6-6-6"></path>
				</svg>
			</a>
		</div>
	{/snippet}
</WorkspaceShell>

<ConfirmDialog
	bind:show={confirmShow}
	title="删除工具？"
	message="此操作无法撤销。"
	onConfirm={() => {
		if (pendingDeleteId) {
			deleteTool(pendingDeleteId);
			pendingDeleteId = null;
			reload();
		}
	}}
/>

{#if manifestShow}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 px-4"
		onclick={() => (manifestShow = false)}
	>
		<div
			class="w-full max-w-md rounded-2xl border border-gray-800 bg-gray-850 p-4 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			role="dialog"
			aria-modal="true"
		>
			<h3 class="text-base font-medium text-white">Manifest</h3>
			<pre
				class="mt-3 max-h-64 overflow-auto rounded-xl bg-gray-900 p-3 text-xs text-gray-300">{manifestText}</pre
			>
			<div class="mt-4 flex justify-end">
				<button
					type="button"
					class="rounded-xl bg-white px-3 py-1.5 text-sm font-medium text-black hover:bg-gray-200"
					onclick={() => (manifestShow = false)}
				>
					关闭
				</button>
			</div>
		</div>
	</div>
{/if}
