<script lang="ts">
	type Props = { className?: string };
	let { className = 'size-4' }: Props = $props();
</script>

<svg class="animate-spin text-gray-400 {className}" viewBox="0 0 24 24" fill="none" aria-hidden="true">
	<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3"></circle>
	<path
		class="opacity-90"
		fill="currentColor"
		d="M4 12a8 8 0 018-8v3a5 5 0 00-5 5H4z"
	></path>
</svg>
