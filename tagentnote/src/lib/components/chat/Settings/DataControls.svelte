<script lang="ts">
	type Props = {
		onImport?: (file: File) => void;
		onExport?: () => void;
		onArchiveAll?: () => void;
		onDeleteAll?: () => void;
		onOpenArchived?: () => void;
	};

	let {
		onImport = () => {},
		onExport = () => {},
		onArchiveAll = () => {},
		onDeleteAll = () => {},
		onOpenArchived = () => {}
	}: Props = $props();

	let fileInput: HTMLInputElement | null = $state(null);
	let confirmArchive = $state(false);
	let confirmDelete = $state(false);
</script>

<div class="flex h-full flex-col justify-between text-sm" id="tab-data-controls">
	<div class="max-h-[28rem] space-y-3 overflow-y-scroll md:max-h-full">
		<input
			bind:this={fileInput}
			type="file"
			accept="application/json,.json"
			class="hidden"
			onchange={(event) => {
				const file = (event.currentTarget as HTMLInputElement).files?.[0];
				if (file) onImport(file);
				if (fileInput) fileInput.value = '';
			}}
		/>

		<div class="mb-1 text-sm font-medium">对话</div>

		<div class="flex w-full items-center justify-between py-0.5">
			<div class="self-center text-xs">导入对话</div>
			<button
				type="button"
				class="rounded-sm px-3 py-1 text-xs transition hover:bg-gray-800"
				onclick={() => fileInput?.click()}
			>
				导入
			</button>
		</div>

		<div class="flex w-full items-center justify-between py-0.5">
			<div class="self-center text-xs">导出对话</div>
			<button
				type="button"
				class="rounded-sm px-3 py-1 text-xs transition hover:bg-gray-800"
				onclick={onExport}
			>
				导出
			</button>
		</div>

		<div class="flex w-full items-center justify-between py-0.5">
			<div class="self-center text-xs">已归档对话</div>
			<button
				type="button"
				class="rounded-sm px-3 py-1 text-xs transition hover:bg-gray-800"
				onclick={onOpenArchived}
			>
				查看
			</button>
		</div>

		<div class="flex w-full items-center justify-between py-0.5">
			<div class="self-center text-xs">归档全部对话</div>
			{#if confirmArchive}
				<div class="flex gap-1">
					<button
						type="button"
						class="rounded px-2 py-1 text-xs text-amber-200 hover:bg-gray-800"
						onclick={() => {
							onArchiveAll();
							confirmArchive = false;
						}}>确认</button
					>
					<button
						type="button"
						class="rounded px-2 py-1 text-xs text-gray-400 hover:bg-gray-800"
						onclick={() => {
							confirmArchive = false;
						}}>取消</button
					>
				</div>
			{:else}
				<button
					type="button"
					class="rounded-sm px-3 py-1 text-xs transition hover:bg-gray-800"
					onclick={() => {
						confirmArchive = true;
					}}>归档全部</button
				>
			{/if}
		</div>

		<div class="flex w-full items-center justify-between py-0.5">
			<div class="self-center text-xs text-red-400">删除全部对话</div>
			{#if confirmDelete}
				<div class="flex gap-1">
					<button
						type="button"
						class="rounded px-2 py-1 text-xs text-red-300 hover:bg-gray-800"
						onclick={() => {
							onDeleteAll();
							confirmDelete = false;
						}}>确认删除</button
					>
					<button
						type="button"
						class="rounded px-2 py-1 text-xs text-gray-400 hover:bg-gray-800"
						onclick={() => {
							confirmDelete = false;
						}}>取消</button
					>
				</div>
			{:else}
				<button
					type="button"
					class="rounded-sm px-3 py-1 text-xs text-red-400 transition hover:bg-gray-800"
					onclick={() => {
						confirmDelete = true;
					}}>删除全部</button
				>
			{/if}
		</div>
	</div>
</div>
