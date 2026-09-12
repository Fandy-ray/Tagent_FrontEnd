<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';

	import { getAgentModels } from '$lib/apis/agent';
	import Switch from '$lib/components/common/Switch.svelte';
	import ConfirmDialog from '$lib/components/workspace/common/ConfirmDialog.svelte';
	import ItemMenu from '$lib/components/workspace/common/ItemMenu.svelte';
	import WorkspaceShell from '$lib/components/workspace/WorkspaceShell.svelte';
	import {
		deleteModel,
		downloadJson,
		filterByView,
		listModels,
		matchQuery,
		upsertModel,
		type WorkspaceModel,
		type WorkspaceView
	} from '$lib/data/workspaceResources';

	let query = $state('');
	let viewOption = $state<WorkspaceView>(
		(typeof localStorage !== 'undefined'
			? (localStorage.workspaceViewOption as WorkspaceView)
			: '') || ''
	);
	let loading = $state(true);
	let models = $state<WorkspaceModel[]>([]);
	let fileInput: HTMLInputElement | null = $state(null);
	let confirmShow = $state(false);
	let pendingDeleteId = $state<string | null>(null);
	let actionsOpen = $state(false);
	let actionsMenuStyle = $state('');
	let actionsBtnEl: HTMLButtonElement | null = $state(null);

	const openActionsMenu = () => {
		if (actionsOpen) {
			actionsOpen = false;
			return;
		}
		const rect = actionsBtnEl?.getBoundingClientRect();
		if (rect) {
			actionsMenuStyle = `top:${Math.round(rect.bottom + 4)}px;right:${Math.round(window.innerWidth - rect.right)}px;`;
		} else {
			actionsMenuStyle = '';
		}
		actionsOpen = true;
	};

	const withParams = (path: string) => {
		const params = new URLSearchParams();
		const model = $page.url.searchParams.get('model');
		const chat = $page.url.searchParams.get('chat');
		if (model) params.set('model', model);
		if (chat) params.set('chat', chat);
		const search = params.toString();
		return search ? `${path}?${search}` : path;
	};

	const visibleModels = $derived(
		filterByView(models, viewOption).filter((m) => {
			if (m.meta?.hidden) return false;
			return matchQuery(`${m.name} ${m.id}`, query);
		})
	);

	const mergeAgent = async () => {
		const local = listModels();
		const localIds = new Set(local.map((m) => m.id));
		try {
			const res = await getAgentModels();
			const systemModels: WorkspaceModel[] = res.data
				.filter((m) => !localIds.has(m.id))
				.map((m) => ({
					id: m.id,
					name: m.name || m.id,
					baseModelId: m.id,
					description: '',
					isActive: true,
					owner: 'system' as const,
					createdAt: (m.created || 0) * 1000 || Date.now(),
					updatedAt: (m.created || 0) * 1000 || Date.now()
				}));
			models = [...local, ...systemModels].sort((a, b) => b.updatedAt - a.updatedAt);
		} catch {
			models = local;
		}
	};

	const copyLink = async (id: string) => {
		const url = `${window.location.origin}/qa?model=${encodeURIComponent(id)}`;
		try {
			await navigator.clipboard.writeText(url);
		} catch {
			/* ignore */
		}
	};

	const toggleActive = (model: WorkspaceModel, state: boolean) => {
		if (model.owner === 'system') return;
		upsertModel({ ...model, isActive: state });
		void mergeAgent();
	};

	const setHidden = (model: WorkspaceModel, hidden: boolean) => {
		if (model.owner === 'system') return;
		upsertModel({
			...model,
			meta: { ...model.meta, hidden }
		});
		void mergeAgent();
	};

	const enableAll = () => {
		for (const m of listModels()) {
			if (m.isActive === false) upsertModel({ ...m, isActive: true });
		}
		void mergeAgent();
		actionsOpen = false;
	};

	const disableAll = () => {
		for (const m of listModels()) {
			if (m.isActive !== false) upsertModel({ ...m, isActive: false });
		}
		void mergeAgent();
		actionsOpen = false;
	};

	const showAll = () => {
		for (const m of listModels()) {
			if (m.meta?.hidden) upsertModel({ ...m, meta: { ...m.meta, hidden: false } });
		}
		void mergeAgent();
		actionsOpen = false;
	};

	const hideAll = () => {
		for (const m of listModels()) {
			upsertModel({ ...m, meta: { ...m.meta, hidden: true } });
		}
		void mergeAgent();
		actionsOpen = false;
	};

	const cloneModel = (model: WorkspaceModel) => {
		sessionStorage.setItem(
			'model',
			JSON.stringify({
				...model,
				id: `${model.id}-copy`,
				name: `${model.name} (副本)`,
				owner: 'you'
			})
		);
		void goto(withParams('/workspace/models/create'));
	};

	const exportOne = (model: WorkspaceModel) => {
		downloadJson(`${model.id}.json`, model);
	};

	const onImport = () => fileInput?.click();

	const handleImportFile = async (e: Event) => {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		try {
			const text = await file.text();
			const data = JSON.parse(text) as WorkspaceModel[] | WorkspaceModel;
			const items = Array.isArray(data) ? data : [data];
			for (const item of items) {
				if (!item?.id || !item?.name) continue;
				upsertModel({
					...item,
					owner: item.owner === 'shared' ? 'shared' : 'you',
					createdAt: item.createdAt || Date.now(),
					updatedAt: Date.now()
				});
			}
			await mergeAgent();
		} catch {
			/* ignore invalid */
		}
		input.value = '';
	};

	onMount(() => {
		void mergeAgent().finally(() => {
			loading = false;
		});
	});
</script>

<input
	bind:this={fileInput}
	type="file"
	accept="application/json,.json"
	class="hidden"
	onchange={handleImportFile}
/>

<WorkspaceShell
	title="模型"
	count={loading ? null : visibleModels.length}
	searchPlaceholder="搜索模型"
	bind:query
	bind:viewOption
	primaryHref={withParams('/workspace/models/create')}
	primaryLabel="创建模型"
	importLabel="导入"
	{onImport}
	showEmpty={!loading && visibleModels.length === 0}
	emptyTitle="未找到任何模型"
>
	{#snippet toolbarEnd()}
		<div class="relative">
			<button
				bind:this={actionsBtnEl}
				type="button"
				class="rounded-lg p-1.5 text-gray-400 transition hover:bg-gray-800 hover:text-white"
				title="操作"
				aria-label="操作"
				aria-expanded={actionsOpen}
				onclick={(e) => {
					e.preventDefault();
					e.stopPropagation();
					openActionsMenu();
				}}
			>
				<svg class="size-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
					<path
						d="M6 12a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0zm7.5 0a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0zm7.5 0a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0z"
					/>
				</svg>
			</button>
		</div>
	{/snippet}

	{#if loading}
		<div class="flex items-center justify-center py-16 text-sm text-gray-500">加载中…</div>
	{:else}
		<div class="divide-y divide-white/[0.04]">
			{#each visibleModels as model (model.id + (model.owner ?? ''))}
				<div class="flex items-center gap-3 px-4 py-3">
					{#if model.meta?.profileImageUrl}
						<img
							src={model.meta.profileImageUrl}
							alt=""
							class="size-9 shrink-0 rounded-full object-cover"
						/>
					{:else}
						<div
							class="flex size-9 shrink-0 items-center justify-center rounded-full bg-gray-800 text-sm font-medium text-gray-200"
						>
							{(model.name || model.id).charAt(0).toUpperCase()}
						</div>
					{/if}
					<button
						type="button"
						class="min-w-0 flex-1 text-left"
						onclick={() => {
							if (model.owner === 'system') return;
							void goto(withParams(`/workspace/models/edit?id=${encodeURIComponent(model.id)}`));
						}}
					>
						<div class="truncate text-sm font-medium text-white">{model.name}</div>
						<div class="truncate text-xs text-gray-500">{model.id}</div>
					</button>
					{#if model.owner !== 'system'}
						<Switch
							state={model.isActive !== false}
							onChange={(state) => toggleActive(model, state)}
						/>
					{/if}
					<ItemMenu
						items={model.owner === 'system'
							? [{ label: '复制链接', onClick: () => void copyLink(model.id) }]
							: [
									{
										label: '编辑',
										onClick: () =>
											void goto(
												withParams(`/workspace/models/edit?id=${encodeURIComponent(model.id)}`)
											)
									},
									{ label: '克隆', onClick: () => cloneModel(model) },
									{ label: '复制链接', onClick: () => void copyLink(model.id) },
									{
										label: model.meta?.hidden ? '显示' : '隐藏',
										onClick: () => setHidden(model, !model.meta?.hidden)
									},
									{ label: '导出', onClick: () => exportOne(model) },
									{
										label: '删除',
										danger: true,
										onClick: () => {
											pendingDeleteId = model.id;
											confirmShow = true;
										}
									}
								]}
					/>
				</div>
			{/each}
		</div>
	{/if}

	{#snippet footer()}
		<div class="mt-8 mb-2">
			<div class="mb-1.5 px-0.5 text-xl font-medium text-white">由 Open WebUI 社区开发</div>
			<a
				href="https://openwebui.com/models"
				target="_blank"
				rel="noopener noreferrer"
				class="flex w-full items-center justify-between rounded-xl px-3.5 py-1.5 transition hover:bg-[#242424]"
			>
				<div>
					<div class="font-medium text-gray-100">发现更多模型</div>
					<div class="text-sm text-gray-500">发现、下载并探索更多模型预设</div>
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

{#if actionsOpen}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-[200]"
		onclick={() => {
			actionsOpen = false;
		}}
	></div>
	<div
		class="fixed z-[210] w-[170px] rounded-xl border border-gray-800 bg-gray-850 p-1 text-white shadow-sm"
		style={actionsMenuStyle}
		role="menu"
	>
		<button
			type="button"
			class="flex w-full cursor-pointer items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium select-none hover:bg-gray-800"
			onclick={() => enableAll()}
		>
			<svg class="size-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
				<path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
			</svg>
			<span>全部启用</span>
		</button>
		<button
			type="button"
			class="flex w-full cursor-pointer items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium select-none hover:bg-gray-800"
			onclick={() => disableAll()}
		>
			<svg class="size-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
				<path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14" />
			</svg>
			<span>全部禁用</span>
		</button>
		<hr class="my-1 border-gray-800" />
		<button
			type="button"
			class="flex w-full cursor-pointer items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium select-none hover:bg-gray-800"
			onclick={() => showAll()}
		>
			<svg class="size-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
				<path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
				<path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
			</svg>
			<span>显示全部</span>
		</button>
		<button
			type="button"
			class="flex w-full cursor-pointer items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium select-none hover:bg-gray-800"
			onclick={() => hideAll()}
		>
			<svg class="size-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
				<path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 0 0 1.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.451 10.451 0 0 1 12 4.5c4.756 0 8.773 3.162 10.065 7.498a10.522 10.522 0 0 1-4.293 5.774M6.228 6.228 3 3m3.228 3.228 3.65 3.65m7.894 7.894L21 21m-3.228-3.228-3.65-3.65m0 0a3 3 0 1 0-4.243-4.243m4.242 4.242L9.88 9.88" />
			</svg>
			<span>全部隐藏</span>
		</button>
	</div>
{/if}

<ConfirmDialog
	bind:show={confirmShow}
	title="删除模型？"
	message="此操作无法撤销。系统模型不会被删除。"
	onConfirm={() => {
		if (pendingDeleteId) {
			deleteModel(pendingDeleteId);
			pendingDeleteId = null;
			void mergeAgent();
		}
	}}
/>
