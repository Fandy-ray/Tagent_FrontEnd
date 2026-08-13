<script lang="ts">
	type MockChat = {
		id: string;
		title: string;
		timeRange: '昨天' | '过去 7 天';
		timeLabel: string;
	};

	type Props = {
		activeChatId?: string | null;
		onNewChat?: () => void;
		onSelectChat?: (chatId: string) => void;
		onClose?: () => void;
	};

	let {
		activeChatId = null,
		onNewChat = () => {},
		onSelectChat = () => {},
		onClose = () => {}
	}: Props = $props();

	const mockChats: MockChat[] = [
		{
			id: 'chat-1',
			title: '离散事件仿真的基本概念',
			timeRange: '昨天',
			timeLabel: '22小时前'
		},
		{
			id: 'chat-2',
			title: '系统模型的分类',
			timeRange: '昨天',
			timeLabel: '22小时前'
		},
		{
			id: 'chat-3',
			title: '连续系统仿真方法',
			timeRange: '过去 7 天',
			timeLabel: '5天前'
		}
	];

	const yesterdayChats = mockChats.filter((chat) => chat.timeRange === '昨天');
	const recentChats = mockChats.filter((chat) => chat.timeRange === '过去 7 天');
</script>

<aside
	class="flex h-screen w-[260px] shrink-0 select-none flex-col overflow-hidden border-r border-white/[0.04] bg-[#111111] text-sm text-gray-200"
>
	<header class="flex h-12 shrink-0 items-center gap-2 px-2">
		<button
			type="button"
			class="flex size-8 shrink-0 items-center justify-center rounded-xl transition hover:bg-gray-900"
			onclick={onNewChat}
			aria-label="新建对话"
		>
			<div class="flex size-6 items-center justify-center rounded-full bg-white text-[9px] font-bold text-black">
				OI
			</div>
		</button>

		<button
			type="button"
			class="min-w-0 flex-1 truncate px-1 text-left text-xs font-medium text-white"
			onclick={onNewChat}
		>
			系统建模与仿真智能体
		</button>

		<button
			type="button"
			class="flex size-8 shrink-0 items-center justify-center rounded-xl text-gray-400 transition hover:bg-gray-900 hover:text-white"
			onclick={onClose}
			title="收起侧边栏"
			aria-label="收起侧边栏"
		>
			<svg
				class="size-[18px]"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="1.5"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				<rect x="3" y="4" width="18" height="16" rx="2"></rect>
				<path d="M9 4v16"></path>
			</svg>
		</button>
	</header>

	<div class="min-h-0 flex-1 overflow-y-auto px-[7px] pb-3 pt-1">
		<nav class="pb-4">
			<button
				type="button"
				id="sidebar-new-chat-button"
				class="group flex w-full items-center gap-3 rounded-2xl px-2.5 py-2 text-gray-200 outline-none transition hover:bg-gray-900"
				onclick={onNewChat}
			>
				<svg
					class="size-[18px] shrink-0"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
					aria-hidden="true"
				>
					<path d="M12 20h9"></path>
					<path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"></path>
				</svg>

				<span class="flex-1 text-left text-sm">新对话</span>

				<span class="invisible rounded border border-gray-800 px-1.5 py-0.5 text-[9px] text-gray-600 group-hover:visible">
					Ctrl K
				</span>
			</button>

			<button
				type="button"
				class="group flex w-full items-center gap-3 rounded-2xl px-2.5 py-2 text-gray-200 outline-none transition hover:bg-gray-900"
			>
				<svg
					class="size-[18px] shrink-0"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
					aria-hidden="true"
				>
					<circle cx="11" cy="11" r="7"></circle>
					<path d="m20 20-3.5-3.5"></path>
				</svg>

				<span class="flex-1 text-left text-sm">搜索</span>
			</button>

			<a
	href="/notebook?from=qa&model=deepseek"
	class="flex w-full items-center gap-3 rounded-2xl px-2.5 py-2 text-gray-200 transition hover:bg-gray-900"
>
	<svg
		class="size-[18px] shrink-0"
		viewBox="0 0 24 24"
		fill="none"
		stroke="currentColor"
		stroke-width="2"
		stroke-linecap="round"
		stroke-linejoin="round"
		aria-hidden="true"
	>
		<path d="M6 3h12a2 2 0 0 1 2 2v16H8a4 4 0 0 1-4-4V5a2 2 0 0 1 2-2z"></path>
		<path d="M8 3v18"></path>
	</svg>

	<span class="text-sm">笔记</span>
</a>

			<button
				type="button"
				class="flex w-full items-center gap-3 rounded-2xl px-2.5 py-2 text-gray-200 transition hover:bg-gray-900"
			>
				<svg
					class="size-[18px] shrink-0"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
					aria-hidden="true"
				>
					<rect x="3" y="3" width="7" height="7" rx="1"></rect>
					<rect x="14" y="3" width="7" height="7" rx="1"></rect>
					<rect x="3" y="14" width="7" height="7" rx="1"></rect>
					<rect x="14" y="14" width="7" height="7" rx="1"></rect>
				</svg>

				<span class="text-sm">工作空间</span>
			</button>
		</nav>

		<section>
			<div class="px-2.5 pb-2 text-xs font-medium text-gray-500">
				分组
			</div>

			<div class="px-2.5 pb-2 pt-1 text-xs font-medium text-gray-500">
				对话
			</div>

			<div class="px-2.5 pb-1.5 pt-1 text-xs font-medium text-gray-500">
				昨天
			</div>

			<div class="space-y-0.5">
				{#each yesterdayChats as chat (chat.id)}
					<button
						type="button"
						class={`group flex w-full items-center gap-2 rounded-xl px-2.5 py-2 text-left transition ${
							activeChatId === chat.id
								? 'bg-gray-900 text-white'
								: 'text-gray-300 hover:bg-gray-900'
						}`}
						onclick={() => onSelectChat(chat.id)}
					>
						<span class="min-w-0 flex-1 truncate text-sm">
							{chat.title}
						</span>

						<span class="shrink-0 text-[10px] text-gray-600">
							{chat.timeLabel}
						</span>
					</button>
				{/each}
			</div>

			<div class="px-2.5 pb-1.5 pt-5 text-xs font-medium text-gray-500">
				过去 7 天
			</div>

			<div class="space-y-0.5">
				{#each recentChats as chat (chat.id)}
					<button
						type="button"
						class={`group flex w-full items-center gap-2 rounded-xl px-2.5 py-2 text-left transition ${
							activeChatId === chat.id
								? 'bg-gray-900 text-white'
								: 'text-gray-300 hover:bg-gray-900'
						}`}
						onclick={() => onSelectChat(chat.id)}
					>
						<span class="min-w-0 flex-1 truncate text-sm">
							{chat.title}
						</span>

						<span class="shrink-0 text-[10px] text-gray-600">
							{chat.timeLabel}
						</span>
					</button>
				{/each}
			</div>
		</section>
	</div>

	<footer class="relative shrink-0 px-1.5 pb-2 pt-4">
		<div
			class="pointer-events-none absolute inset-x-0 -top-8 h-12 bg-gradient-to-t from-gray-950 to-transparent"
		></div>

		<button
			type="button"
			class="relative flex w-full items-center rounded-2xl px-1.5 py-2 transition hover:bg-gray-900"
		>
			<div class="relative mr-3 shrink-0">
				<div class="flex size-7 items-center justify-center rounded-full bg-amber-500 text-[10px] font-semibold text-white">
					T
				</div>

				<span class="absolute -bottom-0.5 -right-0.5 size-2.5 rounded-full border-2 border-gray-950 bg-green-500"></span>
			</div>

			<div class="min-w-0 flex-1 text-left">
				<p class="truncate text-sm font-medium text-gray-200">
					Tagent
				</p>
			</div>
		</button>
	</footer>
</aside>