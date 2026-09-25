<script lang="ts">
	import Checkbox from './Checkbox.svelte';

	type Props = {
		availableFeatures?: string[];
		featureIds?: string[];
	};

	let { availableFeatures = [], featureIds = $bindable([]) }: Props = $props();

	const labels: Record<string, string> = {
		web_search: '联网搜索',
		image_generation: '图像生成',
		code_interpreter: '代码解释器'
	};
</script>

<div>
	<div class="mb-1 flex w-full justify-between">
		<div class="self-center text-xs font-medium text-gray-500">默认功能</div>
	</div>
	<div class="mt-2 flex flex-wrap items-center">
		{#each availableFeatures as feature (feature)}
			<div class="mr-3 flex items-center gap-2">
				<Checkbox
					state={featureIds.includes(feature) ? 'checked' : 'unchecked'}
					onChange={(next) => {
						if (next === 'checked') {
							featureIds = [...featureIds, feature];
						} else {
							featureIds = featureIds.filter((id) => id !== feature);
						}
					}}
				/>
				<div class="py-0.5 text-sm">{labels[feature] ?? feature}</div>
			</div>
		{/each}
	</div>
</div>
