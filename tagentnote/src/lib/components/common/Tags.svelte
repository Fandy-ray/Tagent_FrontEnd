<script lang="ts">
	type Tag = {
		name: string;
		color?: string;
	};

	type Props = {
		tags?: Tag[];
		readonly?: boolean;
		onAdd?: (e: CustomEvent<string>) => void;
		onDelete?: (e: CustomEvent<string>) => void;
	};

	let { tags = $bindable([]), readonly = false, onAdd, onDelete }: Props = $props();

	let inputValue = $state('');

	const addTag = (name: string) => {
		const trimmed = name.trim();
		if (trimmed && !tags.find((t) => t.name === trimmed)) {
			tags = [...tags, { name: trimmed }];
			onAdd?.(new CustomEvent('add', { detail: trimmed }));
		}
		inputValue = '';
	};

	const deleteTag = (name: string) => {
		tags = tags.filter((t) => t.name !== name);
		onDelete?.(new CustomEvent('delete', { detail: name }));
	};

	const handleKeydown = (e: KeyboardEvent) => {
		if (e.key === 'Enter' || e.key === ',') {
			e.preventDefault();
			addTag(inputValue);
		} else if (e.key === 'Backspace' && !inputValue && tags.length > 0) {
			deleteTag(tags[tags.length - 1].name);
		}
	};
</script>

<div class="flex flex-wrap gap-1">
	{#each tags as tag (tag.name)}
		<div class="flex items-center gap-1 rounded-full bg-gray-700 px-2 py-0.5 text-xs text-gray-200">
			<span>{tag.name}</span>
			{#if !readonly}
				<button
					type="button"
					class="hover:text-white"
					onclick={() => deleteTag(tag.name)}
					aria-label="Remove tag"
				>
					<svg
						class="size-3"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
					>
						<path d="M18 6L6 18M6 6l12 12" />
					</svg>
				</button>
			{/if}
		</div>
	{/each}
	{#if !readonly}
		<input
			type="text"
			class="min-w-[60px] flex-1 bg-transparent text-xs outline-none placeholder:text-gray-500"
			placeholder={tags.length === 0 ? 'Add tag...' : ''}
			bind:value={inputValue}
			onkeydown={handleKeydown}
		/>
	{/if}
</div>
