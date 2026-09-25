<script lang="ts">
	import { onMount } from 'svelte';

	import Modal from '$lib/components/common/Modal.svelte';
	import Textarea from '$lib/components/common/Textarea.svelte';
	import {
		listPrompts,
		slugify,
		type PromptHistoryEntry,
		type WorkspacePrompt
	} from '$lib/data/workspaceResources';

	type Props = {
		edit?: boolean;
		initial?: WorkspacePrompt | null;
		onBack?: () => void;
		onSave?: (prompt: WorkspacePrompt) => void;
	};

	let { edit = false, initial = null, onBack = () => {}, onSave = () => {} }: Props = $props();

	let loading = $state(false);
	let error = $state('');
	let showAccessModal = $state(false);
	let showEditModal = $state(false);
	let hasManualEdit = $state(false);
	let contentCopied = $state(false);
	let idCopied = $state(false);
	let hydrated = $state(false);

	let id = $state('');
	let name = $state('');
	let command = $state('');
	let content = $state('');
	let tags = $state<string[]>([]);
	let tagDraft = $state('');
	let isActive = $state(true);
	let accessNote = $state('仅自己可见');
	let createdAt = $state(Date.now());
	let history = $state<PromptHistoryEntry[]>([]);
	let selectedHistoryId = $state<string | null>(null);
	let commitMessage = $state('');
	let isProduction = $state(true);

	const displayCommand = $derived(command.replace(/^\/+/, ''));
	const selectedHistory = $derived(
		history.find((h) => h.id === selectedHistoryId) ?? history[0] ?? null
	);
	const shownContent = $derived(
		edit ? (selectedHistory?.content ?? content) : content
	);

	$effect(() => {
		if (!edit && !hasManualEdit && hydrated) {
			command = name ? slugify(name) : '';
		}
	});

	const validateCommand = (value: string) => /^[a-zA-Z0-9-_]+$/.test(value.replace(/^\/+/, ''));

	const normalizeCommand = (value: string) => value.trim().replace(/^\/+/, '');

	const addTag = () => {
		const t = tagDraft.trim();
		if (!t || tags.includes(t)) {
			tagDraft = '';
			return;
		}
		tags = [...tags, t];
		tagDraft = '';
	};

	const loadInitial = (prompt: WorkspacePrompt) => {
		id = prompt.id || '';
		name = prompt.title || '';
		command = normalizeCommand(prompt.command || '');
		content = prompt.content || '';
		tags = [...(prompt.tags || [])];
		isActive = prompt.isActive !== false;
		createdAt = prompt.createdAt || Date.now();
		accessNote = prompt.owner === 'shared' ? '与您共享' : '仅自己可见';
		history =
			Array.isArray(prompt.history) && prompt.history.length
				? [...prompt.history]
				: [
						{
							id: `v-${prompt.updatedAt || Date.now()}`,
							commitMessage: '当前版本',
							content: prompt.content || '',
							createdAt: prompt.updatedAt || Date.now()
						}
					];
		selectedHistoryId = history[0]?.id ?? null;
		if (edit || prompt.title) hasManualEdit = true;
	};

	onMount(() => {
		if (initial) loadInitial(initial);
		hydrated = true;
	});

	const buildPrompt = (nextContent: string, nextHistory = history): WorkspacePrompt => {
		const cmd = normalizeCommand(command);
		const promptId =
			id ||
			`prompt-${slugify(name) || cmd || Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
		return {
			id: promptId,
			title: name.trim(),
			command: `/${cmd}`,
			content: nextContent,
			tags,
			isActive,
			owner: accessNote === '与您共享' ? 'shared' : 'you',
			createdAt: createdAt || Date.now(),
			updatedAt: Date.now(),
			history: nextHistory
		};
	};

	const submitCreate = () => {
		error = '';
		const cmd = normalizeCommand(command);
		if (!name.trim()) {
			error = '请填写名称';
			return;
		}
		if (!validateCommand(cmd)) {
			error = '命令字符串中只允许使用英文字母，数字 (0-9) 以及连字符 (-)。';
			return;
		}
		if (!content.trim()) {
			error = '请填写提示词内容';
			return;
		}
		const conflict = listPrompts().some(
			(p) => normalizeCommand(p.command) === cmd && (!edit || p.id !== id)
		);
		if (conflict) {
			error = '该命令已存在，请换一个';
			return;
		}
		loading = true;
		const prompt = buildPrompt(content, [
			{
				id: `v-${Date.now()}`,
				commitMessage: '创建',
				content,
				createdAt: Date.now()
			}
		]);
		onSave(prompt);
		loading = false;
	};

	const submitEditContent = () => {
		error = '';
		const cmd = normalizeCommand(command);
		if (!validateCommand(cmd)) {
			error = '命令字符串中只允许使用英文字母，数字 (0-9) 以及连字符 (-)。';
			return;
		}
		loading = true;
		const entry = {
			id: `v-${Date.now()}`,
			commitMessage: commitMessage.trim() || '更新',
			content,
			createdAt: Date.now()
		};
		const nextHistory = isProduction ? [entry, ...history] : [...history, entry];
		history = nextHistory;
		selectedHistoryId = entry.id;
		const prompt = buildPrompt(isProduction ? content : shownContent, nextHistory);
		onSave(prompt);
		showEditModal = false;
		commitMessage = '';
		isProduction = true;
		loading = false;
	};

	const saveMeta = () => {
		if (!edit || !id) return;
		const cmd = normalizeCommand(command);
		if (!name.trim() || !validateCommand(cmd)) return;
		const conflict = listPrompts().some(
			(p) => normalizeCommand(p.command) === cmd && p.id !== id
		);
		if (conflict) {
			error = '该命令已存在，请换一个';
			return;
		}
		error = '';
		onSave(buildPrompt(content, history));
	};

	const copyText = async (text: string, kind: 'content' | 'id') => {
		try {
			await navigator.clipboard.writeText(text);
			if (kind === 'content') {
				contentCopied = true;
				setTimeout(() => {
					contentCopied = false;
				}, 1500);
			} else {
				idCopied = true;
				setTimeout(() => {
					idCopied = false;
				}, 1500);
			}
		} catch {
			/* ignore */
		}
	};
</script>

<div class="px-1">
	<button
		type="button"
		class="mb-3 inline-flex items-center gap-1 text-sm text-gray-400 transition hover:text-white"
		onclick={onBack}
	>
		<svg class="size-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
			<path
				fill-rule="evenodd"
				d="M17 10a.75.75 0 01-.75.75H5.612l4.158 3.96a.75.75 0 11-1.04 1.08l-5.5-5.25a.75.75 0 010-1.08l5.5-5.25a.75.75 0 111.04 1.08L5.612 9.25H16.25A.75.75 0 0117 10z"
				clip-rule="evenodd"
			/>
		</svg>
		<span>返回</span>
	</button>

	{#if error}
		<div class="mb-3 rounded-xl border border-red-900/50 bg-red-950/40 px-3 py-2 text-sm text-red-300">
			{error}
		</div>
	{/if}

	{#if edit}
		<div class="flex w-full max-h-[100dvh] flex-col">
			<div class="flex shrink-0 items-start justify-between gap-4">
				<div class="min-w-0 flex-1">
					<input
						class="w-full bg-transparent text-2xl text-white outline-none placeholder:text-gray-500"
						placeholder="提示词名称"
						bind:value={name}
						onblur={saveMeta}
					/>
					<div class="flex w-full flex-1 items-center gap-0.5 text-sm text-gray-500">
						<span>/</span>
						<input
							class="bg-transparent outline-none"
							placeholder="命令"
							bind:value={command}
							oninput={() => {
								hasManualEdit = true;
							}}
							onblur={saveMeta}
						/>
					</div>
				</div>

				<div>
					<div class="flex shrink-0 items-center justify-end gap-2">
						<button
							class="rounded-full bg-white px-4 py-1 text-sm font-medium text-black shadow-xs transition hover:opacity-90"
							type="button"
							onclick={() => {
								showEditModal = true;
							}}
						>
							编辑
						</button>
						<button
							class="flex items-center gap-1.5 rounded-full border border-gray-800 bg-gray-850 px-2.5 py-1 text-sm text-white transition hover:bg-gray-800"
							type="button"
							onclick={() => {
								showAccessModal = true;
							}}
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2.5"
								class="size-3.5 shrink-0"
								aria-hidden="true"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"
								/>
							</svg>
							访问
						</button>
					</div>
					<div class="mt-1.5">
						<button
							class="cursor-pointer rounded-lg px-2 py-1 font-mono text-xs text-gray-500 transition hover:underline"
							type="button"
							title="点击复制 ID"
							onclick={() => void copyText(id, 'id')}
						>
							{idCopied ? '已复制' : id}
						</button>
					</div>
				</div>
			</div>

			<div class="mb-2 mt-2 flex flex-wrap gap-1.5">
				{#each tags as tag}
					<button
						type="button"
						class="rounded-full bg-gray-850 px-2 py-0.5 text-xs text-gray-300 hover:bg-gray-800"
						onclick={() => {
							tags = tags.filter((t) => t !== tag);
							saveMeta();
						}}
					>
						{tag} ×
					</button>
				{/each}
				<input
					class="min-w-[6rem] flex-1 bg-transparent text-sm outline-none placeholder:text-gray-500"
					placeholder="添加标签..."
					bind:value={tagDraft}
					onkeydown={(e) => {
						if (e.key === 'Enter') {
							e.preventDefault();
							addTag();
							saveMeta();
						}
					}}
				/>
			</div>

			<div class="flex flex-1 flex-col gap-4 overflow-hidden pb-6 md:flex-row">
				<div class="hidden w-72 shrink-0 overflow-hidden md:flex md:flex-col">
					<div class="mb-2 shrink-0 text-xs text-gray-500">历史记录</div>
					<div class="flex-1 space-y-0 overflow-y-auto">
						{#each history as entry}
							<button
								type="button"
								class="mb-1 w-full rounded-2xl px-3.5 py-2 text-left transition {selectedHistoryId ===
								entry.id
									? 'bg-gray-850/50'
									: 'hover:bg-gray-850/50'}"
								onclick={() => {
									selectedHistoryId = entry.id;
								}}
							>
								<div class="mb-1 flex items-center gap-2">
									<div class="truncate text-xs text-white">{entry.commitMessage}</div>
									{#if entry.id === history[0]?.id}
										<span
											class="rounded bg-emerald-900/40 px-1.5 py-0.5 text-[10px] text-emerald-300"
											>线上</span
										>
									{/if}
								</div>
								<div class="text-xs text-gray-500">
									{new Date(entry.createdAt).toLocaleString()}
								</div>
							</button>
						{/each}
					</div>
				</div>

				<div class="flex min-h-0 flex-1 flex-col overflow-hidden">
					<div class="mb-1 flex shrink-0 items-center justify-between">
						<div class="flex items-center gap-2">
							<div class="text-xs text-gray-500">提示词内容</div>
							{#if selectedHistory}
								<span class="rounded bg-gray-800 px-1.5 font-mono text-xs text-gray-500">
									{selectedHistory.id.slice(0, 7)}
								</span>
							{/if}
						</div>
					</div>
					<div class="relative min-h-0 flex-1">
						<div class="absolute top-2 right-2 z-10">
							<button
								class="rounded-lg p-1.5 transition hover:bg-gray-800"
								type="button"
								aria-label="复制内容"
								onclick={() => void copyText(shownContent, 'content')}
							>
								{#if contentCopied}
									<svg class="size-4 text-green-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
										<path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5" />
									</svg>
								{:else}
									<svg class="size-4 text-gray-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
										<path stroke-linecap="round" stroke-linejoin="round" d="M15.666 3.888A2.25 2.25 0 0 0 13.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 0 1-.75.75H9.75a.75.75 0 0 1-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 0 1-2.25 2.25H6.75A2.25 2.25 0 0 1 4.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 0 1 1.927-.184" />
									</svg>
								{/if}
							</button>
						</div>
						<div
							class="h-full min-h-[16rem] overflow-y-auto rounded-xl border border-gray-850/50 bg-gray-900 px-4 py-3"
						>
							<pre class="pr-8 font-mono text-xs whitespace-pre-wrap text-gray-200">{shownContent}</pre>
						</div>
					</div>
				</div>
			</div>
		</div>
	{:else}
		<div class="flex w-full max-h-full justify-center">
			<form
				class="mb-10 flex w-full flex-col"
				onsubmit={(e) => {
					e.preventDefault();
					submitCreate();
				}}
			>
				<div class="mb-2">
					<div class="flex w-full flex-col" title={`只允许使用英文字母，数字 (0-9) 以及连字符 (-) - 在对话框中输入 "/${displayCommand || 'COMMAND'}" 激活此命令`}>
						<div class="flex items-center">
							<input
								class="w-full bg-transparent text-2xl text-white outline-none placeholder:text-gray-500"
								placeholder="名称"
								bind:value={name}
								required
							/>
							<div class="shrink-0 self-center">
								<button
									class="flex items-center gap-1 rounded-full bg-gray-850 px-2 py-1 text-white transition hover:bg-gray-800"
									type="button"
									onclick={() => {
										showAccessModal = true;
									}}
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										viewBox="0 0 24 24"
										fill="none"
										stroke="currentColor"
										stroke-width="2.5"
										class="size-3.5 shrink-0"
										aria-hidden="true"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"
										/>
									</svg>
									<div class="shrink-0 text-sm font-medium">访问</div>
								</button>
							</div>
						</div>
						<div class="flex items-center gap-0.5 text-xs text-gray-500">
							<div>/</div>
							<input
								class="w-full bg-transparent outline-none"
								placeholder="命令"
								bind:value={command}
								oninput={() => {
									hasManualEdit = true;
								}}
								required
							/>
						</div>

						<div class="mt-2 flex flex-wrap gap-1.5">
							{#each tags as tag}
								<button
									type="button"
									class="rounded-full bg-gray-850 px-2 py-0.5 text-xs text-gray-300 hover:bg-gray-800"
									onclick={() => {
										tags = tags.filter((t) => t !== tag);
									}}
								>
									{tag} ×
								</button>
							{/each}
							<input
								class="min-w-[6rem] flex-1 bg-transparent text-sm outline-none placeholder:text-gray-500"
								placeholder="添加标签..."
								bind:value={tagDraft}
								onkeydown={(e) => {
									if (e.key === 'Enter') {
										e.preventDefault();
										addTag();
									}
								}}
							/>
						</div>
					</div>
				</div>

				<div class="my-2">
					<div class="text-xs text-gray-500">提示词内容</div>
					<div class="mt-1">
						<Textarea
							className="w-full resize-none overflow-y-hidden bg-transparent text-sm text-white outline-none placeholder:text-gray-500"
							placeholder="用 50 个字写一份总结 [主题或关键词]"
							bind:value={content}
							rows={6}
						/>
						<div class="text-xs text-gray-500">
							ⓘ 使用
							<span class="font-medium text-gray-300">{'{{变量}}'}</span>
							用于占位符
						</div>
					</div>
				</div>

				<div class="my-4 flex justify-end pb-20">
					<button
						class="flex w-full justify-center rounded-xl bg-white px-4 py-2 text-sm font-medium text-black transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60 lg:w-fit"
						type="submit"
						disabled={loading}
					>
						保存并创建
					</button>
				</div>
			</form>
		</div>
	{/if}
</div>

{#if showEditModal}
	<Modal bind:show={showEditModal} size="lg">
		<div class="px-5 pt-4 pb-5">
			<div class="mb-2 flex items-center justify-between">
				<div class="text-lg font-medium">编辑提示词</div>
				<button
					class="rounded-lg p-1 hover:bg-gray-800"
					type="button"
					aria-label="关闭"
					onclick={() => {
						showEditModal = false;
					}}
				>
					<svg class="size-5" viewBox="0 0 20 20" fill="currentColor">
						<path
							d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
						/>
					</svg>
				</button>
			</div>

			<form
				onsubmit={(e) => {
					e.preventDefault();
					submitEditContent();
				}}
			>
				<div class="my-2">
					<div class="text-xs text-gray-500">提示词内容</div>
					<div class="mt-1">
						<Textarea
							className="w-full resize-none overflow-y-hidden bg-transparent text-sm outline-none"
							placeholder="用 50 个字写一份总结 [主题或关键词]"
							bind:value={content}
							rows={6}
						/>
					</div>
				</div>
				<div class="my-2">
					<div class="text-xs text-gray-500">提交说明（可选）</div>
					<div class="mt-1">
						<input
							class="w-full bg-transparent text-sm outline-none placeholder:text-gray-500"
							placeholder="描述本次更改..."
							bind:value={commitMessage}
						/>
					</div>
				</div>
				<div class="mt-4 flex items-center justify-between">
					<label class="flex cursor-pointer items-center gap-2">
						<input type="checkbox" bind:checked={isProduction} class="size-4 rounded" />
						<span class="text-sm text-gray-300">设为生产版本</span>
					</label>
					<button
						class="rounded-full bg-white px-4 py-2 text-sm font-medium text-black transition hover:bg-gray-100 disabled:opacity-60"
						type="submit"
						disabled={loading}
					>
						保存
					</button>
				</div>
			</form>
		</div>
	</Modal>
{/if}

{#if showAccessModal}
	<Modal bind:show={showAccessModal} size="sm">
		<div class="px-5 py-4">
			<div class="mb-2 text-lg font-medium">访问</div>
			<p class="mb-3 text-sm text-gray-400">本地演示：访问控制暂存于本机</p>
			<div class="space-y-2">
				<button
					type="button"
					class="flex w-full items-center justify-between rounded-xl px-3 py-2 text-sm transition hover:bg-gray-800 {accessNote ===
					'仅自己可见'
						? 'bg-gray-850 text-white'
						: 'text-gray-300'}"
					onclick={() => {
						accessNote = '仅自己可见';
					}}
				>
					仅自己可见
				</button>
				<button
					type="button"
					class="flex w-full items-center justify-between rounded-xl px-3 py-2 text-sm transition hover:bg-gray-800 {accessNote ===
					'与您共享'
						? 'bg-gray-850 text-white'
						: 'text-gray-300'}"
					onclick={() => {
						accessNote = '与您共享';
					}}
				>
					与您共享
				</button>
			</div>
			<div class="mt-4 flex justify-end">
				<button
					type="button"
					class="rounded-lg bg-white px-3 py-1.5 text-sm font-medium text-black hover:bg-gray-200"
					onclick={() => {
						showAccessModal = false;
						if (edit) saveMeta();
					}}
				>
					完成
				</button>
			</div>
		</div>
	</Modal>
{/if}
