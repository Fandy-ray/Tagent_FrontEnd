<script lang="ts">
	import { onMount } from 'svelte';

	import { getAgentModels } from '$lib/apis/agent';
	import WorkspacePanel from '$lib/components/workspace/WorkspacePanel.svelte';

	let query = $state('');
	let loading = $state(true);
	let models = $state<{ id: string; name: string }[]>([]);
	let error = $state('');

	const filtered = $derived(
		query.trim()
			? models.filter((model) => {
					const q = query.trim().toLowerCase();
					return model.name.toLowerCase().includes(q) || model.id.toLowerCase().includes(q);
				})
			: models
	);

	onMount(() => {
		void getAgentModels()
			.then((list) => {
				models = list.data.map((model) => ({
					id: model.id,
					name: model.name || model.id
				}));
			})
			.catch(() => {
				error = '读不到 basic-agent 模型列表，请确认服务已启动。';
				models = [];
			})
			.finally(() => {
				loading = false;
			});
	});
</script>

<WorkspacePanel
	title="模型"
	count={loading ? null : filtered.length}
	searchPlaceholder="搜索模型"
	bind:query
	primaryAction="创建模型"
	secondaryAction="导入"
	emptyTitle="未找到任何模型"
	emptyHint="请尝试调整您的搜索词或过滤器以找到您需要的内容。"
	footerTitle="发现更多模型"
	footerDesc="发现、下载并探索更多模型预设"
	footerHref="https://openwebui.com/models"
	onPrimary={() => {
		error = '创建模型需对接 Open WebUI / basic-agent 管理接口，后续步骤再接。';
	}}
	onSecondary={() => {
		error = '导入功能后续对接。';
	}}
>
	{#if loading}
		<div class="flex items-center justify-center py-16 text-sm text-gray-500">加载中…</div>
	{:else if filtered.length > 0}
		<div class="divide-y divide-white/[0.04]">
			{#each filtered as model (model.id)}
				<div class="flex items-center justify-between px-4 py-3">
					<div class="min-w-0">
						<div class="truncate text-sm font-medium text-white">{model.name}</div>
						<div class="truncate text-xs text-gray-500">{model.id}</div>
					</div>
				</div>
			{/each}
		</div>
	{:else}
		<div class="flex flex-col items-center justify-center px-6 py-20 text-center">
			<div class="mb-3 text-3xl">😕</div>
			<div class="mb-1 text-lg font-medium text-white">未找到任何模型</div>
			<div class="max-w-md text-xs text-gray-500">
				{error || '请尝试调整您的搜索词或过滤器以找到您需要的内容。'}
			</div>
		</div>
	{/if}
</WorkspacePanel>
