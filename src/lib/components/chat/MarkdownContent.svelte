<script lang="ts">
	import { browser } from '$app/environment';
	import DOMPurify from 'dompurify';
	import { marked } from 'marked';

	marked.use({ gfm: true, breaks: true });

	type Props = {
		content?: string;
		streaming?: boolean;
		collapseCodeBlocks?: boolean;
		fadeStreaming?: boolean;
		expandDetails?: boolean;
		detectArtifacts?: boolean;
		iframeSandboxAllowSameOrigin?: boolean;
		iframeSandboxAllowForms?: boolean;
	};

	let {
		content = '',
		streaming = false,
		collapseCodeBlocks = false,
		fadeStreaming = true,
		expandDetails = false,
		detectArtifacts = true,
		iframeSandboxAllowSameOrigin = false,
		iframeSandboxAllowForms = false
	}: Props = $props();

	let rootEl = $state<HTMLDivElement | null>(null);

	const artifactPreview = $derived.by(() => {
		if (!detectArtifacts || streaming) return null;
		const match = content.match(/```(?:html|svg|mermaid)\n([\s\S]*?)```/i);
		if (!match) return null;
		const lang = content.match(/```(html|svg|mermaid)/i)?.[1]?.toLowerCase() ?? 'html';
		return { lang, body: match[1].trim() };
	});

	const sandboxAttr = $derived(
		[
			'allow-scripts',
			iframeSandboxAllowSameOrigin ? 'allow-same-origin' : '',
			iframeSandboxAllowForms ? 'allow-forms' : ''
		]
			.filter(Boolean)
			.join(' ')
	);

	$effect(() => {
		if (!browser || !rootEl || !expandDetails) return;
		rootEl.querySelectorAll('details').forEach((el) => {
			el.open = true;
		});
	});

	const html = $derived.by(() => {
		const rendered = marked.parse(content || '', {
			async: false
		}) as string;

		if (!browser) {
			return rendered;
		}

		return DOMPurify.sanitize(rendered, {
			USE_PROFILES: { html: true }
		});
	});
</script>

<div
	bind:this={rootEl}
	class={`md-body text-sm leading-7 text-gray-200 ${collapseCodeBlocks ? 'collapse-code' : ''} ${
		streaming && fadeStreaming ? 'fade-stream' : ''
	}`}
>
	{@html html}{#if streaming}<span
			class="streaming-caret ml-0.5 inline-block h-[1em] w-[2px] translate-y-[2px] bg-gray-200"
		></span>{/if}
</div>

{#if artifactPreview}
	<div class="mt-3 overflow-hidden rounded-xl border border-white/10 bg-black/40">
		<div class="border-b border-white/10 px-3 py-1.5 text-[11px] uppercase tracking-wide text-gray-400">
			产物 · {artifactPreview.lang}
		</div>
		{#if artifactPreview.lang === 'html' || artifactPreview.lang === 'svg'}
			<iframe
				title="artifact-preview"
				class="h-56 w-full bg-white"
				sandbox={sandboxAttr}
				srcdoc={artifactPreview.body}
			></iframe>
		{:else}
			<pre class="max-h-56 overflow-auto p-3 text-xs text-gray-300">{artifactPreview.body}</pre>
		{/if}
	</div>
{/if}

<style>
	.md-body :global(> :first-child) {
		margin-top: 0;
	}

	.md-body :global(> :last-child) {
		margin-bottom: 0;
	}

	.md-body :global(h1),
	.md-body :global(h2),
	.md-body :global(h3),
	.md-body :global(h4) {
		color: #fff;
		font-weight: 600;
		line-height: 1.4;
		margin: 0.9em 0 0.35em;
	}

	.md-body :global(h1) {
		font-size: 1.2rem;
	}

	.md-body :global(h2) {
		font-size: 1.08rem;
	}

	.md-body :global(h3),
	.md-body :global(h4) {
		font-size: 1rem;
	}

	.md-body :global(p) {
		margin: 0.45em 0;
	}

	.md-body :global(ul),
	.md-body :global(ol) {
		margin: 0.4em 0;
		padding-left: 1.35rem;
	}

	.md-body :global(ul) {
		list-style: disc;
	}

	.md-body :global(ol) {
		list-style: decimal;
	}

	.md-body :global(li) {
		margin: 0.15em 0;
	}

	.md-body :global(strong) {
		color: #fff;
		font-weight: 600;
	}

	.md-body :global(a) {
		color: #7dd3fc;
		text-decoration: underline;
		text-underline-offset: 2px;
	}

	.md-body :global(blockquote) {
		border-left: 3px solid rgba(255, 255, 255, 0.16);
		color: #9ca3af;
		margin: 0.6em 0;
		padding-left: 0.85rem;
	}

	.md-body :global(code) {
		background: rgba(255, 255, 255, 0.08);
		border-radius: 0.3rem;
		font-size: 0.85em;
		padding: 0.1em 0.35em;
	}

	.md-body :global(pre) {
		background: #111;
		border: 1px solid rgba(255, 255, 255, 0.06);
		border-radius: 0.85rem;
		margin: 0.7em 0;
		overflow-x: auto;
		padding: 0.85rem 1rem;
	}

	.md-body :global(pre code) {
		background: transparent;
		padding: 0;
	}

	.md-body :global(table) {
		border-collapse: collapse;
		font-size: 0.85em;
		margin: 0.7em 0;
		width: 100%;
	}

	.md-body :global(th),
	.md-body :global(td) {
		border: 1px solid rgba(255, 255, 255, 0.1);
		padding: 0.35rem 0.55rem;
		text-align: left;
	}

	.md-body :global(th) {
		background: rgba(255, 255, 255, 0.04);
		color: #fff;
	}

	@keyframes caret-blink {
		0%,
		45% {
			opacity: 1;
		}

		55%,
		100% {
			opacity: 0;
		}
	}

	.streaming-caret {
		animation: caret-blink 1s steps(1, end) infinite;
	}

	.collapse-code :global(pre) {
		max-height: 4.5rem;
		overflow: hidden;
		position: relative;
	}

	.collapse-code :global(pre)::after {
		background: linear-gradient(transparent, #111);
		bottom: 0;
		content: '';
		height: 2rem;
		left: 0;
		position: absolute;
		right: 0;
	}

	.fade-stream {
		animation: stream-fade 0.35s ease;
	}

	@keyframes stream-fade {
		from {
			opacity: 0.55;
		}
		to {
			opacity: 1;
		}
	}
</style>
