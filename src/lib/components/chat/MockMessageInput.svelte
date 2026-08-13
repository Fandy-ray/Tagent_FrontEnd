<script lang="ts">
	type Props = {
		prompt?: string;
		placeholder?: string;
		disabled?: boolean;
		generating?: boolean;
		onSubmit?: (content: string) => void;
		onStop?: () => void;
	};

	let {
		prompt = $bindable(''),
		placeholder = '发送消息',
		disabled = false,
		generating = false,
		onSubmit = () => {},
		onStop = () => {}
	}: Props = $props();

	let textareaElement = $state<HTMLTextAreaElement | null>(null);

	const submit = () => {
		const content = prompt.trim();

		if (!content || disabled || generating) {
			return;
		}

		onSubmit(content);
	};

	const handleKeydown = (event: KeyboardEvent) => {
		if (event.key === 'Enter' && !event.shiftKey) {
			event.preventDefault();
			submit();
		}
	};

	const focus = () => {
		textareaElement?.focus();
	};

	export { focus };
</script>

<div
	id="message-input-container"
	class="relative flex w-full flex-1 flex-col rounded-3xl border border-white/[0.08] bg-white/[0.035] px-1 text-gray-100 shadow-lg shadow-black/10 backdrop-blur-sm transition hover:border-white/[0.12] focus-within:border-white/[0.16]"
>
	<div class="max-h-[18rem] min-h-[3rem] overflow-y-auto">
		<textarea
			bind:this={textareaElement}
			bind:value={prompt}
			rows="1"
			class="block min-h-[52px] w-full resize-none bg-transparent px-3 pt-3 pb-1 text-sm leading-6 text-gray-100 outline-none placeholder:text-gray-500 disabled:cursor-not-allowed disabled:opacity-50"
			{placeholder}
			{disabled}
			onkeydown={handleKeydown}
			aria-label={placeholder}
		></textarea>
	</div>

	<div class="mx-0.5 mt-0.5 mb-2.5 flex max-w-full items-end justify-between" dir="ltr">
		<div class="ml-1 flex max-w-[80%] flex-1 items-center self-end">
			<button
				type="button"
				class="flex size-8 items-center justify-center rounded-full bg-transparent text-gray-300 outline-none transition hover:bg-white/[0.07] hover:text-white"
				title="添加"
				aria-label="添加"
			>
				<svg
					class="size-[22px]"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="1.7"
					stroke-linecap="round"
					stroke-linejoin="round"
					aria-hidden="true"
				>
					<path d="M12 5v14"></path>
					<path d="M5 12h14"></path>
				</svg>
			</button>

			<button
				type="button"
				class="ml-1 flex size-8 items-center justify-center rounded-full text-gray-400 transition hover:bg-white/[0.07] hover:text-white"
				title="工具"
				aria-label="工具"
			>
				<svg
					class="size-[18px]"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="1.6"
					stroke-linecap="round"
					stroke-linejoin="round"
					aria-hidden="true"
				>
					<path d="m12 3 2.1 4.9L19 10l-4.9 2.1L12 17l-2.1-4.9L5 10l4.9-2.1z"></path>
					<path d="m19 16 .8 1.8L22 19l-2.2 1.2L19 22l-.8-1.8L16 19l2.2-1.2z"></path>
				</svg>
			</button>
		</div>

		<div class="mr-1 flex shrink-0 items-center gap-1 self-end">
			{#if generating}
				<button
					type="button"
					class="flex size-8 items-center justify-center rounded-full bg-white text-black transition hover:bg-gray-200"
					onclick={onStop}
					title="停止生成"
					aria-label="停止生成"
				>
					<span class="size-2.5 rounded-[2px] bg-black"></span>
				</button>
			{:else if prompt.trim()}
				<button
					type="button"
					class="flex size-8 items-center justify-center rounded-full bg-white text-black transition hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-30"
					onclick={submit}
					disabled={disabled}
					title="发送"
					aria-label="发送"
				>
					<svg
						class="size-[18px]"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						stroke-linecap="round"
						stroke-linejoin="round"
						aria-hidden="true"
					>
						<path d="M12 19V5"></path>
						<path d="m5 12 7-7 7 7"></path>
					</svg>
				</button>
			{:else}
				<button
					type="button"
					class="flex size-8 items-center justify-center rounded-full text-gray-300 transition hover:bg-white/[0.07] hover:text-white"
					title="语音输入"
					aria-label="语音输入"
				>
					<svg
						class="size-[18px]"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="1.8"
						stroke-linecap="round"
						stroke-linejoin="round"
						aria-hidden="true"
					>
						<rect x="9" y="2" width="6" height="12" rx="3"></rect>
						<path d="M5 10a7 7 0 0 0 14 0"></path>
						<path d="M12 17v5"></path>
					</svg>
				</button>

				<button
					type="button"
					class="flex size-8 items-center justify-center rounded-full bg-white text-black transition hover:bg-gray-200"
					title="语音模式"
					aria-label="语音模式"
				>
					<svg
						class="size-[18px]"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="1.8"
						stroke-linecap="round"
						stroke-linejoin="round"
						aria-hidden="true"
					>
						<path d="M5 9v6"></path>
						<path d="M9 6v12"></path>
						<path d="M13 4v16"></path>
						<path d="M17 7v10"></path>
						<path d="M21 10v4"></path>
					</svg>
				</button>
			{/if}
		</div>
	</div>
</div>