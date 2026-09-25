<script lang="ts">
	type Props = {
		value?: string;
		placeholder?: string;
		className?: string;
		rows?: number;
	};

	let {
		value = $bindable(''),
		placeholder = '',
		className = '',
		rows = 3
	}: Props = $props();
</script>

<textarea class={className} {placeholder} {rows} bind:value></textarea>
