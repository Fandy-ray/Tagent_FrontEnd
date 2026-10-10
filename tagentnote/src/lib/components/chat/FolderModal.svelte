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
		knowledgeItems = [...knowledgeItems, { id: option.id, name: option.name, type: 'collection' }];
		showKnowledgePicker = false;
	};

	const removeKnowledge = (id: string) => {
		knowledgeItems = knowledgeItems.filter((item) => item.id !== id);
	};

	// 占位文字要换行：写在引号里的属性值里 \n 不转义、&#10; 也会被并成空格，所以放在这里
	const SYSTEM_PROMPT_PLACEHOLDER =
		'请在此填写模型的系统提示词\n例如：你是《超级马里奥兄弟》中的马里奥（Mario），扮演助理的角色。';
</script>

{#if open}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-[90] flex items-center justify-center bg-black/60 px-4"
		onclick={onClose}
	>
		<div
			class="bg-gray-850 max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-2xl border border-gray-800 text-gray-100 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			tabindex="-1"
			role="dialog"
			aria-modal="true"
			aria-label={title}
		>
			<div class="flex justify-between px-5 pt-3 pb-1 text-gray-300">
				<div class="self-center text-base font-medium">{title}</div>
				<button type="button" class="self-center" onclick={onClose} aria-label="关闭">
					<svg
						class="size-4"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="1.8"
					>
						<path stroke-linecap="round" d="M6 6l12 12M18 6L6 18"></path>
					</svg>
				</button>
			</div>

			<div class="flex w-full flex-col gap-1 px-5 pb-3 text-gray-200">
				<div class="flex w-full flex-col">
					<div class="mb-0.5 text-[11px] text-gray-500">分组名称</div>
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

				<div class="flex w-full items-center justify-between">
					<div class="text-[11px] text-gray-500">分组背景图</div>
					<button
						type="button"
						class="flex rounded-sm px-2.5 py-0.5 text-[11px] transition hover:bg-gray-800"
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
						class="mt-1 h-20 overflow-hidden rounded-xl border border-white/10 bg-cover bg-center"
						style={`background-image:url(${backgroundImageUrl})`}
					></div>
				{/if}

				<hr class="my-1.5 w-full border-gray-800/80" />

				<div>
					<div class="mb-1 text-[11px] text-gray-500">系统提示词</div>
					<textarea
						class="max-h-[180px] min-h-[72px] w-full resize-y bg-transparent text-sm outline-none placeholder:text-gray-600"
						placeholder={SYSTEM_PROMPT_PLACEHOLDER}
						bind:value={systemPrompt}></textarea>
				</div>

				<div>
					<div class="mb-1 flex w-full justify-between">
						<div class="text-[11px] text-gray-500">知识库</div>
					</div>

					{#if knowledgeItems.length > 0}
						<div class="mb-1.5 flex flex-wrap items-center gap-1.5">
							{#each knowledgeItems as item (item.id)}
								<span
									class="inline-flex max-w-full items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[11px] text-gray-200"
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
							class="rounded-full border border-white/15 bg-transparent px-2.5 py-0.5 text-[11px] text-gray-200 transition hover:bg-white/[0.06]"
							onclick={() => {
								showKnowledgePicker = !showKnowledgePicker;
							}}
						>
							选择知识
						</button>

						{#if showKnowledgePicker}
							<div
								class="absolute top-7 left-0 z-20 max-h-48 w-64 overflow-y-auto rounded-xl border border-white/10 bg-gray-900 py-1 shadow-xl"
							>
								{#if knowledgeOptions.length === 0}
									<div class="px-3 py-1.5 text-[11px] text-gray-500">
										暂无可用笔记本（OpenNoteBook 为空或未连接）
									</div>
									<button
										type="button"
										class="w-full px-3 py-1.5 text-left text-[11px] text-sky-400 hover:bg-white/[0.06]"
										onclick={() => {
											showKnowledgePicker = false;
											onOpenWorkspaceKnowledge();
										}}
									>
										前往笔记本添加
									</button>
								{:else}
									{#each knowledgeOptions as option (option.id)}
										<button
											type="button"
											class="flex w-full truncate px-3 py-1.5 text-left text-[11px] hover:bg-white/[0.06] disabled:opacity-40"
											disabled={knowledgeItems.some((item) => item.id === option.id)}
											onclick={() => addKnowledge(option)}
										>
											{option.name}
										</button>
									{/each}
									<button
										type="button"
										class="w-full border-t border-white/10 px-3 py-1.5 text-left text-[11px] text-sky-400 hover:bg-white/[0.06]"
										onclick={() => {
											showKnowledgePicker = false;
											onOpenWorkspaceKnowledge();
										}}
									>
										前往笔记本添加更多 →
									</button>
								{/if}
							</div>
						{/if}
					</div>

					<div class="mt-1.5 text-[10px] leading-4 text-gray-500">
						这里绑定的是 OpenNoteBook 笔记本，去笔记本里上传解析后，再用“选择知识”绑定
					</div>
				</div>

				<div class="flex justify-end gap-1.5 pt-2 text-sm font-medium">
					<button
						type="button"
						class="flex items-center rounded-lg bg-white px-3 py-1 text-xs font-medium text-black transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
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
