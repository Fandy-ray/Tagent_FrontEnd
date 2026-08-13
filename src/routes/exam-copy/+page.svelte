<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import MockExamPanel from '$lib/components/quiz/MockExamPanel.svelte';

	const modelId = $derived(
		$page.url.searchParams.get('model') ?? 'deepseek'
	);

	const returnPath = $derived(
		$page.url.searchParams.get('from') === 'qa'
			? `/qa?model=${encodeURIComponent(modelId)}`
			: '/agent-select'
	);
</script>

<svelte:head>
	<title>智能测评 · AI 试卷</title>
</svelte:head>

<div class="min-h-[100dvh] w-full bg-[#171717] text-gray-100">
	<div class="mx-auto flex h-[100dvh] max-w-6xl flex-col">
		<div class="flex shrink-0 items-center justify-between px-4 pt-3">
			<button
	type="button"
	class="text-sm text-gray-400 transition hover:text-gray-200"
	onclick={() => goto(returnPath)}
>
	‹ 返回选择
</button>

			<div class="font-mono text-xs text-gray-400 dark:text-gray-500">
				测评智能体 · Quiz Agent
			</div>
		</div>

		<div
			class="m-3 min-h-0 flex-1 overflow-hidden rounded-2xl border border-gray-200 shadow-sm dark:border-gray-800"
		>
			<MockExamPanel
				fullPage={true}
				modelId={modelId}
			/>
		</div>
	</div>
</div>