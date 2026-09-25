<script lang="ts">
	type MenuItem = {
		label: string;
		danger?: boolean;
		onClick: () => void;
	};

	type Props = {
		items?: MenuItem[];
	};

	let { items = [] }: Props = $props();
	let open = $state(false);
</script>

<div class="relative">
	<button
		type="button"
		class="rounded-lg p-1 text-gray-400 transition hover:bg-white/5 hover:text-white"
		aria-label="更多操作"
		onclick={(e) => {
			e.stopPropagation();
			open = !open;
		}}
	>
		<svg class="size-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
			<path
				d="M6 12a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0zm7.5 0a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0zm7.5 0a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0z"
			/>
		</svg>
	</button>
	{#if open}
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="fixed inset-0 z-40" onclick={() => (open = false)}></div>
		<div
			class="absolute top-full right-0 z-50 mt-1 min-w-[8.5rem] overflow-hidden rounded-xl border border-gray-800 bg-gray-850 py-1 shadow-lg"
		>
			{#each items as item}
				<button
					type="button"
					class="block w-full px-3 py-1.5 text-left text-sm transition hover:bg-gray-800 {item.danger
						? 'text-red-400'
						: 'text-gray-200'}"
					onclick={(e) => {
						e.stopPropagation();
						open = false;
						item.onClick();
					}}
				>
					{item.label}
				</button>
			{/each}
		</div>
	{/if}
</div>
