<script lang="ts">
	type Props = {
		value?: string;
		onChange?: (value: string) => void;
	};

	let { value = $bindable(''), onChange = () => {} }: Props = $props();

	const items = [
		{ value: '', label: '全部' },
		{ value: 'created', label: '由您创建' },
		{ value: 'shared', label: '与您共享' }
	];

	let open = $state(false);
	const selectedLabel = $derived(items.find((i) => i.value === value)?.label ?? '全部');
</script>

<div class="relative">
	<button
		type="button"
		class="relative flex w-full items-center gap-0.5 rounded-xl bg-gray-850 px-2.5 py-1.5 text-sm text-gray-200"
		onclick={() => {
			open = !open;
		}}
	>
		<span class="inline-flex w-full truncate px-0.5">{selectedLabel}</span>
		<svg class="size-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
			<path stroke-linecap="round" stroke-linejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
		</svg>
	</button>
	{#if open}
		<div
			class="absolute top-full left-0 z-30 mt-1 min-w-[10rem] overflow-hidden rounded-xl border border-gray-800 bg-gray-850 py-1 shadow-lg"
		>
			{#each items as item}
				<button
					type="button"
					class="flex w-full items-center px-3 py-1.5 text-left text-sm hover:bg-gray-800 {value ===
					item.value
						? 'text-white'
						: 'text-gray-300'}"
					onclick={() => {
						value = item.value;
						onChange(item.value);
						open = false;
					}}
				>
					{item.label}
					{#if value === item.value}
						<span class="ml-auto text-xs">✓</span>
					{/if}
				</button>
			{/each}
		</div>
	{/if}
</div>
