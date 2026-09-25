<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/stores';

	import EssayWorkbench from '$lib/components/essay/EssayWorkbench.svelte';

	const modelId = $derived($page.url.searchParams.get('model') ?? '');
	// 从答疑进来时带着当前笔记本：预选为对照材料，返回时也原样带回去
	const notebook = $derived($page.url.searchParams.get('notebook') ?? '');
	const fromQa = $derived($page.url.searchParams.get('from') === 'qa');

	const back = () => {
		if (!fromQa) {
			void goto(resolve('/agent-select'));
			return;
		}

		const query = `model=${encodeURIComponent(modelId)}${
			notebook ? `&notebook=${encodeURIComponent(notebook)}` : ''
		}`;

		void goto(resolve(`/qa?${query}`));
	};
</script>

<svelte:head>
	<title>论文批改 | TAgent</title>
</svelte:head>

<EssayWorkbench {modelId} initialNotebook={notebook} onBack={back} />
