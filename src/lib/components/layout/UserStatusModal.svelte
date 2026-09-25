<script lang="ts">
	import EmojiPicker from '$lib/components/common/EmojiPicker.svelte';

	type Props = {
		open?: boolean;
		initialEmoji?: string;
		initialMessage?: string;
		onClose?: () => void;
		onSave?: (value: { emoji: string; message: string }) => void | Promise<void>;
		onToast?: (message: string, type?: 'success' | 'error') => void;
	};

	let {
		open = false,
		initialEmoji = '',
		initialMessage = '',
		onClose = () => {},
		onSave = () => {},
		onToast = () => {}
	}: Props = $props();

	let emoji = $state('');
	let message = $state('');
	let loading = $state(false);

	$effect(() => {
		if (open) {
			emoji = initialEmoji;
			message = initialMessage;
			loading = false;
			queueMicrotask(() => {
				const input = document.getElementById('status-message') as HTMLInputElement | null;
				input?.focus();
				input?.select();
			});
		} else {
			emoji = '';
			message = '';
			loading = false;
		}
	});

	const submit = async () => {
		const trimmed = message.trim();
		if (!trimmed) {
			onToast('请填写状态内容', 'error');
			return;
		}
		loading = true;
		try {
			await onSave({ emoji, message: trimmed });
			onToast('状态已更新', 'success');
			onClose();
		} catch (error) {
			onToast(error instanceof Error ? error.message : '更新状态失败', 'error');
		} finally {
			loading = false;
		}
	};
</script>

{#if open}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 px-4"
		onclick={() => {
			if (!loading) onClose();
		}}
	>
		<div
			class="w-full max-w-sm rounded-2xl border border-gray-800 bg-gray-850 text-gray-100 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			role="dialog"
			aria-modal="true"
			aria-label="设置您的状态"
		>
			<div class="flex justify-between px-5 pt-4 pb-1 text-gray-300">
				<div class="self-center text-lg font-medium">设置您的状态</div>
				<button
					type="button"
					class="self-center"
					onclick={onClose}
					aria-label="关闭"
					disabled={loading}
				>
					<svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
						<path stroke-linecap="round" d="M6 6l12 12M18 6L6 18"></path>
					</svg>
				</button>
			</div>

			<div class="flex w-full flex-col px-5 pb-4 text-gray-200">
				<form
					class="flex w-full flex-col"
					onsubmit={(e) => {
						e.preventDefault();
						void submit();
					}}
				>
					<div>
						<div class="mb-1.5 text-xs text-gray-500">状态</div>

						<div
							class="flex items-center gap-3 rounded-xl border border-gray-800/80 px-2.5 py-2"
						>
							<EmojiPicker
								selected={emoji}
								onSubmit={(value) => {
									emoji = value;
								}}
							>
								<div class="flex items-center">
									{#if emoji}
										<span class="text-lg leading-none">{emoji}</span>
									{:else}
										<svg
											class="size-5 text-gray-300"
											viewBox="0 0 24 24"
											fill="none"
											stroke="currentColor"
											stroke-width="1.5"
											aria-hidden="true"
										>
											<path
												stroke-linecap="round"
												stroke-linejoin="round"
												d="M15.182 15.182a4.5 4.5 0 0 1-6.364 0M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM9.75 9.75c.008-.034.017-.067.026-.1a.15.15 0 0 1 .222-.062.15.15 0 0 1 .075.112c.01.033.018.066.026.1M14.25 9.75c.008-.034.017-.067.026-.1a.15.15 0 0 1 .222-.062.15.15 0 0 1 .075.112c.01.033.018.066.026.1"
											></path>
										</svg>
									{/if}
								</div>
							</EmojiPicker>

							<input
								id="status-message"
								type="text"
								bind:value={message}
								class="w-full flex-1 bg-transparent text-sm outline-none placeholder:text-gray-600"
								placeholder="聊聊您的想法吧！"
								autocomplete="off"
								required
							/>

							<button
								type="button"
								class="shrink-0 text-gray-400 transition hover:text-white"
								aria-label="清除状态"
								onclick={() => {
									emoji = '';
									message = '';
								}}
							>
								<svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
									<path stroke-linecap="round" d="M6 6l12 12M18 6L6 18"></path>
								</svg>
							</button>
						</div>
					</div>

					<div class="flex justify-end gap-1.5 pt-3 text-sm font-medium">
						<button
							type="submit"
							class={`flex flex-row items-center space-x-1 rounded-full bg-white px-3.5 py-1.5 text-sm font-medium text-black transition hover:bg-gray-100 ${
								loading ? 'cursor-not-allowed opacity-70' : ''
							}`}
							disabled={loading}
						>
							保存
							{#if loading}
								<span
									class="ml-2 inline-block size-3.5 animate-spin rounded-full border-2 border-black/20 border-t-black"
									aria-hidden="true"
								></span>
							{/if}
						</button>
					</div>
				</form>
			</div>
		</div>
	</div>
{/if}
