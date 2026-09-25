<script lang="ts">
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

	type Props = {
		sidebarOpen?: boolean;
		selectedModelId?: string;
		models?: MockModel[];
		collectionId?: string;
		notebooks?: NotebookOption[];
		notebooksLoading?: boolean;
		onOpenSidebar?: () => void;
		onNewChat?: () => void;
		onOpenExam?: () => void;
		onOpenEssay?: () => void;
		onHome?: () => void;
		onModelChange?: () => void;
		onCollectionChange?: (collectionId: string) => void;
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
		onOpenSidebar = () => {},
		onNewChat = () => {},
		onOpenExam = () => {},
		onOpenEssay = () => {},
		onHome = () => {},
		onModelChange = () => {},
		onCollectionChange = () => {}
	}: Props = $props();

	let modelMenuOpen = $state(false);
	let collectionMenuOpen = $state(false);

	const notebookOptions = $derived([ALL_NOTEBOOKS, ...notebooks]);

	const currentCollection = $derived(
		notebookOptions.find((collection) => collection.id === collectionId) ?? ALL_NOTEBOOKS
	);

	const currentModelName = $derived(
		models.find((model) => model.id === selectedModelId)?.name ?? '选择模型'
	);

	const toggleModelMenu = () => {
		modelMenuOpen = !modelMenuOpen;
		collectionMenuOpen = false;
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
</script>

<nav
	class="sticky top-0 z-30 -mb-12 flex w-full shrink-0 flex-col items-center pt-1 pb-1"
	aria-label="聊天顶部导航"
>
	<div class="flex w-full items-center px-1.5 pr-1">
		<div class="mx-auto flex w-full max-w-full bg-transparent px-1.5 pt-0.5 md:px-2">
			<div class="flex w-full max-w-full items-center">
				{#if !sidebarOpen}
					<div
						class="mt-1 mr-1 flex flex-none -translate-x-0.5 items-center self-start text-gray-400"
					>
						<button
							type="button"
							class="hover:bg-gray-850 flex cursor-pointer rounded-lg transition"
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
								<div class="mr-1 max-w-full">
									<button
										type="button"
										class="hover:bg-gray-850 flex max-w-[240px] items-center gap-1 rounded-lg px-1.5 py-1 text-left text-sm text-gray-200 transition"
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

									{#if modelMenuOpen}
										<div
											class="absolute top-9 left-0 z-50 min-w-52 rounded-xl border border-gray-800 bg-gray-900 p-1.5 shadow-2xl shadow-black/40"
											role="listbox"
											aria-label="选择模型"
										>
											{#if models.length === 0}
												<p class="px-3 py-2 text-xs text-gray-500">
													basic-agent 没有返回可用模型。
												</p>
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
								</div>
							</div>
						</div>
					</div>
				</div>

				<div class="flex flex-none items-center self-start text-gray-400">
					<div class="relative mr-1">
						<button
							type="button"
							class="mt-1 flex max-w-[180px] items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[11px] text-gray-200 transition hover:bg-white/[0.08]"
							onclick={() => {
								collectionMenuOpen = !collectionMenuOpen;
								modelMenuOpen = false;
							}}
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
								<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"
								></path>
							</svg>
							<span class="truncate">{currentCollection.name}</span>
						</button>

						{#if collectionMenuOpen}
							<div
								class="absolute top-9 right-0 z-50 min-w-52 rounded-xl border border-gray-800 bg-gray-900 p-1.5 shadow-2xl shadow-black/40"
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
					</div>
					<button
						type="button"
						class="hover:bg-gray-850 flex cursor-pointer rounded-xl px-2 py-2 transition"
						onclick={onNewChat}
						title="新对话"
						aria-label="新对话"
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
							<path d="M12 5v14M5 12h14"></path>
						</svg>
					</button>

					<button
						type="button"
						class="hover:bg-gray-850 flex cursor-pointer rounded-xl px-2 py-2 transition"
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
						class="hover:bg-gray-850 flex cursor-pointer rounded-xl px-2 py-2 transition"
						onclick={onOpenEssay}
						title="论文批改"
						aria-label="论文批改"
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
							<path d="M12 20h9"></path>
							<path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"></path>
						</svg>
					</button>

					<button
						type="button"
						class="hover:bg-gray-850 flex rounded-xl p-1.5 transition select-none"
						onclick={onHome}
						title="返回选择智能体"
						aria-label="返回选择智能体"
					>
						<div
							class="flex size-6 items-center justify-center rounded-full bg-amber-500 text-[9px] font-semibold text-white"
						>
							T
						</div>
					</button>
				</div>
			</div>
		</div>
	</div>
</nav>
