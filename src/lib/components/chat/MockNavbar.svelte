<script lang="ts">
	type MockModel = {
		id: string;
		name: string;
	};

	type Props = {
		sidebarOpen?: boolean;
		selectedModelId?: string;
		hasActiveChat?: boolean;
		onOpenSidebar?: () => void;
		onNewChat?: () => void;
		onOpenExam?: () => void;
	};

	let {
		sidebarOpen = true,
		selectedModelId = $bindable('deepseek'),
		hasActiveChat = false,
		onOpenSidebar = () => {},
		onNewChat = () => {},
		onOpenExam = () => {}
	}: Props = $props();

	const models: MockModel[] = [
		{
			id: 'deepseek',
			name: 'deepseek'
		}
	];

	let modelMenuOpen = $state(false);
	let temporaryChatEnabled = $state(false);
	let controlsEnabled = $state(false);

	const toggleModelMenu = () => {
		modelMenuOpen = !modelMenuOpen;
	};

	const selectModel = (modelId: string) => {
		selectedModelId = modelId;
		modelMenuOpen = false;
	};

	const toggleTemporaryChat = () => {
		temporaryChatEnabled = !temporaryChatEnabled;
	};

	const toggleControls = () => {
		controlsEnabled = !controlsEnabled;
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

				<div
					class={`mt-0.5 flex-1 overflow-visible py-0.5 ${
						sidebarOpen ? 'ml-1' : ''
					}`}
				>
					<div class="relative flex w-full flex-col items-start">
						<div class="flex w-full max-w-fit">
							<div class="w-full overflow-visible">
								<div class="mr-1 max-w-full">
									<button
										type="button"
										class="flex max-w-[240px] items-center gap-1 rounded-lg px-1.5 py-1 text-left text-sm text-gray-200 transition hover:bg-gray-850"
										onclick={toggleModelMenu}
										aria-expanded={modelMenuOpen}
										aria-haspopup="listbox"
									>
										<span class="truncate">
											{models.find((model) => model.id === selectedModelId)?.name ??
												'选择模型'}
										</span>

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
											class="absolute left-0 top-9 z-50 min-w-52 rounded-xl border border-gray-800 bg-gray-900 p-1.5 shadow-2xl shadow-black/40"
											role="listbox"
											aria-label="选择模型"
										>
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

							<div class="mx-1 self-center -translate-y-[0.5px] text-gray-400">
								<button
									type="button"
									class="flex size-6 items-center justify-center rounded-md transition hover:bg-gray-850 hover:text-white"
									onclick={onNewChat}
									title="添加模型"
									aria-label="添加模型"
								>
									<svg
										class="size-3.5"
										viewBox="0 0 24 24"
										fill="none"
										stroke="currentColor"
										stroke-width="2"
										stroke-linecap="round"
										stroke-linejoin="round"
										aria-hidden="true"
									>
										<path d="M12 6v12M18 12H6"></path>
									</svg>
								</button>
							</div>
						</div>

						<div class="ml-1 mt-[1px] text-left text-[0.7rem] text-gray-500">
							<button type="button" class="transition hover:text-gray-300">
								设为默认
							</button>
						</div>
					</div>
				</div>

				<div class="flex flex-none items-center self-start text-gray-400">
					{#if !hasActiveChat}
						<button
							type="button"
							class={`flex cursor-pointer rounded-xl px-2 py-2 transition hover:bg-gray-850 ${
								temporaryChatEnabled ? 'text-white' : ''
							}`}
							onclick={toggleTemporaryChat}
							title={temporaryChatEnabled ? '关闭临时对话' : '临时对话'}
							aria-label={temporaryChatEnabled ? '关闭临时对话' : '临时对话'}
						>
							<div class="m-auto self-center">
								{#if temporaryChatEnabled}
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
										<circle cx="12" cy="12" r="8" stroke-dasharray="3 3"></circle>
										<path d="m8.5 12 2.2 2.2 4.8-5"></path>
									</svg>
								{:else}
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
										<circle cx="12" cy="12" r="8" stroke-dasharray="3 3"></circle>
									</svg>
								{/if}
							</div>
						</button>
					{:else}
						<button
							type="button"
							class="flex cursor-pointer rounded-xl px-2 py-2 transition hover:bg-gray-850"
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
								<path d="M4 4h16v16H4z"></path>
							</svg>
						</button>
					{/if}

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
							controlsEnabled ? 'text-white' : ''
						}`}
						onclick={toggleControls}
						title="控制项"
						aria-label="控制项"
					>
						<svg
							class="size-5"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="1.3"
							stroke-linecap="round"
							stroke-linejoin="round"
							aria-hidden="true"
						>
							<path d="M4 6h16"></path>
							<path d="M4 12h16"></path>
							<path d="M4 18h16"></path>
							<circle cx="8" cy="6" r="1.5" fill="currentColor"></circle>
							<circle cx="16" cy="12" r="1.5" fill="currentColor"></circle>
							<circle cx="10" cy="18" r="1.5" fill="currentColor"></circle>
						</svg>
					</button>

					<button
						type="button"
						class="flex select-none rounded-xl p-1.5 transition hover:bg-gray-850"
						title="用户菜单"
						aria-label="用户菜单"
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

	{#if temporaryChatEnabled}
		<div class="z-30 w-full text-center">
			<div class="text-xs text-gray-500">临时对话</div>
		</div>
	{/if}
</nav>