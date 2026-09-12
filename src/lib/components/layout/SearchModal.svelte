<script lang="ts">
	import { onDestroy, tick, untrack } from 'svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import SearchInput from '$lib/components/layout/Sidebar/SearchInput.svelte';
	import MarkdownContent from '$lib/components/chat/MarkdownContent.svelte';
	import PencilSquare from '$lib/components/icons/PencilSquare.svelte';
	import PageEdit from '$lib/components/icons/PageEdit.svelte';
	import type { QaChat, QaMessage } from '$lib/data/qaConversations';
	import type { QaFolder } from '$lib/data/qaFolders';

	type SearchChatItem = {
		id: string;
		title: string;
		updatedAt: number;
		time_range: string;
		folderId?: string | null;
		archived?: boolean;
		tags?: string[];
		messages: QaMessage[];
	};

	type Props = {
		show?: boolean;
		chats?: QaChat[];
		folders?: QaFolder[];
		onClose?: () => void;
		onSelectChat?: (chatId: string) => void;
		onNewChat?: (query?: string) => void;
		onOpenNotes?: (query?: string) => void;
	};

	let {
		show = $bindable(false),
		chats = [],
		folders = [],
		onClose = () => {},
		onSelectChat = () => {},
		onNewChat = () => {},
		onOpenNotes = () => {}
	}: Props = $props();

	const MONTH_NAMES = [
		'一月',
		'二月',
		'三月',
		'四月',
		'五月',
		'六月',
		'七月',
		'八月',
		'九月',
		'十月',
		'十一月',
		'十二月'
	];

	const getTimeRange = (updatedAt: number) => {
		const now = new Date();
		const date = new Date(updatedAt);
		const diffDays = (now.getTime() - date.getTime()) / (1000 * 3600 * 24);

		if (
			now.getFullYear() === date.getFullYear() &&
			now.getMonth() === date.getMonth() &&
			now.getDate() === date.getDate()
		) {
			return '今天';
		}
		if (
			now.getFullYear() === date.getFullYear() &&
			now.getMonth() === date.getMonth() &&
			now.getDate() - date.getDate() === 1
		) {
			return '昨天';
		}
		if (diffDays <= 7) return '过去 7 天';
		if (diffDays <= 30) return '过去 30 天';
		if (now.getFullYear() === date.getFullYear()) return MONTH_NAMES[date.getMonth()];
		return String(date.getFullYear());
	};

	const formatCalendar = (updatedAt: number) => {
		const now = new Date();
		const date = new Date(updatedAt);
		const startToday = new Date(now);
		startToday.setHours(0, 0, 0, 0);
		const startDate = new Date(date);
		startDate.setHours(0, 0, 0, 0);
		const dayDiff = Math.round((startToday.getTime() - startDate.getTime()) / 86400000);

		if (dayDiff === 0) return '今天';
		if (dayDiff === 1) return '昨天';
		if (dayDiff > 1 && dayDiff < 7) {
			return ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][date.getDay()];
		}
		return `${date.getFullYear()}/${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getDate()).padStart(2, '0')}`;
	};

	const collectTags = (list: QaChat[]) => {
		const map = new Map<string, string>();
		for (const chat of list) {
			for (const tag of chat.tags ?? []) {
				const id = tag.replaceAll(' ', '_').toLowerCase();
				map.set(id, tag);
			}
			for (const message of chat.messages) {
				for (const tag of message.tags ?? []) {
					const id = tag.replaceAll(' ', '_').toLowerCase();
					map.set(id, tag);
				}
			}
		}
		return [...map.entries()].map(([id, name]) => ({ id, name }));
	};

	const searchChats = (queryText: string, page: number): SearchChatItem[] => {
		const pageSize = 60;
		const words = queryText.toLowerCase().trim().split(/\s+/).filter(Boolean);

		const tagIds = words
			.filter((w) => w.startsWith('tag:'))
			.map((w) => w.replace('tag:', '').replaceAll(' ', '_').toLowerCase());
		const folderKeys = words
			.filter((w) => w.startsWith('folder:'))
			.map((w) => w.replace('folder:', ''));

		let isArchived: boolean | null = null;
		if (words.includes('archived:true')) isArchived = true;
		else if (words.includes('archived:false')) isArchived = false;

		let isPinned: boolean | null = null;
		if (words.includes('pinned:true')) isPinned = true;
		else if (words.includes('pinned:false')) isPinned = false;

		let isShared: boolean | null = null;
		if (words.includes('shared:true')) isShared = true;
		else if (words.includes('shared:false')) isShared = false;

		const textWords = words.filter(
			(w) =>
				!w.startsWith('tag:') &&
				!w.startsWith('folder:') &&
				!w.startsWith('pinned:') &&
				!w.startsWith('archived:') &&
				!w.startsWith('shared:')
		);
		const text = textWords.join(' ');

		const folderIds = new Set<string>();
		for (const key of folderKeys) {
			const needle = key.replaceAll(' ', '_').toLowerCase();
			for (const folder of folders) {
				const id = folder.name.replaceAll(' ', '_').toLowerCase();
				if (!needle || id === needle || id.startsWith(needle) || folder.name.includes(key)) {
					folderIds.add(folder.id);
				}
			}
		}

		let filtered = [...chats];

		if (isArchived === true) filtered = filtered.filter((c) => Boolean(c.archived));
		else if (isArchived === false) filtered = filtered.filter((c) => !c.archived);
		else filtered = filtered.filter((c) => !c.archived);

		// 本地暂无置顶/分享字段：pinned:true / shared:true → 无结果；*:false → 全部
		if (isPinned === true || isShared === true) filtered = [];

		if (folderIds.size > 0) {
			filtered = filtered.filter((c) => c.folderId && folderIds.has(c.folderId));
		}

		if (tagIds.includes('none')) {
			filtered = filtered.filter((c) => {
				const chatTags = [
					...(c.tags ?? []),
					...c.messages.flatMap((m) => m.tags ?? [])
				];
				return chatTags.length === 0;
			});
		} else if (tagIds.length > 0) {
			filtered = filtered.filter((c) => {
				const chatTags = [
					...(c.tags ?? []),
					...c.messages.flatMap((m) => m.tags ?? [])
				].map((t) => t.replaceAll(' ', '_').toLowerCase());
				return tagIds.every((id) => chatTags.includes(id));
			});
		}

		if (text) {
			filtered = filtered.filter((c) => {
				if (c.title.toLowerCase().includes(text)) return true;
				return c.messages.some((m) => m.content.toLowerCase().includes(text));
			});
		}

		filtered.sort((a, b) => b.updatedAt - a.updatedAt);

		return filtered.slice(0, page * pageSize).map((chat) => ({
			id: chat.id,
			title: chat.title,
			updatedAt: chat.updatedAt,
			time_range: getTimeRange(chat.updatedAt),
			folderId: chat.folderId,
			archived: chat.archived,
			tags: chat.tags,
			messages: chat.messages
		}));
	};

	let query = $state('');
	let page = $state(1);
	let chatList = $state<SearchChatItem[] | null>(null);
	let chatListLoading = $state(false);
	let allChatsLoaded = $state(false);
	let searchDebounceTimeout: ReturnType<typeof setTimeout> | null = null;
	let selectedIdx = $state<number | null>(null);
	let previewMessages = $state<QaMessage[] | null>(null);

	const actions = [
		{
			label: '开始新的对话',
			icon: PencilSquare,
			onClick: async () => {
				onNewChat(query);
				show = false;
				onClose();
			}
		},
		{
			label: '创建新笔记',
			icon: PageEdit,
			onClick: async () => {
				onOpenNotes(query);
				show = false;
				onClose();
			}
		}
	];

	const tagOptions = $derived(collectTags(chats));
	const folderOptions = $derived(folders.map((f) => ({ id: f.id, name: f.name })));

	const loadChatPreview = async (idx: number | null) => {
		if (!chatList || chatList.length === 0 || idx === null) {
			previewMessages = null;
			return;
		}
		const selectedChatIdx = idx - actions.length;
		if (selectedChatIdx < 0 || selectedChatIdx >= chatList.length) {
			previewMessages = null;
			return;
		}
		previewMessages = chatList[selectedChatIdx].messages ?? [];
		await tick();
		const el = document.getElementById('chat-preview');
		if (el) el.scrollTop = el.scrollHeight;
	};

	const searchHandler = () => {
		if (!show) return;
		if (searchDebounceTimeout) clearTimeout(searchDebounceTimeout);

		page = 1;
		chatList = null;
		previewMessages = null;
		selectedIdx = null;

		const run = () => {
			const list = searchChats(query, page);
			chatList = list;
			allChatsLoaded = list.length < page * 60;
		};

		if (query === '') {
			run();
		} else {
			searchDebounceTimeout = setTimeout(run, 500);
		}
	};

	const loadMoreChats = () => {
		if (chatListLoading || allChatsLoaded || !chatList) return;
		chatListLoading = true;
		page += 1;
		const list = searchChats(query, page);
		const existing = new Set(chatList.map((c) => c.id));
		const unique = list.filter((c) => !existing.has(c.id));
		allChatsLoaded = unique.length === 0;
		chatList = [...chatList, ...unique];
		chatListLoading = false;
	};

	$effect(() => {
		if (!show) return;
		untrack(() => {
			query = '';
			page = 1;
			searchHandler();
		});
		queueMicrotask(() => document.getElementById('search-input')?.focus());
	});

	$effect(() => {
		void loadChatPreview(selectedIdx);
	});

	const onKeyDown = (e: KeyboardEvent) => {
		if (document.getElementById('search-options-container') || !show) return;

		if (e.code === 'Escape') {
			show = false;
			onClose();
		} else if (e.code === 'Enter') {
			const item = document.querySelector<HTMLElement>('[data-arrow-selected="true"]');
			if (item) {
				item.click();
				show = false;
			}
		} else if (e.code === 'ArrowDown') {
			const searchInput = document.getElementById('search-input');
			if (searchInput && document.activeElement === searchInput) {
				searchInput.blur();
				selectedIdx = 0;
				return;
			}
			selectedIdx = Math.min((selectedIdx ?? -1) + 1, (chatList ?? []).length - 1 + actions.length);
		} else if (e.code === 'ArrowUp') {
			if (selectedIdx === 0) {
				const searchInput = document.getElementById('search-input');
				if (searchInput && document.activeElement !== searchInput) {
					searchInput.focus();
					selectedIdx = null;
					return;
				}
			}
			selectedIdx = Math.max((selectedIdx ?? 0) - 1, 0);
		}

		document
			.querySelector('[data-arrow-selected="true"]')
			?.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });
	};

	$effect(() => {
		if (!show) return;
		document.addEventListener('keydown', onKeyDown);
		return () => document.removeEventListener('keydown', onKeyDown);
	});

	onDestroy(() => {
		if (searchDebounceTimeout) clearTimeout(searchDebounceTimeout);
	});
</script>

<Modal size="xl" bind:show>
	<div class="py-3 text-gray-300">
		<div class="px-4 pb-1.5">
			<SearchInput
				bind:value={query}
				placeholder="搜索"
				showClearButton={true}
				tags={tagOptions}
				folders={folderOptions}
				onInput={searchHandler}
				onFocus={() => {
					selectedIdx = null;
					previewMessages = null;
				}}
				onKeydown={(e) => {
					if (e.code === 'Enter' && (chatList ?? []).length > 0) {
						const item = document.querySelector<HTMLElement>('[data-arrow-selected="true"]');
						item?.click();
						show = false;
						return;
					}
					if (e.code === 'ArrowDown') {
						selectedIdx = Math.min(
							(selectedIdx ?? -1) + 1,
							(chatList ?? []).length - 1 + actions.length
						);
					} else if (e.code === 'ArrowUp') {
						selectedIdx = Math.max((selectedIdx ?? 0) - 1, 0);
					} else {
						selectedIdx = 0;
					}
					document
						.querySelector('[data-arrow-selected="true"]')
						?.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });
				}}
			/>
		</div>

		<div class="flex px-4 pb-1">
			<div
				class="scrollbar-hidden flex h-96 max-h-full w-full flex-1 flex-col overflow-y-auto pr-2 md:h-[40rem]"
			>
				<div class="w-full px-2 pb-2 text-xs font-medium text-gray-500">操作</div>

				{#each actions as action, idx (action.label)}
					<button
						type="button"
						class="flex w-full items-center rounded-xl px-3 py-2 text-sm hover:bg-gray-850 {selectedIdx ===
						idx
							? 'bg-gray-850'
							: ''}"
						data-arrow-selected={selectedIdx === idx ? 'true' : undefined}
						draggable="false"
						onmouseenter={() => {
							selectedIdx = idx;
						}}
						onclick={async () => {
							await action.onClick();
						}}
					>
						<div class="pr-2">
							{#if action.label === '开始新的对话'}
								<PencilSquare className="size-4" />
							{:else}
								<PageEdit className="size-4" />
							{/if}
						</div>
						<div class="flex-1 text-left">
							<div class="line-clamp-1 w-full text-ellipsis">{action.label}</div>
						</div>
					</button>
				{/each}

				{#if chatList}
					<hr class="my-3 border-gray-850/30" />

					{#if chatList.length === 0}
						<div class="px-5 py-4 text-center text-xs text-gray-400">未找到结果</div>
					{/if}

					{#each chatList as chat, idx (chat.id)}
						{#if idx === 0 || (idx > 0 && chat.time_range !== chatList[idx - 1].time_range)}
							<div
								class="w-full px-2 pb-2 text-xs font-medium text-gray-500 {idx === 0
									? ''
									: 'pt-5'}"
							>
								{chat.time_range}
							</div>
						{/if}

						<button
							type="button"
							class="flex w-full items-center justify-between rounded-xl px-3 py-2 text-sm hover:bg-gray-850 {selectedIdx ===
							idx + actions.length
								? 'bg-gray-850'
								: ''}"
							draggable="false"
							data-arrow-selected={selectedIdx === idx + actions.length ? 'true' : undefined}
							onmouseenter={() => {
								selectedIdx = idx + actions.length;
							}}
							onclick={() => {
								onSelectChat(chat.id);
								show = false;
								onClose();
							}}
						>
							<div class="flex-1">
								<div class="line-clamp-1 w-full text-ellipsis text-left">{chat.title}</div>
							</div>
							<div class="shrink-0 pl-3 text-xs text-gray-400">
								{formatCalendar(chat.updatedAt)}
							</div>
						</button>
					{/each}

					{#if !allChatsLoaded}
						<button
							type="button"
							class="flex w-full items-center justify-center gap-2 py-4 text-xs text-gray-400"
							onclick={loadMoreChats}
						>
							{#if chatListLoading}
								<Spinner className="size-4" />
								加载中...
							{:else}
								加载更多
							{/if}
						</button>
					{/if}
				{:else}
					<div class="flex h-full w-full items-center justify-center">
						<Spinner className="size-5" />
					</div>
				{/if}
			</div>

			<div
				id="chat-preview"
				class="scrollbar-hidden @container hidden h-96 w-full overflow-y-auto md:flex md:h-[40rem] md:flex-1"
			>
				{#if previewMessages === null}
					<div class="flex h-full w-full items-center justify-center text-sm text-gray-400">
						选择一个对话以预览
					</div>
				{:else if previewMessages.length === 0}
					<div class="flex h-full w-full items-center justify-center text-sm text-gray-400">
						此对话暂无消息
					</div>
				{:else}
					<div class="flex h-full w-full flex-col gap-4 px-3 pt-4 pb-8">
						{#each previewMessages as message (message.id)}
							{#if message.role === 'user'}
								<div class="ml-auto max-w-[85%] rounded-3xl bg-gray-800 px-4 py-2 text-sm text-gray-100">
									<p class="whitespace-pre-wrap">{message.content}</p>
								</div>
							{:else}
								<div class="max-w-full text-sm text-gray-200">
									<div class="mb-1 text-xs font-medium text-gray-400">
										{message.model ?? '助手'}
									</div>
									<MarkdownContent content={message.content} />
								</div>
							{/if}
						{/each}
					</div>
				{/if}
			</div>
		</div>
	</div>
</Modal>
