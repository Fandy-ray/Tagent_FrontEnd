<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';

	import MockSidebar from '$lib/components/chat/MockSidebar.svelte';
	import { loadQaChats, type QaChat } from '$lib/data/qaConversations';

	let { children } = $props();

	let sidebarOpen = $state(true);
	let modelId = $state($page.url.searchParams.get('model') ?? '');
	let chats = $state<{ id: string; title: string; updatedAt: number }[]>([]);
	let searchChats = $state<QaChat[]>([]);
	let activeChatId = $state<string | null>($page.url.searchParams.get('chat'));

	const tabs = [
		{ href: '/workspace/models', label: '模型' },
		{ href: '/workspace/knowledge', label: '知识库' },
		{ href: '/workspace/prompts', label: '提示词' },
		{ href: '/workspace/skills', label: '技能' },
		{ href: '/workspace/tools', label: '工具' }
	] as const;

	const withParams = (path: string, extra?: Record<string, string>) => {
		const params = new URLSearchParams();
		if (modelId) params.set('model', modelId);
		if (activeChatId) params.set('chat', activeChatId);
		if (extra) {
			for (const [key, value] of Object.entries(extra)) {
				if (value) params.set(key, value);
			}
		}
		const search = params.toString();
		return search ? `${path}?${search}` : path;
	};

	const isActiveTab = (href: string) => $page.url.pathname.startsWith(href);

	onMount(() => {
		const stored = loadQaChats();
		searchChats = stored.chats;
		chats = stored.chats.map((chat) => ({
			id: chat.id,
			title: chat.title,
			updatedAt: chat.updatedAt
		}));
		if (!activeChatId) {
			activeChatId = stored.activeId;
		}
	});

	const goQa = (opts?: { newChat?: boolean; chatId?: string }) => {
		const params = new URLSearchParams();
		if (modelId) params.set('model', modelId);
		if (!opts?.newChat) {
			const chatId = opts?.chatId ?? activeChatId;
			if (chatId) params.set('chat', chatId);
		}
		const search = params.toString();
		void goto(search ? `/qa?${search}` : '/qa');
	};
</script>

<svelte:head>
	<title>工作空间 | TAgent</title>
</svelte:head>

<main class="flex h-screen overflow-hidden bg-[#171717] text-white">
	{#if sidebarOpen}
		<MockSidebar
			{activeChatId}
			{chats}
			{searchChats}
			{modelId}
			activeNav="workspace"
			onHome={() => goto('/agent-select')}
			onNewChat={() => goQa({ newChat: true })}
			onSelectChat={(chatId) => goQa({ chatId })}
			onOpenNotes={() => goto(withParams('/notebook', { from: 'qa' }))}
			onOpenWorkspace={() => goto(withParams('/workspace/models'))}
			onClose={() => {
				sidebarOpen = false;
			}}
		/>
	{/if}

	<section class="relative flex min-w-0 flex-1 flex-col bg-[#171717]">
		<nav class="shrink-0 px-2.5 pt-1.5 select-none">
			<div class="flex items-center gap-1">
				{#if !sidebarOpen}
					<button
						type="button"
						class="mr-1 flex rounded-lg p-1.5 text-gray-400 transition hover:bg-gray-850 hover:text-white"
						onclick={() => {
							sidebarOpen = true;
						}}
						aria-label="打开侧边栏"
					>
						<svg
							class="size-5"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="1.5"
							aria-hidden="true"
						>
							<rect x="3" y="4" width="18" height="16" rx="2"></rect>
							<path d="M9 4v16"></path>
						</svg>
					</button>
				{/if}

				<div
					class="flex w-fit touch-auto gap-1 overflow-x-auto rounded-full bg-transparent py-1 text-center text-sm font-medium scrollbar-none"
				>
					{#each tabs as tab (tab.href)}
						<a
							draggable="false"
							aria-current={isActiveTab(tab.href) ? 'page' : undefined}
							class={`min-w-fit p-1.5 transition select-none ${
								isActiveTab(tab.href)
									? 'text-white'
									: 'text-gray-600 hover:text-white'
							}`}
							href={withParams(tab.href)}
						>
							{tab.label}
						</a>
					{/each}
				</div>
			</div>
		</nav>

		<div class="min-h-0 flex-1 overflow-y-auto px-3 pb-1 md:px-[18px]" id="workspace-container">
			{@render children()}
		</div>
	</section>
</main>
