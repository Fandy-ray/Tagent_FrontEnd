<script lang="ts">
	type Props = {
		value?: string;
		placeholder?: string;
		className?: string;
	};

	let {
		value = $bindable(''),
		placeholder = '',
		className = ''
	}: Props = $props();
</script>

<textarea class={className} {placeholder} bind:value rows="3"></textarea>
