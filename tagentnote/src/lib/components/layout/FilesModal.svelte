<script lang="ts">
	import Modal from '$lib/components/common/Modal.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';

	type FileRow = {
		id: string;
		name: string;
		size?: number;
		createdAt: number;
	};

	type Props = {
		show?: boolean;
		files: FileRow[];
		onDelete?: (id: string) => void;
	};

	let { show = $bindable(false), files = [], onDelete = () => {} }: Props = $props();

	let query = $state('');
	let orderBy = $state<'name' | 'createdAt'>('createdAt');
	let direction = $state<'asc' | 'desc'>('desc');
	let selectedFileId = $state<string | null>(null);
	let showDeleteConfirmDialog = $state(false);

	const setSortKey = (key: 'name' | 'createdAt') => {
		if (orderBy === key) {
			direction = direction === 'asc' ? 'desc' : 'asc';
		} else {
			orderBy = key;
			direction = 'asc';
		}
	};

	const formatSize = (bytes: number): string => {
		if (bytes === 0) return '0 B';
		const k = 1024;
		const units = ['B', 'KB', 'MB', 'GB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + units[i];
	};

	const formatDate = (ts: number): string => {
		const d = new Date(ts);
		return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
	};

	const filtered = $derived.by(() => {
		const lower = query.trim().toLowerCase();
		const list = lower ? files.filter((f) => f.name.toLowerCase().includes(lower)) : files;
		const sorted = [...list].sort((a, b) => {
			const av = orderBy === 'name' ? a.name.toLowerCase() : a.createdAt;
			const bv = orderBy === 'name' ? b.name.toLowerCase() : b.createdAt;
			return direction === 'asc' ? (av > bv ? 1 : -1) : av < bv ? 1 : -1;
		});
		return sorted;
	});

	const requestDelete = (id: string) => {
		selectedFileId = id;
		showDeleteConfirmDialog = true;
	};

	const handleConfirmDelete = () => {
		if (selectedFileId) {
			onDelete(selectedFileId);
		}
		selectedFileId = null;
		showDeleteConfirmDialog = false;
	};
</script>

<ConfirmDialog
	bind:show={showDeleteConfirmDialog}
	title="删除文件"
	message="删除文件后无法恢复，是否继续？"
	confirmLabel="删除"
	cancelLabel="取消"
	onConfirm={handleConfirmDelete}
	onCancel={() => {
		showDeleteConfirmDialog = false;
		selectedFileId = null;
	}}
/>

<Modal size="xl" bind:show>
	<div>
		<div class="flex justify-between px-5 pt-4 pb-1 text-gray-300">
			<div class="self-center text-lg font-medium">管理文件</div>
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
			<div class="mb-0.5 flex w-full space-x-2">
				<div class="flex flex-1">
					<div class="mr-3 ml-1 self-center">
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
						placeholder="搜索文件"
						maxlength="500"
					/>
				</div>
			</div>

			<div class="flex w-full flex-col">
				{#if filtered.length > 0}
					<div class="mb-1.5 flex text-xs font-medium">
						<button
							class="basis-3/5 cursor-pointer px-1.5 py-1 select-none"
							onclick={() => setSortKey('name')}
							type="button"
						>
							<div class="flex items-center gap-1.5">
								文件名
								<span class="font-normal">
									{#if orderBy === 'name'}
										{#if direction === 'asc'}↑{:else}↓{/if}
									{:else}
										&nbsp;
									{/if}
								</span>
							</div>
						</button>
						<button
							class="hidden basis-2/5 cursor-pointer justify-end px-1.5 py-1 select-none sm:flex"
							onclick={() => setSortKey('createdAt')}
							type="button"
						>
							<div class="flex items-center gap-1.5">
								创建时间
								<span class="font-normal">
									{#if orderBy === 'createdAt'}
										{#if direction === 'asc'}↑{:else}↓{/if}
									{:else}
										&nbsp;
									{/if}
								</span>
							</div>
						</button>
					</div>
				{/if}

				<div class="mb-3 max-h-[32rem] w-full overflow-y-scroll text-left text-sm">
					{#if filtered.length === 0}
						<div
							class="flex h-full min-h-20 w-full items-center justify-center px-5 text-center text-xs text-gray-500"
						>
							未找到文件
						</div>
					{/if}

					{#each filtered as file (file.id)}
						<div
							role="button"
							tabindex="0"
							class="hover:bg-gray-850 flex w-full cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-sm"
						>
							<div class="min-w-0 basis-3/5">
								<div class="line-clamp-1 text-ellipsis">{file.name}</div>
								<div class="text-xs text-gray-500">{formatSize(file.size ?? 0)}</div>
							</div>
							<div class="flex basis-2/5 items-center justify-end">
								<div class="hidden text-xs text-gray-500 sm:flex">
									{formatDate(file.createdAt)}
								</div>
								<div class="flex justify-end pl-2.5 text-gray-400">
									<button
										type="button"
										class="w-fit rounded-xl px-1 text-sm hover:text-red-400"
										title="删除文件"
										onclick={() => requestDelete(file.id)}
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
												d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"
											></path>
										</svg>
									</button>
								</div>
							</div>
						</div>
					{/each}
				</div>
			</div>
		</div>
	</div>
</Modal>
