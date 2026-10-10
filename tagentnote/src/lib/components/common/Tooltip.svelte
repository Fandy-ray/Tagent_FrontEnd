<script lang="ts">
	type Props = {
		content?: string;
		placement?: string;
		className?: string;
		children?: import('svelte').Snippet;
	};

	let { content = '', placement = 'top', className = 'flex', children }: Props = $props();
</script>

<div class={className} data-placement={placement} title={content || undefined}>
	{#if children}
		{@render children()}
	{/if}
</div>
