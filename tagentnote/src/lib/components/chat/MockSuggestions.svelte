<script lang="ts">
	type Suggestion = {
		id: string;
		title: [string, string];
		content: string;
	};

	type AssistMode = 'qa' | 'paper';

	type Props = {
		inputValue?: string;
		mode?: AssistMode;
		onSelect?: (content: string) => void;
	};

	let {
		inputValue = '',
		mode = 'qa',
		onSelect = () => {}
	}: Props = $props();

	// 开场引导语，不是知识内容：措辞对任何笔记本都成立。
	const qaSuggestions: Suggestion[] = [
		{
			id: 'suggestion-1',
			title: ['帮我梳理', '当前笔记本的核心概念'],
			content: '帮我梳理当前笔记本的核心概念。'
		},
		{
			id: 'suggestion-2',
			title: ['用一个例子', '解释我不懂的地方'],
			content: '用一个具体例子解释这部分内容。'
		},
		{
			id: 'suggestion-3',
			title: ['出几道题', '检验我掌握得怎么样'],
			content: '根据笔记内容出几道题考考我。'
		}
	];

	const paperSuggestions: Suggestion[] = [
		{
			id: 'paper-outline',
			title: ['生成大纲', '课程论文章节结构'],
			content: '请基于离散事件仿真，给我一份课程论文大纲。'
		},
		{
			id: 'paper-abstract',
			title: ['起草摘要', '含方法与结果占位'],
			content: '请为「排队系统仿真优化」起草一段中文摘要。'
		},
		{
			id: 'paper-method',
			title: ['方法段落', '实体事件与假设表'],
			content: '帮我写建模方法部分：包含实体、事件、资源与假设。'
		},
		{
			id: 'paper-experiment',
			title: ['实验设计', '对照场景与指标'],
			content: '给我一个仿真实验设计模板，包含基准/改进场景和评价指标。'
		},
		{
			id: 'paper-checklist',
			title: ['完整性检查', '投稿前清单'],
			content: '按课程论文清单检查：我还缺哪些部分？'
		}
	];

	const suggestions = $derived(mode === 'paper' ? paperSuggestions : qaSuggestions);

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
		<span>{mode === 'paper' ? '论文辅助建议' : '建议'}</span>
	{:else}
		<div class="flex w-full items-center justify-center text-gray-500">
			{mode === 'paper' ? '课程论文写作助手' : '系统建模与仿真智能体'}
		</div>
	{/if}
</div>

<div class="h-40 w-full">
	{#if filteredSuggestions.length > 0}
		<div class="max-h-40 items-start overflow-auto">
			{#each filteredSuggestions as suggestion, index (suggestion.id)}
				<button
					type="button"
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
