<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import { createNotebook } from '$lib/apis/opennotebook';
	import EditorShell from '$lib/components/workspace/EditorShell.svelte';
	import { slugify, upsertKnowledge } from '$lib/data/workspaceResources';

	let saving = $state(false);
	let name = $state('');
	let description = $state('');

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

	const onSave = async () => {
		if (!name.trim()) return;
		saving = true;
		const id = `kb-${slugify(name)}-${Date.now().toString(36)}`;
		let notebookId: string | null = null;
		try {
			const nb = await createNotebook(name.trim(), description.trim());
			notebookId = nb.id;
		} catch {
			/* optional */
		}
		const t = Date.now();
		upsertKnowledge({
			id,
			name: name.trim(),
			description: description.trim(),
			notebookId,
			docs: [],
			writeAccess: true,
			owner: 'you',
			createdAt: t,
			updatedAt: t
		});
		saving = false;
		void goto(withParams(`/workspace/knowledge/${encodeURIComponent(id)}`));
	};

</script>

<EditorShell
	title="创建知识库"
	subtitle="本地集合，可绑定 OpenNoteBook"
	{saving}
	saveLabel="保存并创建"
	onBack={() => void goto(withParams('/workspace/knowledge'))}
	onSave={() => void onSave()}
>
	<div>
		<label class={label} for="kb-name">名称</label>
		<input id="kb-name" class={field} bind:value={name} placeholder="课程知识库" />
	</div>
	<div>
		<label class={label} for="kb-desc">描述</label>
		<textarea id="kb-desc" class="{field} min-h-[5rem] resize-y" bind:value={description} rows="4"
		></textarea>
	</div>
</EditorShell>
