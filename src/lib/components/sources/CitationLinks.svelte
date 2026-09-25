<script lang="ts">
	import { KIND_LABEL, type Citation } from '$lib/data/knowledge';

	type Props = {
		citations?: Citation[];
		label?: string;
	};

	let { citations = [], label = '引用' }: Props = $props();

	const displayTitle = (citation: Citation) => {
		const title = citation.title.trim();
		const notebook = citation.collectionName.trim();
		const same = title && notebook && title === notebook;
		const head = same ? notebook : [notebook, title].filter(Boolean).join(' · ');
		return citation.locator ? `${head} · ${citation.locator}` : head;
	};
</script>

{#if citations.length > 0}
	<div class="mt-3 space-y-1.5">
		<div class="text-[11px] font-medium tracking-wide text-gray-500">
			{label}
		</div>
		<div class="flex flex-col gap-1">
			{#each citations as citation (citation.id)}
				<a
					href={citation.href}
					class="group inline-flex max-w-full items-center gap-2 rounded-lg px-1 py-0.5 text-sm text-sky-300 transition hover:bg-white/[0.04] hover:text-sky-200"
				>
					<span class="shrink-0 text-[10px] text-gray-500">
						{KIND_LABEL[citation.kind]}
					</span>
					<span class="min-w-0 truncate underline decoration-sky-500/40 underline-offset-2">
						{displayTitle(citation)}
					</span>
				</a>
			{/each}
		</div>
	</div>
{/if}
