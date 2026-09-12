<script lang="ts">
	type Props = {
		content?: string;
		type?: 'success' | 'muted' | 'info';
	};
	let { content = '', type = 'success' }: Props = $props();

	const cls =
		type === 'success'
			? 'bg-emerald-500/15 text-emerald-300'
			: type === 'info'
				? 'bg-sky-500/15 text-sky-300'
				: 'bg-white/10 text-gray-400';
</script>

<span class="inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium {cls}">{content}</span>
