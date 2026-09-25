<script lang="ts">
	type Props = {
		open?: boolean;
		title?: string | null;
		buttonClassName?: string;
		className?: string;
		onChange?: (open: boolean) => void;
		children?: import('svelte').Snippet;
		content?: import('svelte').Snippet;
	};

	let {
		open = $bindable(false),
		title = null,
		buttonClassName = 'w-fit text-gray-500 hover:text-gray-300 transition',
		className = '',
		onChange = () => {},
		children,
		content
	}: Props = $props();

	const toggle = () => {
		open = !open;
		onChange(open);
	};
</script>

<div class={className}>
	{#if title !== null}
		<button type="button" class="{buttonClassName} cursor-pointer" onclick={toggle}>
			<div class="flex w-full items-center justify-between gap-2 py-0.5">
				<div class="text-sm">{title}</div>
				<div class="flex translate-y-[1px] self-center text-gray-500">
					{#if open}
						<svg class="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5">
							<path stroke-linecap="round" stroke-linejoin="round" d="m18 15-6-6-6 6"></path>
						</svg>
					{:else}
						<svg class="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5">
							<path stroke-linecap="round" stroke-linejoin="round" d="m6 9 6 6 6-6"></path>
						</svg>
					{/if}
				</div>
			</div>
		</button>
	{/if}

	{#if open}
		<div class="mt-1.5">
			{#if content}
				{@render content()}
			{:else if children}
				{@render children()}
			{/if}
		</div>
	{/if}
</div>
