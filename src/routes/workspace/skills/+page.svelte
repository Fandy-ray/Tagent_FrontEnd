<script lang="ts">
	import WorkspacePanel from '$lib/components/workspace/WorkspacePanel.svelte';

	let query = $state('');
</script>

<WorkspacePanel
	title="技能"
	count={0}
	searchPlaceholder="搜索技能"
	bind:query
	primaryAction="创建技能"
	emptyTitle="未找到任何技能"
	emptyHint="请尝试调整您的搜索词或过滤器以找到您需要的内容。"
/>
