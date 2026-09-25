<script lang="ts">
	import '$lib/components/essay/paper.css';

	import AnnotatedText from '$lib/components/essay/AnnotatedText.svelte';
	import ScoreSheet from '$lib/components/essay/ScoreSheet.svelte';
	import {
		circled,
		countCharacters,
		countParagraphs,
		extraOverallComment,
		humanizeRefs,
		placeAnnotations,
		weakestDimension,
		type DimensionName,
		type PaperCard
	} from '$lib/data/essay';

	type Props = {
		/** 所在消息的 id。一段对话里可能交好几次稿，高亮与旁批的 id 靠它互不串门 */
		id: string;
		card: Extract<PaperCard, { kind: 'review' }>;
		/** 批改请求还没回来 */
		pending: boolean;
		onRetry: () => void;
	};

	let { id, card, pending, onRetry }: Props = $props();

	let sheetEl = $state<HTMLElement | null>(null);
	let activeNote = $state<number | null>(null);
	// undefined = 学生还没点过评分栏：默认展开得分最低的那一维
	let pickedDimension = $state<DimensionName | null | undefined>(undefined);
	// 只有在这张卷子上亲眼等到结果时才演落笔动画；刷新后恢复出来的卷子直接画好
	let sawPending = $state(false);

	$effect(() => {
		if (pending) {
			sawPending = true;
		}
	});

	const review = $derived(card.review);
	const justGraded = $derived(sawPending && review !== null);
	const idPrefix = $derived(`paper-${id}`);
	// 区间来自后端，这里只校验、不找位置；对不上的进 unplaced，不画线（见 $lib/data/essay）
	const placement = $derived(placeAnnotations(card.text, review?.annotations ?? []));
	const noteCount = $derived(placement.placed.length + placement.unplaced.length);
	const extraComment = $derived(review ? extraOverallComment(review) : '');
	const interrupted = $derived(!review && !card.error && !pending);
	const selectedDimension = $derived(
		pickedDimension !== undefined
			? pickedDimension
			: review
				? (weakestDimension(review.dimensions)?.name ?? null)
				: null
	);

	const prefersReducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

	// 只在这张卷子里找那一句：对话里可能不止一份批改
	const showMark = (n: number) => {
		const mark = sheetEl?.querySelector<HTMLElement>(`mark[data-note="${n}"]`);

		if (!mark) {
			return;
		}

		activeNote = n;
		mark.scrollIntoView({ block: 'center', behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
		mark.focus({ preventScroll: true });
	};
</script>

{#snippet kindSample(kind: 'issue' | 'praise')}
	<svg class="kind-sample" viewBox="0 0 20 8" aria-hidden="true">
		{#if kind === 'issue'}
			<path d="M1 5h18"></path>
		{:else}
			<path d="M1 5q2.25-3 4.5 0t4.5 0 4.5 0 4.5 0"></path>
		{/if}
	</svg>
{/snippet}

<!-- 发回来的卷子：评分栏 → 学生原文（朱笔画线）→ 字数 → 总评 → 编号旁批 -->
<article bind:this={sheetEl} class="essay-paper sheet" aria-label="小论文批改">
	<header class="head">
		<p class="paper-eyebrow">小论文批改</p>
		<h3 class="topic">{card.topic || '未设题目'}</h3>
		{#if !card.topic}
			<p class="topic-note">没有设题目：「切题与内容」按正文开头检索材料来判。</p>
		{/if}
	</header>

	<ScoreSheet
		dimensions={review?.dimensions ?? null}
		score={review?.score ?? null}
		pending={pending && !review}
		bind:selected={() => selectedDimension, (value) => (pickedDimension = value)}
		animate={justGraded}
	/>

	{#if card.error}
		<div class="paper-notice" role="alert">
			<p>{card.error}</p>
			<button type="button" class="paper-button" onclick={onRetry}>重新批改</button>
		</div>
	{:else if interrupted}
		<div class="paper-notice">
			<p>这次批改没有完成：已停止，或页面在批改时刷新了。</p>
			<button type="button" class="paper-button" onclick={onRetry}>重新批改</button>
		</div>
	{:else if pending}
		<p class="paper-status" role="status">三个维度正在同时批改，被点名的段落还会再逐句看一遍……</p>
	{/if}

	<div class="ruled">
		{#key review}
			<AnnotatedText
				paragraphs={placement.paragraphs}
				{idPrefix}
				active={activeNote}
				onActivate={(n) => (activeNote = n)}
				animate={justGraded}
			/>
		{/key}
	</div>

	<div class="tally">
		{#if review}
			<p class="count">
				（全文共 {review.quick_scan.characters.toLocaleString()} 字，{review.quick_scan.paragraphs} 段，{review
					.quick_scan.sentences} 句）
			</p>

			{#if review.quick_scan.duplicate_sentence_ids.length > 0}
				<p>有 {review.quick_scan.duplicate_sentence_ids.length} 句和前文重复。</p>
			{/if}

			{#if !review.quick_scan.cites_material}
				<p>
					没找到引用标记（如《书名》、[1]、（见……））。用到课程材料时注明出处，批改更容易认出你用了课程内容。
				</p>
			{/if}
		{:else}
			<!-- 字数和段数本地就能算，交稿当下就给，不必等模型 -->
			<p class="count">
				（全文共 {countCharacters(card.text).toLocaleString()} 字，{countParagraphs(card.text)} 段）
			</p>
		{/if}
	</div>

	{#if extraComment}
		<p class="end-comment">{extraComment}</p>
	{/if}

	{#if review}
		<section class="notes-block" aria-label="旁批">
			{#if noteCount > 0}
				<p class="legend">
					<span>{@render kindSample('issue')}需修改</span>
					<span>{@render kindSample('praise')}写得好</span>
				</p>

				<ol class="notes" class:reveal={justGraded}>
					{#each placement.placed as note (note.n)}
						<li class="note" class:active={activeNote === note.n} style={`--order: ${note.n}`}>
							<button
								type="button"
								id={`${idPrefix}-${note.n}`}
								class="note-button"
								onmouseenter={() => (activeNote = note.n)}
								onmouseleave={() => (activeNote = null)}
								onfocus={() => (activeNote = note.n)}
								onblur={() => (activeNote = null)}
								onclick={() => showMark(note.n)}
							>
								<span class="note-head" aria-hidden="true">
									{circled(note.n)}
									{@render kindSample(note.kind)}
								</span>
								<span class="sr-only">
									第 {note.n} 处，{note.kind === 'issue' ? '需修改' : '写得好'}：
								</span>
								{humanizeRefs(note.comment)}
							</button>
						</li>
					{/each}

					{#each placement.unplaced as note, index (index)}
						<li class="note stray" style={`--order: ${placement.placed.length + index + 1}`}>
							<span class="stray-head">这条批注对不上原文位置，没有画线。原句：「{note.text}」</span
							>
							<span class="note-text">{humanizeRefs(note.comment)}</span>
						</li>
					{/each}
				</ol>
			{:else}
				<p class="no-notes">通读后没有挑出需要单独指出的句子，看上面评分栏里的评语即可。</p>
			{/if}
		</section>
	{/if}
</article>

<style>
	.sheet {
		max-width: 44rem;
		padding: 1.25rem 1.125rem 1.5rem;
	}

	.head {
		margin-bottom: 1rem;
		text-align: center;
	}

	.topic {
		margin: 0.5rem 0 0;
		font-family: var(--song);
		font-size: 1.25rem;
		font-weight: 700;
		line-height: 1.5;
		color: var(--ink);
	}

	.topic-note {
		margin: 0.25rem 0 0;
		font-family: var(--song);
		font-size: 0.75rem;
		color: var(--ink-soft);
	}

	/* 对话列比原来的稿纸窄，字号行距各收一档；格线与行高必须同步改 */
	.ruled {
		--indent: 2em;
		--mark-ink: var(--vermilion);
		--mark-wash: rgba(194, 58, 43, 0.12);
		--mark-offset: 6px;
		--hand: var(--kai);

		margin-top: 1.5rem;
		font-family: var(--song);
		font-size: 16px;
		line-height: 32px;
		letter-spacing: 0.02em;
		overflow-wrap: anywhere;
		background-image: repeating-linear-gradient(
			to bottom,
			transparent 0,
			transparent 31px,
			var(--rule) 31px,
			var(--rule) 32px
		);
	}

	.tally {
		margin-top: 1rem;
		font-family: var(--song);
		font-size: 0.8125rem;
		line-height: 1.85;
		color: var(--ink-soft);
	}

	.tally p {
		margin: 0;
	}

	.tally .count {
		text-align: right;
	}

	.end-comment {
		margin: 1.25rem 0 0;
		font-family: var(--kai);
		font-size: 1.0625rem;
		line-height: 1.8;
		color: var(--vermilion);
	}

	.notes-block {
		margin-top: 1.5rem;
		padding-top: 1.125rem;
		border-top: 1px solid var(--rule-strong);
	}

	.legend {
		display: flex;
		gap: 1rem;
		margin: 0 0 0.75rem;
		font-family: var(--song);
		font-size: 0.75rem;
		color: var(--ink-soft);
	}

	.legend span {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
	}

	.kind-sample {
		width: 1.25rem;
		height: 0.5rem;
		fill: none;
		stroke: var(--vermilion);
		stroke-width: 1.6;
		stroke-linecap: round;
	}

	.notes {
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.note + .note {
		margin-top: 0.5rem;
	}

	.note-button {
		display: block;
		width: calc(100% + 0.75rem);
		margin-left: -0.5rem;
		padding: 0.25rem 0.5rem 0.375rem;
		border-radius: 2px;
		background: transparent;
		color: var(--vermilion);
		font-family: var(--kai);
		font-size: 0.9375rem;
		line-height: 1.7;
		text-align: left;
		transition: background-color 0.15s ease;
	}

	.note-button:hover,
	.note.active .note-button {
		background: rgba(194, 58, 43, 0.07);
	}

	.note-button:focus-visible {
		outline: 2px solid var(--vermilion);
		outline-offset: 1px;
	}

	.note-head {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		margin-right: 0.375rem;
		font-size: 1rem;
		vertical-align: -0.05em;
	}

	.stray {
		font-family: var(--song);
		font-size: 0.8125rem;
		line-height: 1.7;
		color: var(--ink-soft);
	}

	.stray .note-text {
		display: block;
		font-family: var(--kai);
		font-size: 0.9375rem;
		color: var(--vermilion);
	}

	.no-notes {
		margin: 0;
		font-family: var(--song);
		font-size: 0.8125rem;
		color: var(--ink-soft);
	}

	/* 旁批跟在下划线之后落笔（下划线的节奏见 AnnotatedText） */
	.reveal .note {
		animation: note-in 0.4s ease-out both;
		animation-delay: calc(var(--order) * 140ms + 520ms);
	}

	@keyframes note-in {
		from {
			opacity: 0;
			transform: translateY(4px);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.reveal .note {
			animation: none;
		}
	}
</style>
