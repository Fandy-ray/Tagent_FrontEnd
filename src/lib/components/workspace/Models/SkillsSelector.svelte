<script lang="ts">
	import Checkbox from './Checkbox.svelte';

	type SkillOption = { id: string; name: string; description?: string };

	type Props = {
		skills?: SkillOption[];
		selectedSkillIds?: string[];
	};

	let { skills = [], selectedSkillIds = $bindable([]) }: Props = $props();
</script>

<div>
	<div class="mb-1 flex w-full justify-between">
		<div class="self-center text-xs font-medium text-gray-500">技能</div>
	</div>

	<div class="mb-1 flex flex-col">
		{#if skills.length > 0}
			<div class="flex flex-wrap items-center">
				{#each skills as skill (skill.id)}
					<div class="mr-3 flex items-center gap-2">
						<Checkbox
							state={selectedSkillIds.includes(skill.id) ? 'checked' : 'unchecked'}
							onChange={(next) => {
								if (next === 'checked') {
									selectedSkillIds = [...selectedSkillIds, skill.id];
								} else {
									selectedSkillIds = selectedSkillIds.filter((id) => id !== skill.id);
								}
							}}
						/>
						<div class="w-full py-0.5 text-sm font-medium capitalize">{skill.name}</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>

	<div class="text-xs text-gray-600">要在此处选择技能，请先将它们添加到“技能”工作区。</div>
</div>
