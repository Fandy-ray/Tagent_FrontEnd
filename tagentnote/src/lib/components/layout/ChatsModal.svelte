<script lang="ts">
	import Modal from '$lib/components/common/Modal.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';

	export type ChatRow = {
		id: string;
		title: string;
		updatedAt: number;
		shared?: boolean;
		shareId?: string;
		archived?: boolean;
	};

	type Props = {
		show?: boolean;
		title?: string;
		emptyPlaceholder?: string;
		shareUrl?: boolean;
		readOnly?: boolean;
		chats: ChatRow[] | null;
		onUnarchive?: (id: string) => void;
		onUnshare?: (id: string) => void;
		onDelete?: (id: string) => void;
		onUpdate?: () => void;
	};

	let {
		show = $bindable(false),
		title = 'Chats',
		emptyPlaceholder = '没有找到对话',
		shareUrl = false,
		readOnly = false,
		chats,
		onUnarchive,
		onUnshare,
		onDelete = () => {},
		onUpdate = () => {}
	}: Props = $props();

	let query = $state('');
	let orderBy = $state<'title' | 'updated_at'>('updated_at');
	let direction = $state<'asc' | 'desc'>('desc');
	let selectedChatId = $state<string | null>(null);
	let showDeleteConfirmDialog = $state(false);

	const setSortKey = (key: 'title' | 'updated_at') => {
		if (orderBy === key) {
			direction = direction === 'asc' ? 'desc' : 'asc';
		} else {
			orderBy = key;
			direction = 'asc';
		}
	};

	const filteredChats = $derived.by(() => {
		if (!chats) return null;
		const lower = query.trim().toLowerCase();
		const list = lower ? chats.filter((c) => c.title.toLowerCase().includes(lower)) : chats;
		const sorted = [...list].sort((a, b) => {
			const av = orderBy === 'title' ? a.title.toLowerCase() : a.updatedAt;
			const bv = orderBy === 'title' ? b.title.toLowerCase() : b.updatedAt;
			return direction === 'asc' ? (av > bv ? 1 : -1) : av < bv ? 1 : -1;
		});
		return sorted;
	});

	const formatRelative = (ts: number): string => {
		const diff = Date.now() - ts;
		const minute = 60_000;
		const hour = 60 * minute;
		const day = 24 * hour;
		if (diff < minute) return '刚刚';
		if (diff < hour) return `${Math.floor(diff / minute)} 分钟前`;
		if (diff < day) return `${Math.floor(diff / hour)} 小时前`;
		if (diff < 7 * day) return `${Math.floor(diff / day)} 天前`;
		const d = new Date(ts);
		return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
	};

	const copyShareLink = async (shareId: string) => {
		try {
			await navigator.clipboard.writeText(`${window.location.origin}/s/${shareId}`);
		} catch {
			// ignore
		}
	};

	const requestDelete = (id: string) => {
		selectedChatId = id;
		showDeleteConfirmDialog = true;
	};

	const handleConfirmDelete = () => {
		if (selectedChatId) {
			onDelete(selectedChatId);
		}
		selectedChatId = null;
		showDeleteConfirmDialog = false;
		onUpdate();
	};
</script>

<ConfirmDialog
	bind:show={showDeleteConfirmDialog}
	title="删除对话"
	message="删除后无法恢复，是否继续？"
	confirmLabel="删除"
	cancelLabel="取消"
	onConfirm={handleConfirmDelete}
	onCancel={() => {
		showDeleteConfirmDialog = false;
		selectedChatId = null;
	}}
/>

<Modal size="lg" bind:show>
	<div>
		<div class="flex justify-between px-5 pt-4 pb-1 text-gray-300">
			<div class="self-center text-lg font-medium">{title}</div>
			<button
				aria-label="关闭"
				class="self-center"
				onclick={() => {
					show = false;
				}}
				type="button"
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="h-5 w-5"
				>
					<path
						fill-rule="evenodd"
						d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
						clip-rule="evenodd"
					/>
				</svg>
			</button>
		</div>

		<div class="flex w-full flex-col px-5 pb-4 text-gray-200">
			<div class="mt-0.5 mb-1.5 flex w-full space-x-2">
				<div class="flex flex-1">
					<div class="self-center ml-1 mr-3">
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 20 20"
							fill="currentColor"
							class="h-4 w-4"
						>
							<path
								fill-rule="evenodd"
								d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
								clip-rule="evenodd"
							/>
						</svg>
					</div>
					<input
						class="w-full rounded-r-xl bg-transparent py-1 pr-4 text-sm outline-hidden"
						bind:value={query}
						placeholder="搜索对话"
						maxlength="500"
					/>
				</div>
			</div>

			<div class="flex flex-col w-full">
				{#if filteredChats !== null}
					{#if filteredChats.length > 0}
						<div class="mb-1.5 flex text-xs font-medium">
							<button
								class="basis-3/5 cursor-pointer select-none px-1.5 py-1"
								onclick={() => setSortKey('title')}
								type="button"
							>
								<div class="flex items-center gap-1.5">
									标题
									<span class="font-normal">
										{#if orderBy === 'title'}
											{#if direction === 'asc'}↑{:else}↓{/if}
										{:else}
											&nbsp;
										{/if}
									</span>
								</div>
							</button>
							<button
								class="hidden basis-2/5 cursor-pointer select-none justify-end px-1.5 py-1 sm:flex"
								onclick={() => setSortKey('updated_at')}
								type="button"
							>
								<div class="flex items-center gap-1.5">
									更新时间
									<span class="font-normal">
										{#if orderBy === 'updated_at'}
											{#if direction === 'asc'}↑{:else}↓{/if}
										{:else}
											&nbsp;
										{/if}
									</span>
								</div>
							</button>
						</div>
					{/if}

					<div class="mb-3 max-h-[22rem] w-full overflow-y-scroll text-left text-sm">
						{#if filteredChats.length === 0}
							<div
								class="flex h-full min-h-20 w-full items-center justify-center px-5 text-center text-xs text-gray-500"
							>
								{emptyPlaceholder}
							</div>
						{/if}

						{#each filteredChats as chat (chat.id)}
							<div
								role="button"
								tabindex="0"
								class="flex w-full items-center rounded-lg px-3 py-2 text-sm hover:bg-gray-850"
								onclick={() => {
									if (shareUrl && chat.shareId) {
										void copyShareLink(chat.shareId);
									}
								}}
								onkeydown={(event) => {
									if (event.key === 'Enter' || event.key === ' ') {
										event.preventDefault();
									}
								}}
							>
								<div class="basis-3/5 min-w-0">
									<div class="line-clamp-1 text-ellipsis">{chat.title}</div>
								</div>
								<div class="basis-2/5 flex items-center justify-end">
									<div class="hidden text-xs text-gray-500 sm:flex">
										{formatRelative(chat.updatedAt)}
									</div>

									{#if !readOnly}
										<div class="flex justify-end pl-2.5 text-gray-400">
											{#if onUnarchive}
												<button
													type="button"
													class="w-fit rounded-xl px-1 text-sm hover:text-gray-200"
													title="取消归档"
													onclick={(e) => {
														e.stopPropagation();
														onUnarchive(chat.id);
														onUpdate();
													}}
												>
													<svg
														xmlns="http://www.w3.org/2000/svg"
														fill="none"
														viewBox="0 0 24 24"
														stroke-width="1.5"
														stroke="currentColor"
														class="size-4"
													>
														<path
															stroke-linecap="round"
															stroke-linejoin="round"
															d="M9 8.25H7.5a2.25 2.25 0 0 0-2.25 2.25v9a2.25 2.25 0 0 0 2.25 2.25h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25H15m0-3-3-3m0 0-3 3m3-3V15"
														></path>
													</svg>
												</button>
											{/if}

											{#if onUnshare && chat.shareId}
												<button
													type="button"
													class="w-fit rounded-xl px-1 text-sm hover:text-gray-200"
													title="复制分享链接"
													onclick={(e) => {
														e.stopPropagation();
														void copyShareLink(chat.shareId!);
													}}
												>
													<svg
														xmlns="http://www.w3.org/2000/svg"
														viewBox="0 0 20 20"
														fill="currentColor"
														class="size-4"
													>
														<path
															d="M12.232 4.232a2.5 2.5 0 0 1 3.536 3.536l-1.591 1.59-.707-.707 1.591-1.59a1.5 1.5 0 0 0-2.121-2.122l-1.591 1.59-.707-.706 1.59-1.59Z"
														></path>
														<path
															d="M7.768 15.768a2.5 2.5 0 0 1-3.536-3.536l1.591-1.59.707.707-1.59 1.59a1.5 1.5 0 0 0 2.121 2.122l1.591-1.59.707.706-1.59 1.59Z"
														></path>
													</svg>
												</button>
												<button
													type="button"
													class="w-fit rounded-xl px-1 text-sm hover:text-red-400"
													title="取消分享"
													onclick={(e) => {
														e.stopPropagation();
														onUnshare(chat.id);
														onUpdate();
													}}
												>
													<svg
														xmlns="http://www.w3.org/2000/svg"
														viewBox="0 0 24 24"
														fill="none"
														stroke="currentColor"
														stroke-width="1.5"
														class="size-4"
													>
														<path
															stroke-linecap="round"
															stroke-linejoin="round"
															d="M13.19 8.688a4.5 4.5 0 0 1 1.242 7.244l-4.5 4.5a4.5 4.5 0 0 1-6.364-6.364l1.757-1.757m9.193-3.193 1.757-1.757a4.5 4.5 0 0 0-6.364-6.364L4.757 7.05"
														></path>
														<line
															x1="3"
															y1="3"
															x2="21"
															y2="21"
														></line>
													</svg>
												</button>
											{/if}

											<button
												type="button"
												class="w-fit rounded-xl px-1 text-sm hover:text-red-400"
												title="删除对话"
												onclick={(e) => {
													e.stopPropagation();
													requestDelete(chat.id);
												}}
											>
												<svg
													xmlns="http://www.w3.org/2000/svg"
													fill="none"
													viewBox="0 0 24 24"
													stroke-width="1.5"
													stroke="currentColor"
													class="h-4 w-4"
												>
													<path
														stroke-linecap="round"
														stroke-linejoin="round"
														d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"
													></path>
												</svg>
											</button>
										</div>
									{/if}
								</div>
							</div>
						{/each}
					</div>
				{:else}
					<div class="flex min-h-20 w-full items-center justify-center text-xs text-gray-500">
						加载中…
					</div>
				{/if}
			</div>
		</div>
	</div>
</Modal>
