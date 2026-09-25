<script lang="ts">
	type Props = {
		content?: string;
		placement?: string;
		className?: string;
		children?: import('svelte').Snippet;
	};

	let { content = '', className = 'flex', children }: Props = $props();
</script>

<div class={className} title={content || undefined}>
	{#if children}
		{@render children()}
	{/if}
</div>
