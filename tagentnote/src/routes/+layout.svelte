<script lang="ts">
	import '../app.css';

	let { children } = $props();
</script>

<svelte:head>
	<meta
		name="description"
		content="TAgent 系统建模与仿真智能教学平台"
	/>
</svelte:head>

{@render children()}