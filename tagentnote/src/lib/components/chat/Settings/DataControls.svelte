<script lang="ts">
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import type { ChatRow } from '$lib/components/layout/ChatsModal.svelte';

	type Props = {
		// mock 数据
		allChats?: ChatRow[];
		files?: { id: string; name: string; size?: number; createdAt: number }[];
		// 行为回调（mock 行为）
		onImport?: (file: File) => void;
		onExport?: () => void;
		onArchiveAll?: () => void;
		onDeleteAll?: () => void;
		onUnarchive?: (id: string) => void;
		onUnshare?: (id: string) => void;
		onDeleteChat?: (id: string) => void;
		onDeleteFile?: (id: string) => void;
		// 行为：是否显示导出按钮（默认管理员可见）
		canExport?: boolean;
	};

	let {
		allChats = [],
		files = [],
		onImport = () => {},
		onExport = () => {},
		onArchiveAll = () => {},
		onDeleteAll = () => {},
		onUnarchive = () => {},
		onUnshare = () => {},
		onDeleteChat = () => {},
		onDeleteFile = () => {},
		canExport = true
	}: Props = $props();

	let importFiles: FileList | null = $state(null);
	let chatImportInputElement: HTMLInputElement | null = $state(null);
	let showArchiveConfirmDialog = $state(false);
	let showDeleteConfirmDialog = $state(false);

	$effect(() => {
		if (importFiles && importFiles.length > 0) {
			onImport(importFiles[0]);
			if (chatImportInputElement) chatImportInputElement.value = '';
			importFiles = null;
		}
	});

</script>

<ConfirmDialog
	bind:show={showArchiveConfirmDialog}
	title="归档所有对话"
	message="确定要归档全部对话吗？此操作无法撤销。"
	cancelLabel="取消"
	confirmLabel="全部归档"
	onConfirm={onArchiveAll}
	onCancel={() => {
		showArchiveConfirmDialog = false;
	}}
/>

<ConfirmDialog
	bind:show={showDeleteConfirmDialog}
	title="删除所有对话"
	message="确定要删除全部对话吗？此操作无法撤销。"
	cancelLabel="取消"
	confirmLabel="全部删除"
	onConfirm={onDeleteAll}
	onCancel={() => {
		showDeleteConfirmDialog = false;
	}}
/>

<div id="tab-chats" class="flex h-full flex-col justify-between text-sm">
	<div class="max-h-[28rem] space-y-3 overflow-y-scroll md:max-h-full">
		<input
			id="chat-import-input"
			bind:this={chatImportInputElement}
			bind:files={importFiles}
			type="file"
			accept=".json"
			hidden
		/>

		<div>
			<div class="mb-1 text-sm font-medium">对话</div>

			<div>
				<div class="flex w-full justify-between py-0.5">
					<div class="self-center text-xs">导入对话记录</div>
					<button
						class="flex rounded-sm p-1 px-3 text-xs transition hover:bg-gray-800"
						onclick={() => {
							chatImportInputElement?.click();
						}}
						type="button"
					>
						<span class="self-center">导入</span>
					</button>
				</div>
			</div>

			{#if canExport}
				<div>
					<div class="flex w-full justify-between py-0.5">
						<div class="self-center text-xs">导出对话</div>
						<button
							class="flex rounded-sm p-1 px-3 text-xs transition hover:bg-gray-800"
							onclick={onExport}
							type="button"
						>
							<span class="self-center">导出</span>
						</button>
					</div>
				</div>
			{/if}

			<div>
				<div class="flex w-full justify-between py-0.5">
					<div class="self-center text-xs">归档所有对话记录</div>
					<button
						class="flex rounded-sm p-1 px-3 text-xs transition hover:bg-gray-800"
						onclick={() => {
							showArchiveConfirmDialog = true;
						}}
						type="button"
					>
						<span class="self-center">全部归档</span>
					</button>
				</div>
			</div>

			<div>
				<div class="flex w-full justify-between py-0.5">
					<div class="self-center text-xs">删除所有对话记录</div>
					<button
						class="flex rounded-sm p-1 px-3 text-xs transition hover:bg-gray-800"
						onclick={() => {
							showDeleteConfirmDialog = true;
						}}
						type="button"
					>
						<span class="self-center">全部删除</span>
					</button>
				</div>
			</div>
		</div>

	</div>
</div>
