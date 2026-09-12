<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';

	import Switch from '$lib/components/common/Switch.svelte';
	import EditorShell from '$lib/components/workspace/EditorShell.svelte';
	import { slugify, upsertSkill, type WorkspaceSkill } from '$lib/data/workspaceResources';

	let saving = $state(false);
	let name = $state('');
	let id = $state('');
	let idTouched = $state(false);
	let description = $state('');
	let content = $state('');
	let isActive = $state(true);

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
		const raw = sessionStorage.getItem('skill');
		if (raw) {
			try {
				const clone = JSON.parse(raw) as WorkspaceSkill;
				name = clone.name || '';
				id = clone.id || '';
				idTouched = true;
				description = clone.description || '';
				content = clone.content || '';
				isActive = clone.isActive !== false;
			} catch {
				/* ignore */
			}
			sessionStorage.removeItem('skill');
		}
	});

	const onSave = () => {
		const finalId = (idTouched ? id : slugify(name) || id).trim();
		if (!name.trim() || !finalId) return;
		saving = true;
		upsertSkill({
			id: finalId.startsWith('skill-') ? finalId : `skill-${finalId}`,
			name: name.trim(),
			description: description.trim(),
			content,
			isActive,
			owner: 'you',
			createdAt: Date.now(),
			updatedAt: Date.now()
		});
		saving = false;
		void goto(withParams('/workspace/skills'));
	};
</script>

<EditorShell
	title="创建技能"
	subtitle="Markdown 技能定义"
	{saving}
	saveLabel="保存并创建"
	onBack={() => void goto(withParams('/workspace/skills'))}
	{onSave}
>
	<div>
		<label class={label} for="skill-name">名称</label>
		<input
			id="skill-name"
			class={field}
			bind:value={name}
			placeholder="教材引用助手"
			oninput={() => {
				if (!idTouched) id = slugify(name);
			}}
		/>
	</div>
	<div>
		<label class={label} for="skill-id">ID</label>
		<input
			id="skill-id"
			class={field}
			bind:value={id}
			placeholder="citation-helper"
			oninput={() => {
				idTouched = true;
			}}
		/>
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
			placeholder={'---\nname: my-skill\n---\n\nInstructions…'}
		></textarea>
	</div>
	<div class="flex items-center justify-between py-1">
		<span class="text-sm text-gray-300">启用</span>
		<Switch bind:state={isActive} />
	</div>
</EditorShell>
