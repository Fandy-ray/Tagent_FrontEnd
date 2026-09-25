<script lang="ts">
	type KnowledgeOption = { id: string; name: string };
	type KnowledgeFile = { id: string; name: string; type: 'file'; size?: number };

	type Props = {
		options?: KnowledgeOption[];
		knowledgeIds?: string[];
		knowledgeFiles?: KnowledgeFile[];
	};

	let {
		options = [],
		knowledgeIds = $bindable([]),
		knowledgeFiles = $bindable([])
	}: Props = $props();

	let showPicker = $state(false);
	let fileInput: HTMLInputElement | null = $state(null);

	const selectedKnowledge = $derived(
		options.filter((item) => knowledgeIds.includes(item.id))
	);

	const toggleKnowledge = (id: string) => {
		if (knowledgeIds.includes(id)) {
			knowledgeIds = knowledgeIds.filter((x) => x !== id);
		} else {
			knowledgeIds = [...knowledgeIds, id];
		}
	};

	const onUpload = (e: Event) => {
		const input = e.target as HTMLInputElement;
		const files = Array.from(input.files ?? []);
		for (const file of files) {
			knowledgeFiles = [
				...knowledgeFiles,
				{
					id: `file-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
					name: file.name,
					type: 'file',
					size: file.size
				}
			];
		}
		input.value = '';
	};
</script>

<div>
	<div class="mb-2">
		<div class="mb-1 flex w-full justify-between">
			<div class="self-center text-xs font-medium text-gray-500">知识库</div>
		</div>
	</div>

	{#if selectedKnowledge.length > 0 || knowledgeFiles.length > 0}
		<div class="mb-2.5 flex flex-wrap items-center gap-2">
			{#each selectedKnowledge as item (item.id)}
				<span
					class="inline-flex items-center gap-1.5 rounded-xl border border-gray-800 bg-transparent px-2.5 py-1 text-xs text-gray-200"
				>
					{item.name}
					<button
						type="button"
						class="text-gray-500 hover:text-white"
						aria-label="移除"
						onclick={() => {
							knowledgeIds = knowledgeIds.filter((id) => id !== item.id);
						}}
					>
						×
					</button>
				</span>
			{/each}
			{#each knowledgeFiles as file, idx (file.id)}
				<span
					class="inline-flex items-center gap-1.5 rounded-xl border border-gray-800 bg-transparent px-2.5 py-1 text-xs text-gray-200"
				>
					{file.name}
					<button
						type="button"
						class="text-gray-500 hover:text-white"
						aria-label="移除文件"
						onclick={() => {
							knowledgeFiles = knowledgeFiles.filter((_, i) => i !== idx);
						}}
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
			class="rounded-3xl px-3.5 py-1.5 font-medium outline outline-1 outline-gray-850 hover:bg-white/5"
			onclick={() => {
				showPicker = !showPicker;
			}}
		>
			选择知识
		</button>
		<button
			type="button"
			class="rounded-3xl px-3.5 py-1.5 font-medium outline outline-1 outline-gray-850 hover:bg-white/5"
			onclick={() => fileInput?.click()}
		>
			上传文件
		</button>

		{#if showPicker}
			<div
				class="absolute top-full left-0 z-20 mt-1 max-h-56 min-w-56 overflow-y-auto rounded-xl border border-gray-800 bg-[#171717] p-2 shadow-xl"
			>
				{#if options.length === 0}
					<div class="px-2 py-2 text-xs text-gray-500">暂无知识库</div>
				{:else}
					{#each options as opt (opt.id)}
						<label
							class="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-gray-850"
						>
							<input
								type="checkbox"
								checked={knowledgeIds.includes(opt.id)}
								onchange={() => toggleKnowledge(opt.id)}
							/>
							<span class="truncate">{opt.name}</span>
						</label>
					{/each}
				{/if}
				<button
					type="button"
					class="mt-1 w-full rounded-lg px-2 py-1 text-xs text-gray-400 hover:bg-gray-850"
					onclick={() => {
						showPicker = false;
					}}
				>
					完成
				</button>
			</div>
		{/if}
	</div>

	<input bind:this={fileInput} type="file" class="hidden" multiple onchange={onUpload} />

	<div class="mt-1 text-xs text-gray-600">
		要在此处附加知识库，请先将它们添加到“知识库”工作区。
	</div>
</div>
