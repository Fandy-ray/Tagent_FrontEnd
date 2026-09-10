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
			{/if}
		</div>
	</div>
</div>