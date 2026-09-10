<script lang="ts">
	export type ChatSummary = {
		id: string;
		title: string;
		/** Date.now() 毫秒数，用来分组和排序。 */
		updatedAt: number;
	};

	type Props = {
		activeChatId?: string | null;
		chats?: ChatSummary[];
		modelId?: string;
		onHome?: () => void;
		onNewChat?: () => void;
		onSelectChat?: (chatId: string) => void;
		onClose?: () => void;
	};

	let {
		activeChatId = null,
		chats = [],
		modelId = '',
		onHome = () => {},
		onNewChat = () => {},
		onSelectChat = () => {},
		onClose = () => {}
	}: Props = $props();

	let searchOpen = $state(false);
	let searchQuery = $state('');

	// 会话列表来自本次页面里真实发生过的提问，没有则为空。
	const sortedChats = $derived([...chats].sort((a, b) => b.updatedAt - a.updatedAt));

	const filteredChats = $derived(
		searchQuery.trim()
			? sortedChats.filter((chat) => chat.title.includes(searchQuery.trim()))
			: sortedChats
	);

	const startOfToday = () => {
		const date = new Date();
		date.setHours(0, 0, 0, 0);
		return date.getTime();
	};

	const DAY = 24 * 60 * 60 * 1000;

	const groupOf = (chat: ChatSummary) => {
		const today = startOfToday();

		if (chat.updatedAt >= today) {
			return '今天';
		}
		if (chat.updatedAt >= today - DAY) {
			return '昨天';
		}
		if (chat.updatedAt >= today - 7 * DAY) {
			return '过去 7 天';
		}
		return '更早';
	};

	const timeLabel = (chat: ChatSummary) => {
		const minutes = Math.floor((Date.now() - chat.updatedAt) / 60000);

		if (minutes < 1) {
			return '刚刚';
		}
		if (minutes < 60) {
			return `${minutes}分钟前`;
		}
		if (minutes < 60 * 24) {
			return `${Math.floor(minutes / 60)}小时前`;
		}
		return `${Math.floor(minutes / (60 * 24))}天前`;
	};

	const GROUP_ORDER = ['今天', '昨天', '过去 7 天', '更早'];

	const groupedChats = $derived(
		GROUP_ORDER.map((label) => ({
			label,
			items: filteredChats.filter((chat) => groupOf(chat) === label)
		})).filter((group) => group.items.length > 0)
	);
</script>

<aside
	class="flex h-screen w-[260px] shrink-0 select-none flex-col overflow-hidden border-r border-white/[0.04] bg-[#111111] text-sm text-gray-200"
>
	<header class="flex h-12 shrink-0 items-center gap-2 px-2">
		<button
			type="button"
			class="flex size-8 shrink-0 items-center justify-center rounded-xl transition hover:bg-gray-900"
			onclick={onHome}
			title="返回选择智能体"
			aria-label="返回选择智能体"
		>
			<div class="flex size-6 items-center justify-center rounded-full bg-white text-[9px] font-bold text-black">
				T
			</div>
		</button>

		<button
			type="button"
			class="min-w-0 flex-1 truncate px-1 text-left text-xs font-medium text-white"
			onclick={onHome}
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
			</button>

			<button
				type="button"
				class="group flex w-full items-center gap-3 rounded-2xl px-2.5 py-2 text-gray-200 outline-none transition hover:bg-gray-900"
				onclick={() => {
					searchOpen = !searchOpen;
					if (!searchOpen) searchQuery = '';
				}}
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

			{#if searchOpen}
				<input
					class="mb-1 w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-gray-100 outline-none placeholder:text-gray-500 focus:border-white/20"
					placeholder="搜索对话"
					bind:value={searchQuery}
				/>
			{/if}
		</nav>

		<section>
			<div class="px-2.5 pb-2 pt-1 text-xs font-medium text-gray-500">
				对话
			</div>

			{#each groupedChats as group (group.label)}
				<div class="px-2.5 pb-1.5 pt-1 text-xs font-medium text-gray-500">
					{group.label}
				</div>
				<div class="space-y-0.5">
					{#each group.items as chat (chat.id)}
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
								{timeLabel(chat)}
							</span>
						</button>
					{/each}
				</div>
			{/each}

			{#if filteredChats.length === 0}
				<p class="px-2.5 py-6 text-xs leading-5 text-gray-500">
					{#if chats.length === 0}
						还没有对话。提问后会出现在这里，刷新页面即清空。
					{:else}
						没有匹配的对话
					{/if}
				</p>
			{/if}
		</section>
	</div>

	<footer class="relative shrink-0 px-1.5 pb-2 pt-4">
		<div
			class="pointer-events-none absolute inset-x-0 -top-8 h-12 bg-gradient-to-t from-gray-950 to-transparent"
		></div>

		<button
			type="button"
			class="relative flex w-full items-center rounded-2xl px-1.5 py-2 transition hover:bg-gray-900"
			onclick={onHome}
			title="返回选择智能体"
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
				<p class="truncate text-[11px] text-gray-500">
					{modelId || '未选择模型'}
				</p>
			</div>
		</button>
	</footer>
</aside>
