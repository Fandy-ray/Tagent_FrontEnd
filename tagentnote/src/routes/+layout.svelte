<script lang="ts">
	import '../app.css';
	import { initI18n, setI18nContext } from '$lib/i18n';
	import i18n from '$lib/i18n';

	// 初始化 i18n 并设置 context（在组件初始化时同步执行）
	initI18n();
	setI18nContext();

	let { children } = $props();
</script>

<svelte:head>
	<meta
		name="description"
		content="TAgent 系统建模与仿真智能教学平台"
	/>
</svelte:head>

{@render children()}