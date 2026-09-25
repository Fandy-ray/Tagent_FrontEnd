<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';

	import Switch from '$lib/components/common/Switch.svelte';
	import EditorShell from '$lib/components/workspace/EditorShell.svelte';
	import { getSkill, upsertSkill } from '$lib/data/workspaceResources';

	let saving = $state(false);
	let missing = $state(false);
	let name = $state('');
	let id = $state('');
	let description = $state('');
	let content = $state('');
	let isActive = $state(true);
	let createdAt = $state(Date.now());

	const withParams = (path: string) => {
		const params = new URLSearchParams();
		const model = $page.url.searchParams.get('model');
		const chat = $page.url.searchParams.get('chat');
		if (model) params.set('model', model);
		if (chat) params.set('chat', chat);
		const search = params.toString();
		return search ? `${path}?${search}` : path;
	};

	const field =
		'w-full rounded-xl border border-gray-800 bg-gray-850 px-3 py-2 text-sm text-white outline-none placeholder:text-gray-500 focus:border-gray-600';
	const label = 'mb-1.5 block text-xs font-medium text-gray-400';

	onMount(() => {
		const editId = $page.url.searchParams.get('id') || '';
		const existing = editId ? getSkill(editId) : null;
		if (!existing) {
			missing = true;
			return;
		}
		id = existing.id;
		name = existing.name;
		description = existing.description || '';
		content = existing.content;
		isActive = existing.isActive !== false;
		createdAt = existing.createdAt;
	});

	const onSave = () => {
		if (!id || !name.trim()) return;
		saving = true;
		upsertSkill({
			id,
			name: name.trim(),
			description: description.trim(),
			content,
			isActive,
			owner: 'you',
			createdAt,
			updatedAt: Date.now()
		});
		saving = false;
		void goto(withParams('/workspace/skills'));
	};
</script>

{#if missing}
	<div class="px-2 py-16 text-center text-sm text-gray-500">
		未找到该技能。
		<button
			type="button"
			class="mt-3 block w-full text-white underline"
			onclick={() => void goto(withParams('/workspace/skills'))}
		>
			返回列表
		</button>
	</div>
{:else}
	<EditorShell
		title="编辑技能"
		subtitle={id}
		{saving}
		saveLabel="保存"
		onBack={() => void goto(withParams('/workspace/skills'))}
		{onSave}
	>
		<div>
			<label class={label} for="skill-name">名称</label>
			<input id="skill-name" class={field} bind:value={name} />
		</div>
		<div>
			<label class={label} for="skill-id">ID</label>
			<input id="skill-id" class="{field} opacity-60" value={id} disabled />
		</div>
		<div>
			<label class={label} for="skill-desc">描述</label>
			<textarea id="skill-desc" class="{field} min-h-[3.5rem] resize-y" bind:value={description} rows="2"
			></textarea>
		</div>
		<div>
			<label class={label} for="skill-content">内容（Markdown）</label>
			<textarea
				id="skill-content"
				class="{field} min-h-[12rem] resize-y font-mono text-xs"
				bind:value={content}
				rows="12"
			></textarea>
		</div>
		<div class="flex items-center justify-between py-1">
			<span class="text-sm text-gray-300">启用</span>
			<Switch bind:state={isActive} />
		</div>
	</EditorShell>
{/if}
