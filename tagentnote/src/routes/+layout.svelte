<script lang="ts">
	import '../app.css';
	// 出题 prompt 要求公式用 $...$ / $$...$$ 包裹，渲染走 $lib/data/math.ts
	import 'katex/dist/katex.min.css';

	let { children } = $props();
</script>

<svelte:head>
	<meta name="description" content="TAgent 系统建模与仿真智能教学平台" />
</svelte:head>

{@render children()}
