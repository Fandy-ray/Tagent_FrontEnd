<script lang="ts">
	type Props = {
		value?: string;
		placeholder?: string;
		className?: string;
		rows?: number;
		minSize?: number;
		maxSize?: number;
		ariaLabel?: string;
	};

	let {
		value = $bindable(''),
		placeholder = '',
		className = '',
		rows = 3,
		minSize,
		maxSize,
		ariaLabel
	}: Props = $props();

	const minHeight = minSize !== undefined ? `${minSize}px` : undefined;
	const maxHeight = maxSize !== undefined ? `${maxSize}px` : undefined;
</script>

<textarea
	{placeholder}
	{rows}
	aria-label={ariaLabel}
	class={className}
	bind:value
	style:min-height={minHeight}
	style:max-height={maxHeight}
></textarea>
