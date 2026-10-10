<script lang="ts">
	import { getI18nContext } from '$lib/i18n';
	const i18n = getI18nContext();

	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import Pencil from '$lib/components/icons/Pencil.svelte';
	import GarbageBin from '$lib/components/icons/GarbageBin.svelte';
	import Search from '$lib/components/icons/Search.svelte';
	import ChevronUp from '$lib/components/icons/ChevronUp.svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import AddMemoryModal from './AddMemoryModal.svelte';
	import EditMemoryModal from './EditMemoryModal.svelte';
	import {
		listMemories,
		deleteMemoriesByUserId,
		deleteMemoryById,
		type MemoryRecord
	} from './memoryStore';

	type Props = { show?: boolean };
	let { show = $bindable(false) }: Props = $props();

	let memories = $state<MemoryRecord[]>([]);
	let loading = $state(true);

	let query = $state('');
	let orderBy = $state<'content' | 'updated_at'>('updated_at');
	let direction = $state<'asc' | 'desc'>('desc');

	const setSortKey = (key: 'content' | 'updated_at') => {
		if (orderBy === key) {
			direction = direction === 'asc' ? 'desc' : 'asc';
		} else {
			orderBy = key;
			direction = 'asc';
		}
	};

	let showAddMemoryModal = $state(false);
	let showEditMemoryModal = $state(false);
	let selectedMemory = $state<MemoryRecord | null>(null);

	let showClearConfirmDialog = $state(false);
	let showDeleteConfirm = $state(false);

	const filteredMemories = $derived(
		query
			? memories.filter((m) => m.content?.toLowerCase().includes(query.toLowerCase()))
			: memories
	);

	const sortedMemories = $derived(
		[...filteredMemories].sort((a, b) => {
			let aVal: number | string;
			let bVal: number | string;
			if (orderBy === 'content') {
				aVal = (a.content ?? '').toLowerCase();
				bVal = (b.content ?? '').toLowerCase();
			} else {
				aVal = a.updatedAt ?? 0;
				bVal = b.updatedAt ?? 0;
			}
			if (direction === 'asc') {
				return aVal > bVal ? 1 : -1;
			}
			return aVal < bVal ? 1 : -1;
		})
	);

	const fmtDate = (ts: number) => {
		const d = new Date(ts * 1000);
		const mm = String(d.getMonth() + 1).padStart(2, '0');
		const dd = String(d.getDate()).padStart(2, '0');
		const hh = String(d.getHours()).padStart(2, '0');
		const mi = String(d.getMinutes()).padStart(2, '0');
		return `${mm}/${dd} ${hh}:${mi}`;
	};

	$effect(() => {
		const isOpen = show;
		if (isOpen && memories.length === 0 && loading) {
			(async () => {
				memories = await listMemories();
				loading = false;
			})();
		}
	});

	const onClearConfirmed = async () => {
		await deleteMemoriesByUserId(null);
		memories = await listMemories();
		showClearConfirmDialog = false;
	};

	const refresh = async () => {
		loading = true;
		memories = await listMemories();
		loading = false;
	};

	const deleteMessage = $derived(
		selectedMemory
			? `确定要删除这条记忆吗？该操作不可撤销。\n\n${selectedMemory.content}`
			: '确定要删除这条记忆吗？该操作不可撤销。'
	);
</script>

<Modal size="lg" bind:show>
	<div>
		<!-- Header -->
		<div class="flex justify-between px-5 pt-4 pb-1 text-gray-200">
			<div class="flex items-center gap-2">
				<div class="text-lg font-medium">记忆</div>

				{#if !loading}
					<div class="text-lg font-medium text-gray-500">
						{memories.length}
					</div>
				{/if}
			</div>

			<button class="self-center" onclick={() => (show = false)} aria-label="关闭">
				<XMark className="size-5" />
			</button>
		</div>

		<div class="flex w-full flex-col px-5 pb-4 text-gray-200">
			<!-- Search -->
			<div class="mb-1 flex w-full flex-1 items-center">
				<div class="mr-3 ml-1 self-center">
					<Search className="size-3.5" />
				</div>
				<input
					class="w-full rounded-r-xl bg-transparent py-1 text-sm outline-none"
					bind:value={query}
					placeholder="搜索记忆"
					maxlength="500"
				/>

				{#if query}
					<div class="translate-y-[0.5px] self-center bg-transparent pl-1.5">
						<button
							class="rounded-full p-0.5 transition hover:bg-gray-800"
							aria-label="清除搜索"
							onclick={() => {
								query = '';
							}}
						>
							<XMark className="size-3" />
						</button>
					</div>
				{/if}
			</div>

			<!-- Memories List -->
			<div class="flex w-full flex-col">
				{#if !loading}
					{#if sortedMemories.length === 0}
						<div
							class="flex min-h-20 w-full items-center justify-center px-5 text-center text-xs text-gray-400"
						>
							{#if memories.length === 0}
								LLM 可访问的记忆会显示在这里。
							{:else}
								{$i18n.t('No results found')}
							{/if}
						</div>
					{:else}
						{#if sortedMemories.length > 0}
							<div class="mb-1 flex text-xs font-medium">
								<button
									class="basis-3/5 cursor-pointer px-1.5 py-1 text-left select-none"
									onclick={() => setSortKey('content')}
								>
									<div class="flex items-center gap-1.5">
										内容
										{#if orderBy === 'content'}
											<span class="font-normal">
												{#if direction === 'asc'}
													<ChevronUp className="size-2" />
												{:else}
													<ChevronDown className="size-2" />
												{/if}
											</span>
										{:else}
											<span class="invisible">
												<ChevronUp className="size-2" />
											</span>
										{/if}
									</div>
								</button>
								<button
									class="hidden basis-2/5 cursor-pointer justify-end px-1.5 py-1 select-none sm:flex"
									onclick={() => setSortKey('updated_at')}
								>
									<div class="flex items-center gap-1.5">
										更新时间
										{#if orderBy === 'updated_at'}
											<span class="font-normal">
												{#if direction === 'asc'}
													<ChevronUp className="size-2" />
												{:else}
													<ChevronDown className="size-2" />
												{/if}
											</span>
										{:else}
											<span class="invisible">
												<ChevronUp className="size-2" />
											</span>
										{/if}
									</div>
								</button>
							</div>
						{/if}

						<div class="max-h-[28rem] w-full overflow-y-auto text-left text-sm">
							{#each sortedMemories as memory (memory.id)}
								<!-- svelte-ignore a11y_click_events_have_key_events -->
								<!-- svelte-ignore a11y_no_static_element_interactions -->
								<div
									role="button"
									tabindex="0"
									class="flex w-full cursor-pointer items-center justify-between rounded-xl px-3 py-2 text-sm transition hover:bg-gray-800"
									onclick={() => {
										selectedMemory = memory;
										showEditMemoryModal = true;
									}}
									onkeydown={(event) => {
										if (event.key === 'Enter' || event.key === ' ') {
											event.preventDefault();
											selectedMemory = memory;
											showEditMemoryModal = true;
										}
									}}
								>
									<div class="min-w-0 flex-1 pr-2">
										<div class="line-clamp-1 text-ellipsis">{memory.content}</div>
										<div class="text-xs text-gray-400">
											{fmtDate(memory.updatedAt)}
										</div>
									</div>

									<div class="flex shrink-0 items-center">
										<div class="mr-2 hidden text-xs whitespace-nowrap text-gray-400 sm:flex">
											{new Date(memory.updatedAt * 1000).toLocaleTimeString([], {
												hour: '2-digit',
												minute: '2-digit'
											})}
										</div>

										<div class="flex text-gray-300">
											<Tooltip content="编辑">
												<button
													class="w-fit self-center rounded-xl p-1.5 text-sm transition hover:bg-white/5"
													aria-label="编辑"
													onclick={(e) => {
														e.stopPropagation();
														selectedMemory = memory;
														showEditMemoryModal = true;
													}}
												>
													<Pencil className="size-4" />
												</button>
											</Tooltip>

											<Tooltip content="删除">
												<button
													class="w-fit self-center rounded-xl p-1.5 text-sm transition hover:bg-white/5"
													aria-label="删除"
													onclick={(e) => {
														e.stopPropagation();
														selectedMemory = memory;
														showDeleteConfirm = true;
													}}
												>
													<GarbageBin className="size-4" />
												</button>
											</Tooltip>
										</div>
									</div>
								</div>
							{/each}
						</div>
					{/if}
				{:else}
					<div class="flex min-h-20 w-full items-center justify-center">
						<Spinner className="size-4" />
					</div>
				{/if}
			</div>

			<!-- Footer -->
			<div class="mt-2 flex items-center justify-between text-sm">
				<button
					class="px-2 py-1 text-xs text-gray-400 transition hover:text-gray-200 hover:underline"
					onclick={() => {
						showClearConfirmDialog = true;
					}}
				>
					清空记忆
				</button>

				<button
					class="rounded-3xl px-3.5 py-1.5 font-medium outline outline-1 outline-gray-800 transition hover:bg-white/5"
					onclick={() => {
						showAddMemoryModal = true;
					}}
				>
					新增记忆
				</button>
			</div>
		</div>
	</div>
</Modal>

<ConfirmDialog
	title="清空记忆"
	message="确定要清空所有记忆吗？该操作不可撤销。"
	confirmLabel="确定"
	cancelLabel="取消"
	show={showClearConfirmDialog}
	onConfirm={onClearConfirmed}
/>

<ConfirmDialog
	title="删除记忆"
	message={deleteMessage}
	confirmLabel="确定"
	cancelLabel="取消"
	show={showDeleteConfirm}
	onConfirm={async () => {
		if (!selectedMemory) {
			showDeleteConfirm = false;
			return;
		}
		await deleteMemoryById(null, selectedMemory.id);
		memories = await listMemories();
		showDeleteConfirm = false;
	}}
/>

<AddMemoryModal bind:show={showAddMemoryModal} onSave={refresh} />

<EditMemoryModal bind:show={showEditMemoryModal} memory={selectedMemory} onSave={refresh} />
