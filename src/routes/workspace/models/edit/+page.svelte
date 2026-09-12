<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import ModelEditor from '$lib/components/workspace/Models/ModelEditor.svelte';
	import { getModel, upsertModel, type WorkspaceModel } from '$lib/data/workspaceResources';

	const editId = $derived($page.url.searchParams.get('id') || '');
	const initial = $derived(editId ? getModel(editId) : null);

	const withParams = (path: string) => {
		const params = new URLSearchParams();
		const model = $page.url.searchParams.get('model');
		const chat = $page.url.searchParams.get('chat');
		if (model) params.set('model', model);
		if (chat) params.set('chat', chat);
		const search = params.toString();
		return search ? `${path}?${search}` : path;
	};

	const back = () => void goto(withParams('/workspace/models'));

	const onSave = (model: WorkspaceModel) => {
		upsertModel(model);
		back();
	};
</script>

<svelte:head>
	<title>编辑模型 · 工作空间</title>
</svelte:head>

{#if !initial}
	<div class="px-2 py-10 text-center text-sm text-gray-500">
		未找到该模型。
		<button type="button" class="ml-2 underline hover:text-white" onclick={back}>返回列表</button>
	</div>
{:else}
	<ModelEditor edit {initial} onBack={back} {onSave} />
{/if}
