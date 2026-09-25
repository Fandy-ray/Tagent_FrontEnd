<script lang="ts">
	type Props = { className?: string };
	let { className = 'size-3.5' }: Props = $props();
</script>

<svg
	xmlns="http://www.w3.org/2000/svg"
	viewBox="0 0 20 20"
	fill="currentColor"
	class={className}
	aria-hidden="true"
>
	<path
		d="M2.695 14.763l-1.945 1.945a.75.75 0 001.06 1.06l1.945-1.945a3.75 3.75 0 005.304 0L10 17.88V20a.75.75 0 001.5 0v-2.12a.75.75 0 00-.22-.53l-3.415-3.414a.75.75 0 00-1.06 0L3.39 17.296a3.75 3.75 0 000 5.304l3.535 3.535a.75.75 0 001.06 0l3.535-3.535a3.75 3.75 0 000-5.304l-1.95-1.95a.75.75 0 00-1.06 0L8.55 13.293l-1.767-1.768a.75.75 0 00-1.06 0L2.696 14.763z"
	/>
</svg>
