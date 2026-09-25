<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';

	import EditorShell from '$lib/components/workspace/EditorShell.svelte';
	import { getTool, upsertTool } from '$lib/data/workspaceResources';

	let saving = $state(false);
	let missing = $state(false);
	let name = $state('');
	let id = $state('');
	let description = $state('');
	let content = $state('');
	let createdAt = $state(Date.now());
	let manifest = $state<Record<string, unknown>>({});

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
		const existing = editId ? getTool(editId) : null;
		if (!existing) {
			missing = true;
			return;
		}
		id = existing.id;
		name = existing.name;
		description = existing.description || '';
		content = existing.content;
		createdAt = existing.createdAt;
		manifest = existing.meta?.manifest ?? {};
	});

	const onSave = () => {
		if (!id || !name.trim()) return;
		saving = true;
		upsertTool({
			id,
			name: name.trim(),
			description: description.trim(),
			content,
			meta: { manifest },
			owner: 'you',
			createdAt,
			updatedAt: Date.now()
		});
		saving = false;
		void goto(withParams('/workspace/tools'));
	};
</script>

{#if missing}
	<div class="px-2 py-16 text-center text-sm text-gray-500">
		未找到该工具。
		<button
			type="button"
			class="mt-3 block w-full text-white underline"
			onclick={() => void goto(withParams('/workspace/tools'))}
		>
			返回列表
		</button>
	</div>
{:else}
	<EditorShell
		title="编辑工具"
		subtitle={id}
		{saving}
		saveLabel="保存"
		onBack={() => void goto(withParams('/workspace/tools'))}
		{onSave}
	>
		<div>
			<label class={label} for="tool-name">名称</label>
			<input id="tool-name" class={field} bind:value={name} />
		</div>
		<div>
			<label class={label} for="tool-id">ID</label>
			<input id="tool-id" class="{field} opacity-60" value={id} disabled />
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
{/if}
