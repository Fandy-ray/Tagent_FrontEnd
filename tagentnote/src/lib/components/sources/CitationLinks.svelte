<script lang="ts">
	import { KIND_LABEL, type Citation } from '$lib/data/knowledge';

	type Props = {
		citations?: Citation[];
		label?: string;
	};

	let { citations = [], label = '引用' }: Props = $props();
</script>

{#if citations.length > 0}
	<div class="mt-3 space-y-1.5">
		<div class="text-[11px] font-medium tracking-wide text-gray-500">
			{label}
		</div>
		<div class="flex flex-col gap-1">
			{#each citations as citation (citation.id)}
				<!-- eslint-disable svelte/no-navigation-without-resolve -- href 由 $lib/data/knowledge 的 sourceHref() 生成，那边已经 resolve 过 -->
				<a
					href={citation.href}
					class="group inline-flex max-w-full items-center gap-2 rounded-lg px-1 py-0.5 text-sm text-sky-300 transition hover:bg-white/[0.04] hover:text-sky-200"
				>
					<span class="shrink-0 text-[10px] text-gray-500">
						{KIND_LABEL[citation.kind]}
					</span>
					<span class="min-w-0 truncate underline decoration-sky-500/40 underline-offset-2">
						{citation.collectionName} · {citation.title}
					</span>
				</a>
				<!-- eslint-enable svelte/no-navigation-without-resolve -->
			{/each}
		</div>
	</div>
{/if}
