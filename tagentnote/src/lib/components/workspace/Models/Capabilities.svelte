<script lang="ts">
	import Checkbox from './Checkbox.svelte';

	type Props = {
		capabilities?: Record<string, boolean | undefined>;
	};

	let { capabilities = $bindable({}) }: Props = $props();

	const labels: { key: string; label: string }[] = [
		{ key: 'vision', label: '视觉' },
		{ key: 'file_upload', label: '文件上传' },
		{ key: 'file_context', label: '文件上下文' },
		{ key: 'web_search', label: '联网搜索' },
		{ key: 'image_generation', label: '图像生成' },
		{ key: 'code_interpreter', label: '代码解释器' },
		{ key: 'citations', label: '引用' },
		{ key: 'status_updates', label: '显示实时回答状态' },
		{ key: 'builtin_tools', label: '内置工具' },
		{ key: 'usage', label: '用量' }
	];

	const visible = $derived(
		labels.filter((item) => !(item.key === 'file_context' && !capabilities.file_upload))
	);
</script>

<div>
	<div class="mb-1 flex w-full justify-between">
		<div class="self-center text-xs font-medium text-gray-500">能力</div>
	</div>
	<div class="mt-2 flex flex-wrap items-center">
		{#each visible as item (item.key)}
			<div class="mr-3 flex items-center gap-2">
				<Checkbox
					state={capabilities[item.key] ? 'checked' : 'unchecked'}
					onChange={(next) => {
						capabilities = { ...capabilities, [item.key]: next === 'checked' };
					}}
				/>
				<div class="py-0.5 text-sm">{item.label}</div>
			</div>
		{/each}
	</div>
</div>
