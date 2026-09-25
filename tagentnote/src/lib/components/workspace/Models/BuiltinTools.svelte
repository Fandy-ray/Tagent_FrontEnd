<script lang="ts">
	import Checkbox from './Checkbox.svelte';

	type Props = {
		builtinTools?: Record<string, boolean>;
	};

	let { builtinTools = $bindable({}) }: Props = $props();

	const labels: { key: string; label: string }[] = [
		{ key: 'time', label: '时间和计算' },
		{ key: 'memory', label: '记忆' },
		{ key: 'chats', label: '对话历史记录' },
		{ key: 'notes', label: '笔记' },
		{ key: 'knowledge', label: '知识库' },
		{ key: 'channels', label: '频道' },
		{ key: 'web_search', label: '联网搜索' },
		{ key: 'image_generation', label: '图像生成' },
		{ key: 'code_interpreter', label: '代码解释器' }
	];

	$effect(() => {
		let changed = false;
		const next = { ...builtinTools };
		for (const item of labels) {
			if (!(item.key in next)) {
				next[item.key] = true;
				changed = true;
			}
		}
		if (changed) builtinTools = next;
	});
</script>

<div>
	<div class="mb-1 flex w-full justify-between">
		<div class="self-center text-xs font-medium text-gray-500">内置工具</div>
	</div>
	<div class="mt-2 flex flex-wrap items-center">
		{#each labels as item (item.key)}
			<div class="mr-3 flex items-center gap-2">
				<Checkbox
					state={builtinTools[item.key] !== false ? 'checked' : 'unchecked'}
					onChange={(next) => {
						builtinTools = { ...builtinTools, [item.key]: next === 'checked' };
					}}
				/>
				<div class="py-0.5 text-sm">{item.label}</div>
			</div>
		{/each}
	</div>
</div>
