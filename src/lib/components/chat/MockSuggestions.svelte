<script lang="ts">
	type Suggestion = {
		id: string;
		title: [string, string];
		content: string;
	};

	type Props = {
		inputValue?: string;
		onSelect?: (content: string) => void;
	};

	let {
		inputValue = '',
		onSelect = () => {}
	}: Props = $props();

	const suggestions: Suggestion[] = [
		{
			id: 'suggestion-1',
			title: ['Help me study', 'vocabulary for a college entrance exam'],
			content: 'Help me study vocabulary for a college entrance exam'
		},
		{
			id: 'suggestion-2',
			title: ['Give me ideas', "for what to do with my kids' art"],
			content: "Give me ideas for what to do with my kids' art"
		},
		{
			id: 'suggestion-3',
			title: ['Show me a code snippet', "of a website's sticky header"],
			content: "Show me a code snippet of a website's sticky header"
		}
	];

	let filteredSuggestions = $derived(
		inputValue.trim()
			? suggestions.filter((suggestion) => {
					const searchText =
						`${suggestion.title[0]} ${suggestion.title[1]} ${suggestion.content}`.toLowerCase();

					return searchText.includes(inputValue.trim().toLowerCase());
				})
			: suggestions
	);
</script>

<div class="mb-1 flex items-center gap-1 text-xs font-medium text-gray-400">
	{#if filteredSuggestions.length > 0}
		<svg
			class="size-3.5"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			stroke-width="1.8"
			stroke-linecap="round"
			stroke-linejoin="round"
			aria-hidden="true"
		>
			<path d="m13 2-8 12h7l-1 8 8-12h-7z"></path>
		</svg>

		<span>建议</span>
	{:else}
		<div class="flex w-full items-center justify-center text-gray-500">
			系统建模与仿真智能体
		</div>
	{/if}
</div>

<div class="h-40 w-full">
	{#if filteredSuggestions.length > 0}
		<div
			role="list"
			class="max-h-40 items-start overflow-auto"
		>
			{#each filteredSuggestions as suggestion, index (suggestion.id)}
				<button
					type="button"
					role="listitem"
					class="suggestion-item group flex w-full flex-col justify-between rounded-xl bg-transparent px-3 py-2 text-left transition hover:bg-white/[0.05]"
					style={`animation-delay: ${index * 60}ms`}
					onclick={() => onSelect(suggestion.content)}
				>
					<span
						class="line-clamp-1 text-xs font-medium text-gray-300 transition group-hover:text-gray-200"
					>
						{suggestion.title[0]}
					</span>

					<span class="line-clamp-1 text-xs font-normal text-gray-500">
						{suggestion.title[1]}
					</span>
				</button>
			{/each}
		</div>
	{/if}
</div>

<style>
	@keyframes fade-in-up {
		from {
			opacity: 0;
			transform: translateY(20px);
		}

		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.suggestion-item {
		opacity: 0;
		animation: fade-in-up 200ms ease forwards;
	}
</style>