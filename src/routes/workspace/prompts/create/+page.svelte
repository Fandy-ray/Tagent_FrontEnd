<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';

	import PromptEditor from '$lib/components/workspace/Prompts/PromptEditor.svelte';
	import { upsertPrompt, type WorkspacePrompt } from '$lib/data/workspaceResources';

	let ready = $state(false);
	let initial = $state<WorkspacePrompt | null>(null);

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
		const raw = sessionStorage.getItem('prompt');
		if (raw) {
			try {
				const clone = JSON.parse(raw) as WorkspacePrompt & { name?: string };
				initial = {
					id: '',
					title: clone.title || clone.name || '',
					command: (clone.command || '').replace(/^\/+/, ''),
					content: clone.content || '',
					tags: clone.tags || [],
					isActive: clone.isActive !== false,
					owner: 'you',
					createdAt: Date.now(),
					updatedAt: Date.now()
				};
			} catch {
				/* ignore */
			}
			sessionStorage.removeItem('prompt');
		}
		ready = true;
	});

	const onSave = (prompt: WorkspacePrompt) => {
		upsertPrompt(prompt);
		back();
	};
</script>

<svelte:head>
	<title>创建提示词 · 工作空间</title>
</svelte:head>

{#if ready}
	<PromptEditor {initial} onBack={back} {onSave} />
{/if}
