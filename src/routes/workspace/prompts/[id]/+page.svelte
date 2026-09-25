<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';

	import PromptEditor from '$lib/components/workspace/Prompts/PromptEditor.svelte';
	import { getPrompt, upsertPrompt, type WorkspacePrompt } from '$lib/data/workspaceResources';

	let initial = $state<WorkspacePrompt | null>(null);
	let missing = $state(false);
	let ready = $state(false);

	const withParams = (path: string) => {
		const params = new URLSearchParams();
		const model = $page.url.searchParams.get('model');
		const chat = $page.url.searchParams.get('chat');
		if (model) params.set('model', model);
		if (chat) params.set('chat', chat);
		const search = params.toString();
		return search ? `${path}?${search}` : path;
	};

	const back = () => void goto(withParams('/workspace/prompts'));

	onMount(() => {
		const editId = $page.params.id || '';
		const existing = editId ? getPrompt(editId) : null;
		if (!existing) {
			missing = true;
		} else {
			initial = existing;
		}
		ready = true;
	});

	const onSave = (prompt: WorkspacePrompt) => {
		upsertPrompt(prompt);
		initial = prompt;
	};
</script>

<svelte:head>
	<title>编辑提示词 · 工作空间</title>
</svelte:head>

{#if ready && missing}
	<div class="px-2 py-16 text-center text-sm text-gray-500">
		未找到该提示词。
		<button type="button" class="mt-3 block w-full text-white underline" onclick={back}>
			返回列表
		</button>
	</div>
{:else if ready && initial}
	{#key initial.id}
		<PromptEditor edit {initial} onBack={back} {onSave} />
	{/key}
{/if}
