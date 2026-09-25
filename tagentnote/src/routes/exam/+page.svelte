<script lang="ts">
	import { goto, replaceState } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/stores';

	import ExamShell from '$lib/components/quiz/ExamShell.svelte';
	import { type ExamMode } from '$lib/data/exam';

	const modelId = $derived($page.url.searchParams.get('model') ?? '');
	const initialTopic = $derived($page.url.searchParams.get('topic') ?? '');

	// ?mode= 只预选模式卡，不代表已经开跑（见 ExamShell 里 running 的注释）
	const initialMode = $derived<ExamMode>(
		$page.url.searchParams.get('mode') === 'full' ? 'full' : 'flash'
	);

	const returnPath = $derived(
		$page.url.searchParams.get('from') === 'qa'
			? resolve(`/qa?model=${encodeURIComponent(modelId)}`)
			: resolve('/agent-select')
	);

	// 只是把选择记在地址栏里，不触发导航：用浅路由的 replaceState，
	// 免得 goto 白跑一遍 load、还把焦点和滚动位置重置掉。
	const rememberMode = (mode: ExamMode) => {
		const url = new URL($page.url);
		url.searchParams.set('mode', mode);
		replaceState(resolve(`/exam?${url.searchParams.toString()}`), $page.state);
	};
</script>

<svelte:head>
	<title>智能测评 | TAgent</title>
</svelte:head>

<div class="min-h-[100dvh] w-full bg-[#171717] text-gray-100">
	<div class="mx-auto flex h-[100dvh] max-w-6xl flex-col">
		<div class="flex shrink-0 items-center justify-between px-4 pt-3">
			<button
				type="button"
				class="text-sm text-gray-400 transition hover:text-gray-200"
				onclick={() => goto(returnPath)}
			>
				‹ 返回
			</button>

			<div class="font-mono text-xs text-gray-400">测评智能体</div>
		</div>

		<div class="m-3 min-h-0 flex-1 overflow-hidden rounded-2xl border border-gray-800">
			<ExamShell
				fullPage={true}
				{modelId}
				{initialTopic}
				{initialMode}
				onModeChange={rememberMode}
			/>
		</div>
	</div>
</div>
