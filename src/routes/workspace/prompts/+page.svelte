<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';

	import Switch from '$lib/components/common/Switch.svelte';
	import ConfirmDialog from '$lib/components/workspace/common/ConfirmDialog.svelte';
	import ItemMenu from '$lib/components/workspace/common/ItemMenu.svelte';
	import WorkspaceShell from '$lib/components/workspace/WorkspaceShell.svelte';
	import {
		deletePrompt,
		downloadJson,
		filterByView,
		listPrompts,
		matchQuery,
		slugify,
		upsertPrompt,
		type WorkspacePrompt,
		type WorkspaceView
	} from '$lib/data/workspaceResources';

	let query = $state('');
	let viewOption = $state<WorkspaceView>(
		(typeof localStorage !== 'undefined'
			? (localStorage.workspaceViewOption as WorkspaceView)
			: '') || ''
	);
	let selectedTag = $state('');
	let prompts = $state<WorkspacePrompt[]>([]);
	let fileInput: HTMLInputElement | null = $state(null);
	let confirmShow = $state(false);
	let pendingDelete = $state<WorkspacePrompt | null>(null);
	let copiedId = $state<string | null>(null);
	let shiftKey = $state(false);

	const withParams = (path: string) => {
		const params = new URLSearchParams();
		const model = $page.url.searchParams.get('model');
		const chat = $page.url.searchParams.get('chat');
		if (model) params.set('model', model);
		if (chat) params.set('chat', chat);
		const search = params.toString();
		return search ? `${path}?${search}` : path;
	};

	const normalizeCommand = (cmd: string) => cmd.replace(/^\/+/, '');
	const displayCommand = (cmd: string) => `/${normalizeCommand(cmd)}`;

	const allTags = $derived(
		Array.from(new Set(prompts.flatMap((p) => p.tags || []))).sort((a, b) => a.localeCompare(b))
	);

	const filtered = $derived(
		filterByView(prompts, viewOption)
			.filter((p) => matchQuery(`${p.title} ${p.command} ${p.content} ${(p.tags || []).join(' ')}`, query))
			.filter((p) => !selectedTag || (p.tags || []).includes(selectedTag))
	);

	const reload = () => {
		prompts = listPrompts();
	};

	const ownerLabel = (p: WorkspacePrompt) => (p.owner === 'shared' ? '共享' : '您');

	const copyContent = async (p: WorkspacePrompt) => {
		try {
			await navigator.clipboard.writeText(p.content);
			copiedId = p.id;
			setTimeout(() => {
				if (copiedId === p.id) copiedId = null;
			}, 2000);
		} catch {
			/* ignore */
		}
	};

	const clonePrompt = (p: WorkspacePrompt) => {
		const base = normalizeCommand(p.command);
		sessionStorage.setItem(
			'prompt',
			JSON.stringify({
				...p,
				id: '',
				title: `${p.title} (副本)`,
				command: slugify(`${base} clone`)
			})
		);
		void goto(withParams('/workspace/prompts/create'));
	};

	const sharePrompt = (p: WorkspacePrompt) => {
		const url = 'https://openwebui.com';
		const tab = window.open(`${url}/prompts/create`, '_blank');
		const payload = {
			name: p.title,
			command: normalizeCommand(p.command),
			content: p.content,
			tags: p.tags || []
		};
		const onMessage = (event: MessageEvent) => {
			if (event.origin !== url) return;
			if (event.data === 'loaded' && tab) {
				tab.postMessage(JSON.stringify(payload), '*');
				window.removeEventListener('message', onMessage);
			}
		};
		window.addEventListener('message', onMessage);
	};

	const exportOne = (p: WorkspacePrompt) => {
		downloadJson(`prompt-export-${Date.now()}.json`, [
			{
				command: normalizeCommand(p.command),
				name: p.title,
				content: p.content,
				tags: p.tags || []
			}
		]);
	};

	const onImport = () => fileInput?.click();

	const handleImportFile = async (e: Event) => {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		try {
			const data = JSON.parse(await file.text()) as unknown;
			const items = Array.isArray(data) ? data : [data];
			for (const raw of items) {
				const item = raw as {
					id?: string;
					title?: string;
					name?: string;
					command?: string;
					content?: string;
					tags?: string[];
					isActive?: boolean;
					owner?: 'you' | 'shared';
					createdAt?: number;
				};
				const title = (item.title || item.name || '').trim();
				const command = normalizeCommand(item.command || '');
				if (!title || !command) continue;
				const id =
					item.id ||
					`prompt-${slugify(title) || command}-${Math.random().toString(36).slice(2, 7)}`;
				upsertPrompt({
					id,
					title,
					command: `/${command}`,
					content: item.content || '',
					tags: item.tags || [],
					isActive: item.isActive !== false,
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

	onMount(() => {
		reload();
		const onKeyDown = (event: KeyboardEvent) => {
			if (event.key === 'Shift') shiftKey = true;
		};
		const onKeyUp = (event: KeyboardEvent) => {
			if (event.key === 'Shift') shiftKey = false;
		};
		const onBlur = () => {
			shiftKey = false;
		};
		window.addEventListener('keydown', onKeyDown);
		window.addEventListener('keyup', onKeyUp);
		window.addEventListener('blur', onBlur);
		return () => {
			window.removeEventListener('keydown', onKeyDown);
			window.removeEventListener('keyup', onKeyUp);
			window.removeEventListener('blur', onBlur);
		};
	});
</script>

<svelte:head>
	<title>提示词 · 工作空间</title>
</svelte:head>

<input
	bind:this={fileInput}
	id="prompts-import-input"
	type="file"
	accept="application/json,.json"
	class="hidden"
	onchange={handleImportFile}
/>

<WorkspaceShell
	title="提示词"
	count={filtered.length}
	searchPlaceholder="搜索提示词"
	bind:query
	bind:viewOption
	primaryHref={withParams('/workspace/prompts/create')}
	primaryLabel="创建提示词"
	importLabel="导入"
	{onImport}
	showEmpty={filtered.length === 0}
	emptyTitle="未找到提示词"
	emptyHint="请尝试调整您的搜索词或过滤器以找到您需要的内容。"
>
	{#snippet filters()}
		{#if allTags.length > 0}
			<div class="relative ml-1">
				<select
					class="appearance-none rounded-xl bg-gray-850 py-1.5 pr-7 pl-2.5 text-sm text-gray-200 outline-none"
					bind:value={selectedTag}
					aria-label="按标签筛选"
				>
					<option value="">标签</option>
					{#each allTags as tag}
						<option value={tag}>{tag}</option>
					{/each}
				</select>
			</div>
		{/if}
	{/snippet}

	<div class="my-2 grid gap-2 px-3 lg:grid-cols-2">
		{#each filtered as prompt (prompt.id)}
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div
				class="flex w-full cursor-pointer space-x-4 rounded-2xl px-3 py-2.5 text-left transition hover:bg-gray-850/50"
				onclick={() => void goto(withParams(`/workspace/prompts/${encodeURIComponent(prompt.id)}`))}
			>
				<div class="flex w-full flex-1 cursor-pointer flex-col space-x-4 pl-1">
					<div class="mb-0.5 flex w-full items-center justify-between">
						<div class="flex min-w-0 items-center gap-2">
							<div class="line-clamp-1 font-medium capitalize text-white">{prompt.title}</div>
							<div class="line-clamp-1 overflow-hidden text-xs text-ellipsis text-gray-500">
								{displayCommand(prompt.command)}
							</div>
						</div>
					</div>
					<div class="flex gap-1 text-xs text-gray-400">
						<div class="shrink-0 text-gray-500">由 {ownerLabel(prompt)} 提供</div>
						{#if prompt.content}
							<div>·</div>
							<div class="line-clamp-1" title={prompt.content}>{prompt.content}</div>
						{/if}
					</div>
				</div>

				<div class="flex flex-row gap-0.5 self-center" onclick={(e) => e.stopPropagation()}>
					{#if shiftKey}
						<button
							class="self-center rounded-xl px-2 py-2 text-sm text-gray-300 transition hover:bg-white/5 hover:text-white"
							type="button"
							aria-label="删除"
							onclick={() => {
								deletePrompt(prompt.id);
								reload();
							}}
						>
							<svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"
								/>
							</svg>
						</button>
					{:else}
						<button
							class="self-center rounded-xl p-1.5 text-sm text-gray-300 transition hover:bg-white/5 hover:text-white"
							type="button"
							aria-label="复制提示词"
							onclick={() => void copyContent(prompt)}
						>
							{#if copiedId === prompt.id}
								<svg class="size-4 text-green-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
									<path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5" />
								</svg>
							{:else}
								<svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										d="M15.666 3.888A2.25 2.25 0 0 0 13.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 0 1-.75.75H9.75a.75.75 0 0 1-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 0 1-2.25 2.25H6.75A2.25 2.25 0 0 1 4.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 0 1 1.927-.184"
									/>
								</svg>
							{/if}
						</button>

						<ItemMenu
							items={[
								{ label: '分享', onClick: () => sharePrompt(prompt) },
								{ label: '复制', onClick: () => clonePrompt(prompt) },
								{ label: '导出', onClick: () => exportOne(prompt) },
								{
									label: '删除',
									danger: true,
									onClick: () => {
										pendingDelete = prompt;
										confirmShow = true;
									}
								}
							]}
						/>

						<button type="button" onclick={(e) => e.stopPropagation()}>
							<Switch
								state={prompt.isActive !== false}
								onChange={(state) => {
									upsertPrompt({ ...prompt, isActive: state, updatedAt: Date.now() });
									reload();
								}}
							/>
						</button>
					{/if}
				</div>
			</div>
		{/each}
	</div>

	{#snippet footer()}
		<div class="my-16">
			<div class="mb-1 line-clamp-1 text-xl font-medium text-white">由 Open WebUI 社区开发</div>
			<a
				class="mb-2 flex w-full cursor-pointer items-center justify-between rounded-xl px-3.5 py-1.5 transition hover:bg-gray-850"
				href="https://openwebui.com/prompts"
				target="_blank"
				rel="noopener noreferrer"
			>
				<div class="self-center">
					<div class="line-clamp-1 font-medium text-gray-100">发现更多提示词</div>
					<div class="line-clamp-1 text-sm text-gray-500">发现、下载并探索更多自定义提示词</div>
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
	title="删除提示词？"
	message={pendingDelete
		? `这将删除 ${displayCommand(pendingDelete.command)}。`
		: '此操作无法撤销。'}
	onConfirm={() => {
		if (pendingDelete) {
			deletePrompt(pendingDelete.id);
			pendingDelete = null;
			reload();
		}
	}}
/>
