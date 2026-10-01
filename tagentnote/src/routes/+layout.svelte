<script lang="ts">
	import { onMount } from 'svelte';

	import '../app.css';
	// 出题 prompt 要求公式用 $...$ / $$...$$ 包裹，渲染走 $lib/data/math.ts
	import 'katex/dist/katex.min.css';
	import { initI18n, setI18nContext } from '$lib/i18n';
	import i18n from '$lib/i18n';

	// 初始化 i18n 并设置 context（在组件初始化时同步执行）
	initI18n();
	setI18nContext();

	let { children } = $props();

	// 断网时顶部一条提示：学生知道是网的问题，也知道已经写的东西没丢（压测 F4）
	let online = $state(true);

	onMount(() => {
		const update = () => (online = navigator.onLine);
		update();
		window.addEventListener('online', update);
		window.addEventListener('offline', update);
		return () => {
			window.removeEventListener('online', update);
			window.removeEventListener('offline', update);
		};
	});
</script>

<svelte:head>
	<meta
		name="description"
		content="TAgent 系统建模与仿真智能教学平台"
	/>
</svelte:head>

{#if !online}
	<div
		role="status"
		class="fixed inset-x-0 top-0 z-[100] bg-amber-400 px-4 py-1.5 text-center text-xs font-medium text-gray-950 shadow"
	>
		网络已断开：已经写的内容都还在，恢复连接后再继续。
	</div>
{/if}

{@render children()}