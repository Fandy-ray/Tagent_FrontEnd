<script lang="ts">
	import WorkspacePanel from '$lib/components/workspace/WorkspacePanel.svelte';

	let query = $state('');
</script>

<WorkspacePanel
	title="提示词"
	count={0}
	searchPlaceholder="搜索提示词"
	bind:query
	primaryAction="创建提示词"
	emptyTitle="未找到任何提示词"
	emptyHint="请尝试调整您的搜索词或过滤器以找到您需要的内容。"
/>
