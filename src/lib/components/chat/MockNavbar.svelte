<script lang="ts">
	import ChatOverflowMenu from './ChatOverflowMenu.svelte';
	import UserMenu from '$lib/components/layout/UserMenu.svelte';

	type MockModel = {
		id: string;
		name: string;
	};

	type NotebookOption = {
		id: string;
		name: string;
		// OpenNoteBook 的 description 可以是 null，别把它收窄成 string。
		description?: string | null;
		noteCount?: number;
	};

	type AssistMode = 'qa' | 'paper';

	type Props = {
		sidebarOpen?: boolean;
		selectedModelId?: string;
		models?: MockModel[];
		collectionId?: string;
		notebooks?: NotebookOption[];
		notebooksLoading?: boolean;
		assistMode?: AssistMode;
		temporaryChat?: boolean;
		hasMessages?: boolean;
		controlsOpen?: boolean;
		userName?: string;
		avatarText?: string;
		onOpenSidebar?: () => void;
		onNewChat?: () => void;
		onOpenExam?: () => void;
		onHome?: () => void;
		onModelChange?: () => void;
		onCollectionChange?: (collectionId: string) => void;
		onAssistModeChange?: (mode: AssistMode) => void;
		onToggleTemporaryChat?: () => void;
		onSaveTemporaryChat?: () => void;
		onToggleControls?: () => void;
		onSettings?: () => void;
		onArchivedChats?: () => void;
		onPlayground?: () => void;
		onAdmin?: () => void;
		onShortcuts?: () => void;
		onSignOut?: () => void;
		onShareChat?: () => void;
		onDownloadChat?: () => void;
		onCopyChat?: () => void;
		onArchiveChat?: () => void;
		onAddChatTag?: (tag: string) => void;
		folders?: { id: string; name: string }[];
		onMoveChatToFolder?: (folderId: string | null) => void;
	};

	const ALL_NOTEBOOKS: NotebookOption = {
		id: '',
		name: '全部笔记本',
		description: '检索所有笔记本和本地教材'
	};

	let {
		sidebarOpen = true,
		selectedModelId = $bindable(''),
		models = [],
		collectionId = '',
		notebooks = [],
		notebooksLoading = false,
		assistMode = 'qa',
		temporaryChat = false,
		hasMessages = false,
		controlsOpen = false,
		userName = 'Tagent',
		avatarText = 'T',
		onOpenSidebar = () => {},
		onNewChat = () => {},
		onOpenExam = () => {},
		onHome = () => {},
		onModelChange = () => {},
		onCollectionChange = () => {},
		onAssistModeChange = () => {},
		onToggleTemporaryChat = () => {},
		onSaveTemporaryChat = () => {},
		onToggleControls = () => {},
		onSettings = () => {},
		onArchivedChats = () => {},
		onPlayground = () => {},
		onAdmin = () => {},
		onShortcuts = () => {},
		onSignOut = () => {},
		onShareChat = () => {},
		onDownloadChat = () => {},
		onCopyChat = () => {},
		onArchiveChat = () => {},
		onAddChatTag = () => {},
		folders = [],
		onMoveChatToFolder = () => {}
	}: Props = $props();

	let modelMenuOpen = $state(false);
	let collectionMenuOpen = $state(false);
	let modelTriggerEl = $state<HTMLDivElement | null>(null);
	let modelMenuEl = $state<HTMLDivElement | null>(null);
	let modelMenuStyle = $state('');
	let collectionTriggerEl = $state<HTMLDivElement | null>(null);
	let collectionMenuEl = $state<HTMLDivElement | null>(null);
	let collectionMenuStyle = $state('');

	const notebookOptions = $derived([ALL_NOTEBOOKS, ...notebooks]);

	const currentCollection = $derived(
		notebookOptions.find((collection) => collection.id === collectionId) ?? ALL_NOTEBOOKS
	);

	const currentModelName = $derived(
		models.find((model) => model.id === selectedModelId)?.name ?? '选择模型'
	);

	const portal = (node: HTMLElement) => {
		document.body.appendChild(node);
		return {
			destroy() {
				node.remove();
			}
		};
	};

	const placeMenu = (
		trigger: HTMLElement | null,
		align: 'start' | 'end',
		minWidth = 208
	) => {
		if (!trigger) return '';
		const rect = trigger.getBoundingClientRect();
		let left = align === 'end' ? rect.right - minWidth : rect.left;
		left = Math.max(8, Math.min(left, window.innerWidth - minWidth - 8));
		return `position:fixed;left:${left}px;top:${rect.bottom + 4}px;min-width:${minWidth}px;z-index:100;`;
	};

	const toggleModelMenu = () => {
		modelMenuOpen = !modelMenuOpen;
		collectionMenuOpen = false;
		if (modelMenuOpen) {
			modelMenuStyle = placeMenu(modelTriggerEl, 'start');
		}
	};

	const selectModel = (modelId: string) => {
		selectedModelId = modelId;
		modelMenuOpen = false;
		onModelChange();
	};

	const selectCollection = (collection: NotebookOption) => {
		collectionMenuOpen = false;
		onCollectionChange(collection.id);
	};

	const toggleCollectionMenu = () => {
		collectionMenuOpen = !collectionMenuOpen;
		modelMenuOpen = false;
		if (collectionMenuOpen) {
			collectionMenuStyle = placeMenu(collectionTriggerEl, 'end');
		}
	};

	$effect(() => {
		if (!modelMenuOpen && !collectionMenuOpen) return;

		const onPointerDown = (event: PointerEvent) => {
			const target = event.target as Node;
			if (modelMenuOpen) {
				if (modelTriggerEl?.contains(target) || modelMenuEl?.contains(target)) return;
				modelMenuOpen = false;
			}
			if (collectionMenuOpen) {
				if (collectionTriggerEl?.contains(target) || collectionMenuEl?.contains(target)) return;
				collectionMenuOpen = false;
			}
		};
		const onKeyDown = (event: KeyboardEvent) => {
			if (event.key === 'Escape') {
				modelMenuOpen = false;
				collectionMenuOpen = false;
			}
		};
		const onReposition = () => {
			if (modelMenuOpen) modelMenuStyle = placeMenu(modelTriggerEl, 'start');
			if (collectionMenuOpen) collectionMenuStyle = placeMenu(collectionTriggerEl, 'end');
		};

		const timer = window.setTimeout(() => {
			window.addEventListener('pointerdown', onPointerDown, true);
			window.addEventListener('keydown', onKeyDown);
			window.addEventListener('resize', onReposition);
			window.addEventListener('scroll', onReposition, true);
		}, 0);

		return () => {
			window.clearTimeout(timer);
			window.removeEventListener('pointerdown', onPointerDown, true);
			window.removeEventListener('keydown', onKeyDown);
			window.removeEventListener('resize', onReposition);
			window.removeEventListener('scroll', onReposition, true);
		};
	});
</script>

<nav
	class="sticky top-0 z-30 flex w-full shrink-0 flex-col items-center overflow-visible border-b border-white/[0.04] bg-[#171717] pt-1 pb-1"
	aria-label="聊天顶部导航"
>
	<div class="flex w-full items-center px-1.5 pr-1">
		<div class="mx-auto flex w-full max-w-full bg-transparent px-1.5 pt-0.5 md:px-2">
			<div class="flex w-full max-w-full items-center">
				{#if !sidebarOpen}
					<div class="mr-1 mt-1 flex flex-none -translate-x-0.5 self-start items-center text-gray-400">
						<button
							type="button"
							class="flex cursor-pointer rounded-lg transition hover:bg-gray-850"
							onclick={onOpenSidebar}
							title="打开侧边栏"
							aria-label="打开侧边栏"
						>
							<div class="self-center p-1.5">
								<svg
									class="size-5"
									viewBox="0 0 24 24"
									fill="none"
									stroke="currentColor"
									stroke-width="1.5"
									stroke-linecap="round"
									stroke-linejoin="round"
									aria-hidden="true"
								>
									<rect x="3" y="4" width="18" height="16" rx="2"></rect>
									<path d="M9 4v16"></path>
								</svg>
							</div>
						</button>
					</div>
				{/if}

				<div class={`mt-0.5 flex-1 overflow-visible py-0.5 ${sidebarOpen ? 'ml-1' : ''}`}>
					<div class="relative flex w-full flex-col items-start">
						<div class="flex w-full max-w-fit">
							<div class="w-full overflow-visible">
								<div class="mr-1 max-w-full" bind:this={modelTriggerEl}>
									<button
										type="button"
										id="model-selector-0-button"
										class="flex max-w-[240px] items-center gap-1 rounded-lg px-1.5 py-1 text-left text-sm text-gray-200 transition hover:bg-gray-850"
										onclick={toggleModelMenu}
										aria-expanded={modelMenuOpen}
										aria-haspopup="listbox"
									>
										<span class="truncate">{currentModelName}</span>
										<svg
											class={`size-3.5 shrink-0 text-gray-500 transition ${
												modelMenuOpen ? 'rotate-180' : ''
											}`}
											viewBox="0 0 24 24"
											fill="none"
											stroke="currentColor"
											stroke-width="2"
											stroke-linecap="round"
											stroke-linejoin="round"
											aria-hidden="true"
										>
											<path d="m6 9 6 6 6-6"></path>
										</svg>
									</button>
								</div>
							</div>
						</div>
					</div>
				</div>

				<div class="flex min-w-0 flex-none items-center self-start text-gray-400">
					{#if !controlsOpen}
						<div
							class="mr-1 mt-1 inline-flex rounded-full border border-white/10 bg-white/[0.03] p-0.5 text-[11px]"
							role="group"
							aria-label="答疑模式"
						>
							<button
								type="button"
								class={`rounded-full px-2.5 py-1 transition ${
									assistMode === 'qa'
										? 'bg-white/10 text-white'
										: 'text-gray-400 hover:text-gray-200'
								}`}
								onclick={() => onAssistModeChange('qa')}
							>
								课程答疑
							</button>
							<button
								type="button"
								class={`rounded-full px-2.5 py-1 transition ${
									assistMode === 'paper'
										? 'bg-amber-500/20 text-amber-100'
										: 'text-gray-400 hover:text-gray-200'
								}`}
								onclick={() => onAssistModeChange('paper')}
							>
								论文辅助
							</button>
						</div>

						<div class="relative mr-1" bind:this={collectionTriggerEl}>
							<button
								type="button"
								class="mt-1 flex max-w-[180px] items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[11px] text-gray-200 transition hover:bg-white/[0.08]"
								onclick={toggleCollectionMenu}
								title="当前知识库"
								aria-expanded={collectionMenuOpen}
							>
								<svg
									class="size-3.5 shrink-0"
									viewBox="0 0 24 24"
									fill="none"
									stroke="currentColor"
									stroke-width="1.8"
									aria-hidden="true"
								>
									<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
								</svg>
								<span class="truncate">{currentCollection.name}</span>
							</button>
						</div>
					{/if}

					{#if temporaryChat && hasMessages}
						<button
							type="button"
							class="flex cursor-pointer rounded-xl px-2 py-2 text-gray-400 transition hover:bg-gray-850 hover:text-white"
							onclick={onSaveTemporaryChat}
							title="保存临时对话"
							aria-label="保存临时对话"
							id="save-temporary-chat-button"
						>
							<svg
								class="size-[18px]"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="1.5"
								stroke-linecap="round"
								stroke-linejoin="round"
								aria-hidden="true"
							>
								<path d="M8 12L11 15L16 10"></path>
								<path
									d="M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 13.8214 2.48697 15.5291 3.33782 17L2.5 21.5L7 20.6622C8.47087 21.513 10.1786 22 12 22Z"
								></path>
							</svg>
						</button>
					{:else if !hasMessages || temporaryChat}
						<button
							type="button"
							class={`flex cursor-pointer rounded-xl px-2 py-2 transition hover:bg-gray-850 ${
								temporaryChat ? 'text-amber-200' : 'text-gray-400 hover:text-white'
							}`}
							onclick={onToggleTemporaryChat}
							title={temporaryChat ? '关闭临时对话' : '临时对话'}
							aria-label={temporaryChat ? '关闭临时对话' : '临时对话'}
							aria-pressed={temporaryChat}
							id="temporary-chat-button"
						>
							<svg
								class="size-[18px]"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="1.5"
								stroke-linecap="round"
								stroke-linejoin="round"
								aria-hidden="true"
							>
								{#if temporaryChat}
									<path d="M8 12L11 15L16 10"></path>
								{/if}
								<path
									d="M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 13.8214 2.48697 15.5291 3.33782 17L2.5 21.5L7 20.6622C8.47087 21.513 10.1786 22 12 22Z"
									stroke-dasharray="2.5 3.5"
								></path>
							</svg>
						</button>
					{/if}

					<ChatOverflowMenu
						onShare={onShareChat}
						onDownload={onDownloadChat}
						onCopy={onCopyChat}
						onArchive={onArchiveChat}
						onAddTag={onAddChatTag}
						{folders}
						onMoveToFolder={onMoveChatToFolder}
					/>

					<button
						type="button"
						class="flex cursor-pointer rounded-xl px-2 py-2 transition hover:bg-gray-850"
						onclick={onOpenExam}
						title="智能测评"
						aria-label="智能测评"
					>
						<svg
							class="size-5"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="1.5"
							stroke-linecap="round"
							stroke-linejoin="round"
							aria-hidden="true"
						>
							<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
							<path d="M14 2v6h6"></path>
							<path d="m9 15 2 2 4-4"></path>
						</svg>
					</button>

					<button
						type="button"
						class={`flex cursor-pointer rounded-xl px-2 py-2 transition hover:bg-gray-850 ${
							controlsOpen ? 'text-white' : 'text-gray-400 hover:text-white'
						}`}
						onclick={onToggleControls}
						title="控制"
						aria-label="控制"
						aria-pressed={controlsOpen}
						id="chat-controls-button"
					>
						<svg
							class="size-5"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="1"
							stroke-linecap="round"
							stroke-linejoin="round"
							aria-hidden="true"
						>
							<path
								d="M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-9.75 0h9.75"
							></path>
						</svg>
					</button>

					<UserMenu
						variant="navbar"
						className="w-[240px]"
						userRole="admin"
						userName={userName}
						avatarText={avatarText}
						align="end"
						placement="bottom"
						onSettings={onSettings}
						onArchivedChats={onArchivedChats}
						onPlayground={onPlayground}
						onAdmin={onAdmin}
						onShortcuts={onShortcuts}
						onSignOut={onSignOut}
					/>
				</div>
			</div>
		</div>
	</div>
</nav>

{#if modelMenuOpen}
	<div
		bind:this={modelMenuEl}
		use:portal
		class="rounded-xl border border-gray-800 bg-gray-900 p-1.5 text-white shadow-2xl shadow-black/40"
		style={modelMenuStyle}
		role="listbox"
		aria-label="选择模型"
	>
		{#if models.length === 0}
			<p class="px-3 py-2 text-xs text-gray-500">basic-agent 没有返回可用模型。</p>
		{/if}
		{#each models as model (model.id)}
			<button
				type="button"
				class={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition ${
					selectedModelId === model.id
						? 'bg-gray-800 text-white'
						: 'text-gray-300 hover:bg-gray-800'
				}`}
				onclick={() => selectModel(model.id)}
				role="option"
				aria-selected={selectedModelId === model.id}
			>
				<span>{model.name}</span>
				{#if selectedModelId === model.id}
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
						<path d="m5 12 4 4L19 6"></path>
					</svg>
				{/if}
			</button>
		{/each}
	</div>
{/if}

{#if collectionMenuOpen}
	<div
		bind:this={collectionMenuEl}
		use:portal
		class="max-h-[min(24rem,70vh)] overflow-y-auto rounded-xl border border-gray-800 bg-gray-900 p-1.5 text-white shadow-2xl shadow-black/40"
		style={collectionMenuStyle}
		role="listbox"
		aria-label="选择知识库"
	>
		{#if notebooksLoading && notebooks.length === 0}
			<p class="px-3 py-2 text-xs text-gray-500">正在读取笔记本…</p>
		{:else}
			{#each notebookOptions as collection (collection.id || 'all')}
				<button
					type="button"
					class={`flex w-full flex-col rounded-lg px-3 py-2 text-left transition ${
						collection.id === currentCollection.id
							? 'bg-gray-800 text-white'
							: 'text-gray-300 hover:bg-gray-800'
					}`}
					onclick={() => selectCollection(collection)}
				>
					<span class="text-sm">{collection.name}</span>
					<span class="text-[11px] text-gray-500">
						{collection.id ? `${collection.noteCount ?? 0} 条笔记` : '不限定范围'}
					</span>
				</button>
			{/each}
		{/if}
	</div>
{/if}
