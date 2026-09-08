<script lang="ts">
	import WorkspacePanel from '$lib/components/workspace/WorkspacePanel.svelte';

	let query = $state('');
</script>

<WorkspacePanel
	title="工具"
	count={0}
	searchPlaceholder="搜索工具"
	bind:query
	primaryAction="创建工具"
	emptyTitle="未找到任何工具"
	emptyHint="请尝试调整您的搜索词或过滤器以找到您需要的内容。"
/>
