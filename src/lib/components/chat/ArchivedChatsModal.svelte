<script lang="ts">
	type ArchivedChat = {
		id: string;
		title: string;
		updatedAt: number;
	};

	type Props = {
		open?: boolean;
		chats?: ArchivedChat[];
		onClose?: () => void;
		onUnarchive?: (chatId: string) => void;
		onOpenChat?: (chatId: string) => void;
	};

	let {
		open = false,
		chats = [],
		onClose = () => {},
		onUnarchive = () => {},
		onOpenChat = () => {}
	}: Props = $props();

	const formatTime = (ts: number) => {
		try {
			return new Date(ts).toLocaleString('zh-CN', {
				month: 'numeric',
				day: 'numeric',
				hour: '2-digit',
				minute: '2-digit'
			});
		} catch {
			return '';
		}
	};
</script>

{#if open}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-[80] flex items-center justify-center bg-black/55 px-4"
		onclick={onClose}
	>
		<div
			class="flex max-h-[80vh] w-full max-w-lg flex-col rounded-2xl border border-gray-800 bg-gray-850 text-white shadow-2xl"
			onclick={(event) => event.stopPropagation()}
			role="dialog"
			aria-modal="true"
			aria-label="已归档对话"
		>
			<div class="flex shrink-0 items-center justify-between border-b border-gray-800 px-5 py-4">
				<h2 class="text-lg font-medium">已归档对话</h2>
				<button
					type="button"
					class="rounded-lg p-1 text-gray-400 transition hover:bg-gray-800 hover:text-white"
					onclick={onClose}
					aria-label="关闭"
				>
					<svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
						<path stroke-linecap="round" d="M6 6l12 12M18 6L6 18"></path>
					</svg>
				</button>
			</div>

			<div class="min-h-0 flex-1 overflow-y-auto px-3 py-3">
				{#if chats.length === 0}
					<p class="px-2 py-10 text-center text-sm text-gray-500">暂无已归档对话</p>
				{:else}
					<ul class="space-y-1">
						{#each chats as chat (chat.id)}
							<li
								class="flex items-center gap-2 rounded-xl px-2 py-2 transition hover:bg-gray-800/80"
							>
								<button
									type="button"
									class="min-w-0 flex-1 text-left"
									onclick={() => onOpenChat(chat.id)}
								>
									<p class="truncate text-sm text-gray-100">{chat.title}</p>
									<p class="text-[11px] text-gray-500">{formatTime(chat.updatedAt)}</p>
								</button>
								<button
									type="button"
									class="shrink-0 rounded-lg px-2 py-1 text-xs text-gray-300 transition hover:bg-gray-700 hover:text-white"
									onclick={() => onUnarchive(chat.id)}
								>
									取消归档
								</button>
							</li>
						{/each}
					</ul>
				{/if}
			</div>
		</div>
	</div>
{/if}
