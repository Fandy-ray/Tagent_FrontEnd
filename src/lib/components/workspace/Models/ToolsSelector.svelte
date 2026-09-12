<script lang="ts">
	import Checkbox from './Checkbox.svelte';

	type ToolOption = { id: string; name: string; description?: string };

	type Props = {
		tools?: ToolOption[];
		selectedToolIds?: string[];
	};

	let { tools = [], selectedToolIds = $bindable([]) }: Props = $props();
</script>

<div>
	<div class="mb-1 flex w-full justify-between">
		<div class="self-center text-xs font-medium text-gray-500">工具</div>
	</div>

	<div class="mb-1 flex flex-col">
		{#if tools.length > 0}
			<div class="flex flex-wrap items-center">
				{#each tools as tool (tool.id)}
					<div class="mr-3 flex items-center gap-2">
						<Checkbox
							state={selectedToolIds.includes(tool.id) ? 'checked' : 'unchecked'}
							onChange={(next) => {
								if (next === 'checked') {
									selectedToolIds = [...selectedToolIds, tool.id];
								} else {
									selectedToolIds = selectedToolIds.filter((id) => id !== tool.id);
								}
							}}
						/>
						<div class="w-full py-0.5 text-sm font-medium capitalize">{tool.name}</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>

	<div class="text-xs text-gray-600">要在此处选择工具包，请先将它们添加到“工具”工作区。</div>
</div>
