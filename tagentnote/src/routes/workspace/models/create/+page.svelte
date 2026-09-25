<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import ModelEditor from '$lib/components/workspace/Models/ModelEditor.svelte';
	import { upsertModel, type WorkspaceModel } from '$lib/data/workspaceResources';

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
	<title>创建模型 · 工作空间</title>
</svelte:head>

<ModelEditor onBack={back} {onSave} />
