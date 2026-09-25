<script lang="ts">
	export type FolderKnowledgeItem = {
		id: string;
		name: string;
		type: 'collection' | 'file';
	};

	export type FolderFormValue = {
		name: string;
		systemPrompt: string;
		backgroundImageUrl: string | null;
		knowledgeItems: FolderKnowledgeItem[];
	};

	type KnowledgeOption = {
		id: string;
		name: string;
	};

	type Props = {
		open?: boolean;
		title?: string;
		initialName?: string;
		initialSystemPrompt?: string;
		initialBackgroundImageUrl?: string | null;
		initialKnowledgeItems?: FolderKnowledgeItem[];
		knowledgeOptions?: KnowledgeOption[];
		confirmLabel?: string;
		onClose?: () => void;
		onSubmit?: (value: FolderFormValue) => void;
		onOpenWorkspaceKnowledge?: () => void;
	};

	let {
		open = false,
		title = '创建分组',
		initialName = '',
		initialSystemPrompt = '',
		initialBackgroundImageUrl = null,
		initialKnowledgeItems = [],
		knowledgeOptions = [],
		confirmLabel = '保存',
		onClose = () => {},
		onSubmit = () => {},
		onOpenWorkspaceKnowledge = () => {}
	}: Props = $props();

	let name = $state('');
	let systemPrompt = $state('');
	let backgroundImageUrl = $state<string | null>(null);
	let knowledgeItems = $state<FolderKnowledgeItem[]>([]);
	let showKnowledgePicker = $state(false);
	let fileInput: HTMLInputElement | null = $state(null);
	let knowledgeFileInput: HTMLInputElement | null = $state(null);

	$effect(() => {
		if (open) {
			name = initialName;
			systemPrompt = initialSystemPrompt;
			backgroundImageUrl = initialBackgroundImageUrl;
			knowledgeItems = [...initialKnowledgeItems];
			showKnowledgePicker = false;
			queueMicrotask(() => document.getElementById('folder-name')?.focus());
		}
	});

	const submit = () => {
		const trimmed = name.trim();
		if (!trimmed) return;
		onSubmit({
			name: trimmed,
			systemPrompt: systemPrompt.trim(),
			backgroundImageUrl,
			knowledgeItems: [...knowledgeItems]
		});
		onClose();
	};

	const onPickBackground = (event: Event) => {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file || !['image/gif', 'image/webp', 'image/jpeg', 'image/png'].includes(file.type)) {
			input.value = '';
			return;
		}
		const reader = new FileReader();
		reader.onload = () => {
			backgroundImageUrl = String(reader.result ?? '');
		};
		reader.readAsDataURL(file);
		input.value = '';
	};

	const addKnowledge = (option: KnowledgeOption) => {
		if (knowledgeItems.some((item) => item.id === option.id)) return;
		knowledgeItems = [
			...knowledgeItems,
			{ id: option.id, name: option.name, type: 'collection' }
		];
		showKnowledgePicker = false;
	};

	const removeKnowledge = (id: string) => {
		knowledgeItems = knowledgeItems.filter((item) => item.id !== id);
	};

	const onUploadKnowledgeFiles = (event: Event) => {
		const input = event.target as HTMLInputElement;
		const files = Array.from(input.files ?? []);
		for (const file of files) {
			if (file.type.startsWith('image/')) continue;
			const id = `local-file-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
			knowledgeItems = [
				...knowledgeItems,
				{ id, name: file.name, type: 'file' }
			];
		}
		input.value = '';
	};
</script>

{#if open}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-[90] flex items-center justify-center bg-black/60 px-4"
		onclick={onClose}
	>
		<div
			class="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-2xl border border-gray-800 bg-gray-850 text-gray-100 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			role="dialog"
			aria-modal="true"
			aria-label={title}
		>
			<div class="flex justify-between px-5 pt-4 pb-1 text-gray-300">
				<div class="self-center text-lg font-medium">{title}</div>
				<button type="button" class="self-center" onclick={onClose} aria-label="关闭">
					<svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
						<path stroke-linecap="round" d="M6 6l12 12M18 6L6 18"></path>
					</svg>
				</button>
			</div>

			<div class="flex w-full flex-col px-5 pb-4 text-gray-200">
				<div class="mt-1 flex w-full flex-col">
					<div class="mb-1 text-xs text-gray-500">分组名称</div>
					<input
						id="folder-name"
						class="w-full bg-transparent text-sm outline-none placeholder:text-gray-600"
						type="text"
						bind:value={name}
						placeholder="输入分组名称"
						autocomplete="off"
						onkeydown={(e) => {
							if (e.key === 'Enter') {
								e.preventDefault();
								submit();
							}
						}}
					/>
				</div>

				<input
					bind:this={fileInput}
					type="file"
					hidden
					accept="image/gif,image/webp,image/jpeg,image/png"
					onchange={onPickBackground}
				/>

				<div class="mt-1 flex w-full items-center justify-between">
					<div class="text-xs text-gray-500">分组背景图</div>
					<button
						type="button"
						class="flex rounded-sm px-3 py-1 text-xs transition hover:bg-gray-800"
						onclick={() => {
							if (backgroundImageUrl !== null) backgroundImageUrl = null;
							else fileInput?.click();
						}}
					>
						<span class="ml-2 self-center">
							{backgroundImageUrl === null ? '上传' : '重置'}
						</span>
					</button>
				</div>

				{#if backgroundImageUrl}
					<div
						class="mt-2 h-24 overflow-hidden rounded-xl border border-white/10 bg-cover bg-center"
						style={`background-image:url(${backgroundImageUrl})`}
					></div>
				{/if}

				<hr class="my-2.5 w-full border-gray-800/80" />

				<div class="my-1">
					<div class="mb-2 text-xs text-gray-500">系统提示词</div>
					<textarea
						class="max-h-[200px] min-h-[88px] w-full resize-y bg-transparent text-sm outline-none placeholder:text-gray-600"
						placeholder={`请在此填写模型的系统提示词\n例如：你是《超级马里奥兄弟》中的马里奥（Mario），扮演助理的角色。`}
						bind:value={systemPrompt}
					></textarea>
				</div>

				<div class="my-2">
					<div class="mb-2 flex w-full justify-between">
						<div class="mb-1 text-xs text-gray-500">知识库</div>
					</div>

					{#if knowledgeItems.length > 0}
						<div class="mb-2.5 flex flex-wrap items-center gap-2">
							{#each knowledgeItems as item (item.id)}
								<span
									class="inline-flex max-w-full items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2 py-1 text-xs text-gray-200"
								>
									<span class="truncate">{item.name}</span>
									<button
										type="button"
										class="text-gray-500 hover:text-white"
										aria-label="移除"
										onclick={() => removeKnowledge(item.id)}
									>
										×
									</button>
								</span>
							{/each}
						</div>
					{/if}

					<div class="relative flex flex-row flex-wrap gap-1 text-sm">
						<button
							type="button"
							class="rounded-full border border-white/15 bg-transparent px-3 py-1 text-xs text-gray-200 transition hover:bg-white/[0.06]"
							onclick={() => {
								showKnowledgePicker = !showKnowledgePicker;
							}}
						>
							选择知识
						</button>
						<button
							type="button"
							class="rounded-full border border-white/15 bg-transparent px-3 py-1 text-xs text-gray-200 transition hover:bg-white/[0.06]"
							onclick={() => knowledgeFileInput?.click()}
						>
							上传文件
						</button>

						{#if showKnowledgePicker}
							<div
								class="absolute top-9 left-0 z-20 max-h-48 w-64 overflow-y-auto rounded-xl border border-white/10 bg-[#1f1f1f] py-1 shadow-xl"
							>
								{#if knowledgeOptions.length === 0}
									<div class="px-3 py-2 text-xs text-gray-500">暂无可用知识库</div>
									<button
										type="button"
										class="w-full px-3 py-1.5 text-left text-xs text-sky-400 hover:bg-white/[0.06]"
										onclick={() => {
											showKnowledgePicker = false;
											onOpenWorkspaceKnowledge();
										}}
									>
										前往工作空间添加
									</button>
								{:else}
									{#each knowledgeOptions as option (option.id)}
										<button
											type="button"
											class="flex w-full truncate px-3 py-1.5 text-left text-xs hover:bg-white/[0.06] disabled:opacity-40"
											disabled={knowledgeItems.some((item) => item.id === option.id)}
											onclick={() => addKnowledge(option)}
										>
											{option.name}
										</button>
									{/each}
								{/if}
							</div>
						{/if}
					</div>

					<input
						bind:this={knowledgeFileInput}
						type="file"
						hidden
						multiple
						onchange={onUploadKnowledgeFiles}
					/>

					<div class="mt-2 text-[11px] leading-4 text-gray-500">
						如需在此处附加知识库，请先将其添加到工作空间中的“知识库”中
					</div>
				</div>

				<div class="flex justify-end gap-1.5 pt-3 text-sm font-medium">
					<button
						type="button"
						class="flex items-center rounded-full bg-white px-3.5 py-1.5 text-sm font-medium text-black transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
						disabled={!name.trim()}
						onclick={submit}
					>
						{confirmLabel}
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}
