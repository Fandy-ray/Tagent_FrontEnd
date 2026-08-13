<script lang="ts">
	export type MockMessage = {
		id: string;
		role: 'user' | 'assistant';
		content: string;
		model?: string;
	};

	type Props = {
		messages?: MockMessage[];
		generating?: boolean;
		modelName?: string;
		onCopy?: (content: string) => void;
		onRegenerate?: (messageId: string) => void;
	};

	let {
		messages = [],
		generating = false,
		modelName = 'deepseek',
		onCopy = () => {},
		onRegenerate = () => {}
	}: Props = $props();

	const copyMessage = async (content: string) => {
		try {
			await navigator.clipboard.writeText(content);
		} catch {
			onCopy(content);
		}
	};
</script>

<div class="mx-auto w-full max-w-3xl px-4 pt-20 pb-8 md:px-6">
	<div class="flex flex-col gap-7">
		{#each messages as message (message.id)}
			{#if message.role === 'user'}
				<article class="group flex w-full justify-end">
					<div class="max-w-[90%]">
						<div class="rounded-3xl bg-gray-800 px-4 py-2 text-sm leading-6 text-gray-100">
							<p class="whitespace-pre-wrap">{message.content}</p>
						</div>

						<div
							class="mt-1 flex justify-end text-gray-500 opacity-0 transition group-hover:opacity-100"
						>
							<button
								type="button"
								class="rounded-lg p-1.5 transition hover:bg-white/[0.06] hover:text-white"
								onclick={() => copyMessage(message.content)}
								title="复制"
								aria-label="复制用户消息"
							>
								<svg
									class="size-4"
									viewBox="0 0 24 24"
									fill="none"
									stroke="currentColor"
									stroke-width="1.8"
									stroke-linecap="round"
									stroke-linejoin="round"
									aria-hidden="true"
								>
									<rect x="9" y="9" width="11" height="11" rx="2"></rect>
									<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
								</svg>
							</button>
						</div>
					</div>
				</article>
			{:else}
				<article class="group flex w-full">
					<div class="mr-3 mt-1 hidden shrink-0 sm:flex">
						<div
							class="flex size-8 items-center justify-center rounded-full bg-white text-[9px] font-black text-black"
						>
							OI
						</div>
					</div>

					<div class="relative w-0 flex-auto pl-1">
						<div class="mb-1 flex items-center gap-2">
							<span class="line-clamp-1 text-sm font-medium text-white">
								{message.model ?? modelName}
							</span>
						</div>

						<div class="w-full min-w-full">
							<p class="whitespace-pre-wrap text-sm leading-7 text-gray-200">
								{message.content}
							</p>
						</div>

						<div class="mt-2 flex items-center text-gray-500">
							<button
								type="button"
								class="rounded-lg p-1.5 transition hover:bg-white/[0.06] hover:text-white"
								onclick={() => copyMessage(message.content)}
								title="复制"
								aria-label="复制回答"
							>
								<svg
									class="size-4"
									viewBox="0 0 24 24"
									fill="none"
									stroke="currentColor"
									stroke-width="1.8"
									stroke-linecap="round"
									stroke-linejoin="round"
									aria-hidden="true"
								>
									<rect x="9" y="9" width="11" height="11" rx="2"></rect>
									<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
								</svg>
							</button>

							<button
								type="button"
								class="rounded-lg p-1.5 transition hover:bg-white/[0.06] hover:text-white"
								title="朗读"
								aria-label="朗读回答"
							>
								<svg
									class="size-4"
									viewBox="0 0 24 24"
									fill="none"
									stroke="currentColor"
									stroke-width="1.8"
									stroke-linecap="round"
									stroke-linejoin="round"
									aria-hidden="true"
								>
									<path d="M11 5 6 9H2v6h4l5 4z"></path>
									<path d="M15.5 8.5a5 5 0 0 1 0 7"></path>
									<path d="M19 5a10 10 0 0 1 0 14"></path>
								</svg>
							</button>

							<button
								type="button"
								class="rounded-lg p-1.5 transition hover:bg-white/[0.06] hover:text-white"
								title="赞"
								aria-label="回答有帮助"
							>
								<svg
									class="size-4"
									viewBox="0 0 24 24"
									fill="none"
									stroke="currentColor"
									stroke-width="1.8"
									stroke-linecap="round"
									stroke-linejoin="round"
									aria-hidden="true"
								>
									<path d="M7 10v12H3V10z"></path>
									<path d="M7 20h10.5a2 2 0 0 0 2-1.7l1.2-7A2 2 0 0 0 18.7 9H14l1-4a2 2 0 0 0-3.6-1.5L7 10"></path>
								</svg>
							</button>

							<button
								type="button"
								class="rounded-lg p-1.5 transition hover:bg-white/[0.06] hover:text-white"
								title="踩"
								aria-label="回答没有帮助"
							>
								<svg
									class="size-4"
									viewBox="0 0 24 24"
									fill="none"
									stroke="currentColor"
									stroke-width="1.8"
									stroke-linecap="round"
									stroke-linejoin="round"
									aria-hidden="true"
								>
									<path d="M17 14V2h4v12z"></path>
									<path d="M17 4H6.5a2 2 0 0 0-2 1.7l-1.2 7A2 2 0 0 0 5.3 15H10l-1 4a2 2 0 0 0 3.6 1.5L17 14"></path>
								</svg>
							</button>

							<button
								type="button"
								class="rounded-lg p-1.5 transition hover:bg-white/[0.06] hover:text-white"
								onclick={() => onRegenerate(message.id)}
								title="重新生成"
								aria-label="重新生成回答"
							>
								<svg
									class="size-4"
									viewBox="0 0 24 24"
									fill="none"
									stroke="currentColor"
									stroke-width="1.8"
									stroke-linecap="round"
									stroke-linejoin="round"
									aria-hidden="true"
								>
									<path d="M20 11a8 8 0 1 0-2.3 5.7"></path>
									<path d="M20 4v7h-7"></path>
								</svg>
							</button>
						</div>
					</div>
				</article>
			{/if}
		{/each}

		{#if generating}
			<article class="flex w-full">
				<div class="mr-3 mt-1 hidden shrink-0 sm:flex">
					<div
						class="flex size-8 items-center justify-center rounded-full bg-white text-[9px] font-black text-black"
					>
						OI
					</div>
				</div>

				<div class="relative w-0 flex-auto pl-1">
					<div class="mb-2 flex items-center gap-2">
						<span class="text-sm font-medium text-white">
							{modelName}
						</span>
					</div>

					<div class="flex items-center gap-1.5 py-2">
						<span class="thinking-dot size-1.5 rounded-full bg-gray-400"></span>
						<span
							class="thinking-dot size-1.5 rounded-full bg-gray-400 [animation-delay:150ms]"
						></span>
						<span
							class="thinking-dot size-1.5 rounded-full bg-gray-400 [animation-delay:300ms]"
						></span>
					</div>
				</div>
			</article>
		{/if}
	</div>
</div>

<style>
	@keyframes thinking {
		0%,
		80%,
		100% {
			opacity: 0.25;
			transform: translateY(0);
		}

		40% {
			opacity: 1;
			transform: translateY(-3px);
		}
	}

	.thinking-dot {
		animation: thinking 1.2s infinite ease-in-out;
	}
</style>