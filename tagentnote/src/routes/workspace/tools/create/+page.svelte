<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';

	import EditorShell from '$lib/components/workspace/EditorShell.svelte';
	import { slugify, upsertTool, type WorkspaceTool } from '$lib/data/workspaceResources';

	let saving = $state(false);
	let name = $state('');
	let id = $state('');
	let idTouched = $state(false);
	let description = $state('');
	let content = $state(
		'class Tools:\n    def example(self, query: str) -> str:\n        """Describe the tool."""\n        return query\n'
	);
	let clonedManifest = $state<Record<string, unknown> | null>(null);

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
		const raw = sessionStorage.getItem('tool');
		if (raw) {
			try {
				const clone = JSON.parse(raw) as WorkspaceTool;
				name = clone.name || '';
				id = clone.id || '';
				idTouched = true;
				description = clone.description || '';
				content = clone.content || content;
				clonedManifest = clone.meta?.manifest ?? { name: clone.id };
			} catch {
				/* ignore */
			}
			sessionStorage.removeItem('tool');
		}
	});

	const onSave = () => {
		const finalId = (idTouched ? id : slugify(name) || id).trim();
		if (!name.trim() || !finalId) return;
		saving = true;
		const toolId = finalId.startsWith('tool-') ? finalId : `tool-${finalId}`;
		upsertTool({
			id: toolId,
			name: name.trim(),
			description: description.trim(),
			content,
			meta: { manifest: clonedManifest ?? { name: toolId } },
			owner: 'you',
			createdAt: Date.now(),
			updatedAt: Date.now()
		});
		saving = false;
		void goto(withParams('/workspace/tools'));
	};
</script>

<EditorShell
	title="创建工具"
	subtitle="Python 工具脚本"
	{saving}
	saveLabel="保存并创建"
	onBack={() => void goto(withParams('/workspace/tools'))}
	{onSave}
>
	<div>
		<label class={label} for="tool-name">名称</label>
		<input
			id="tool-name"
			class={field}
			bind:value={name}
			placeholder="计算器"
			oninput={() => {
				if (!idTouched) id = slugify(name);
			}}
		/>
	</div>
	<div>
		<label class={label} for="tool-id">ID</label>
		<input
			id="tool-id"
			class={field}
			bind:value={id}
			placeholder="calculator"
			oninput={() => {
				idTouched = true;
			}}
		/>
	</div>
	<div>
		<label class={label} for="tool-desc">描述</label>
		<textarea id="tool-desc" class="{field} min-h-[3.5rem] resize-y" bind:value={description} rows="2"
		></textarea>
	</div>
	<div>
		<label class={label} for="tool-content">内容（Python）</label>
		<textarea
			id="tool-content"
			class="{field} min-h-[12rem] resize-y font-mono text-xs"
			bind:value={content}
			rows="12"
		></textarea>
	</div>
</EditorShell>
