<script lang="ts">
	import { onDestroy, onMount, tick } from 'svelte';

	import { getAgentModels, reviewEssay } from '$lib/apis/agent';
	import AnnotatedText from '$lib/components/essay/AnnotatedText.svelte';
	import ScoreSheet from '$lib/components/essay/ScoreSheet.svelte';
	import KnowledgeCombobox from '$lib/components/quiz/KnowledgeCombobox.svelte';
	import {
		ESSAY_MAX_CHARS,
		ESSAY_MIN_CHARS,
		ESSAY_TOPIC_MAX,
		circled,
		countCharacters,
		countParagraphs,
		essayLengthGate,
		humanizeRefs,
		placeAnnotations,
		pyStrip,
		weakestDimension,
		type DimensionName,
		type PaperReview
	} from '$lib/data/essay';
	import { formatDuration } from '$lib/data/exam';
	import {
		findCollection,
		parseSourceKey,
		sourceKeysForCollection,
		type KnowledgeCollection
	} from '$lib/data/knowledge';
	import { essaySamples, type EssaySample } from '$lib/data/samples';

	type Phase = 'compose' | 'grading' | 'result' | 'failed';

	/** 真正交出去的那一份。高亮下标相对 text 计算，所以它必须和发给后端的一字不差 */
	type Submitted = { text: string; topic: string; notebookIds: string[] };

	type Props = {
		modelId?: string;
		/** 从答疑进来时带上当前笔记本，预选为对照材料 */
		initialNotebook?: string;
		onBack: () => void;
	};

	let { modelId = '', initialNotebook = '', onBack }: Props = $props();

	/** 后端 ESSAY_LLM_BUDGET=220s 已经封了顶；这条只防「再也不回话」 */
	const CLIENT_TIMEOUT_MS = 260_000;
	/**
	 * 草稿只存 sessionStorage：误刷新不丢稿，关掉标签页就清掉。
	 * 机房电脑是多人共用的，作文留在 localStorage 里等于留给下一个人看。
	 */
	const DRAFT_KEY = 'tagent:essay-draft';
	/** 稿纸行高（px）。横线、textarea 自增高都按它对齐，改这里要连 CSS 一起改 */
	const LINE = 34;
	const MIN_LINES = 14;

	let models = $state<{ id: string; name: string }[]>([]);
	let modelsLoading = $state(true);
	let modelsError = $state('');
	// 可写 $derived：跟着 props 走，模型列表回来后也能就地改
	let selectedModelId = $derived(modelId);

	let topic = $state('');
	let draft = $state('');
	// 只用来筛下拉里的笔记本，不当题目发出去——题目写在稿纸上
	let materialFilter = $state('');
	let selectedSourceKeys = $state<string[]>([]);
	let notebooks = $state<KnowledgeCollection[]>([]);

	let phase = $state<Phase>('compose');
	let submitted = $state<Submitted | null>(null);
	let review = $state<PaperReview | null>(null);
	let failure = $state('');
	let elapsed = $state(0);
	/** 结果刚到：分数、下划线、旁批依次落笔。只演这一次 */
	let justGraded = $state(false);
	let selectedDimension = $state<DimensionName | null>(null);
	let activeNote = $state<number | null>(null);

	let wideSheet = $state(false);
	let noteTops = $state<number[]>([]);
	let marginHeight = $state(0);

	let deskEl = $state<HTMLElement>();
	let textareaEl = $state<HTMLTextAreaElement>();
	let bodyEl = $state<HTMLElement>();
	let notesEl = $state<HTMLElement>();

	let controller: AbortController | null = null;
	let ticker: ReturnType<typeof setInterval> | null = null;
	let draftRestored = false;
	let notebookPreselected = false;

	// 范例正文来自 src/lib/samples/*.txt，构建时读进来；那个目录里的 .txt 不进仓库
	const samples = essaySamples();
	let sampleBody = $state('');
	let pendingSample = $state('');
	let pendingTimer: ReturnType<typeof setTimeout> | null = null;

	const characters = $derived(countCharacters(draft));
	const paragraphCount = $derived(countParagraphs(draft));
	const gate = $derived(essayLengthGate(characters));
	const canSubmit = $derived(gate.ok && Boolean(selectedModelId) && phase === 'compose');

	// 来源粒度折叠成笔记本 id —— 后端 notebook_ids 只认笔记本（与测评同一套）
	const notebookIds = $derived([
		...new Set(
			selectedSourceKeys
				.map((key) => parseSourceKey(key)?.collectionId)
				.filter((id): id is string => Boolean(id))
		)
	]);

	const placement = $derived(
		submitted ? placeAnnotations(submitted.text, review?.annotations ?? []) : null
	);

	const noteCount = $derived(placement ? placement.placed.length + placement.unplaced.length : 0);

	const materialScope = $derived.by(() => {
		const ids = submitted?.notebookIds ?? [];

		if (ids.length === 0) {
			return '全部笔记本';
		}

		return ids.map((id) => notebooks.find((item) => item.id === id)?.name ?? id).join('、');
	});

	// 后端目前把「切题与内容」的评语当总评下发，和评分栏细则里那条重复；
	// 只有总评另有内容时才在文末单独写。
	const extraComment = $derived.by(() => {
		const comment = review?.overall_comment.trim() ?? '';

		if (!comment || review?.dimensions.some((item) => item.comment.trim() === comment)) {
			return '';
		}

		return humanizeRefs(comment);
	});

	const busy = $derived(failure.includes('过多'));

	const prefersReducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

	const stopTicker = () => {
		if (ticker !== null) {
			clearInterval(ticker);
			ticker = null;
		}
	};

	const scrollDeskTop = async () => {
		await tick();
		deskEl?.scrollTo({ top: 0, behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
	};

	/** textarea 跟着内容长高、按整行取整：滚动的是整张稿纸，不是框里的一小块 */
	const fitTextarea = () => {
		if (!textareaEl) {
			return;
		}

		// 先缩成 auto 才量得到真实内容高度；这一下会让外层滚动条跳，量完还原
		const scrollTop = deskEl?.scrollTop ?? 0;
		textareaEl.style.height = 'auto';
		const lines = Math.max(MIN_LINES, Math.ceil(textareaEl.scrollHeight / LINE));
		textareaEl.style.height = `${lines * LINE}px`;

		if (deskEl) {
			deskEl.scrollTop = scrollTop;
		}
	};

	/**
	 * 宽屏时把旁批摆到对应下划线的同一高度，挨得太近就依次往下让。
	 * 位置只看 DOM 里已经画好的 <mark>（id 由 AnnotatedText 按批注编号给出），
	 * 不碰正文、不重新找句子。
	 */
	const layoutNotes = () => {
		if (!wideSheet || !notesEl || !bodyEl || phase !== 'result') {
			return;
		}

		const origin = notesEl.getBoundingClientRect().top;
		const items = Array.from(notesEl.querySelectorAll<HTMLElement>(':scope > li'));
		const tops: number[] = [];
		let floor = 0;

		for (const item of items) {
			const n = item.dataset.note;
			// 正在展开的那条盖在别的旁批上面，不该把后面的往下挤：按折叠后的三行高度排
			let height = item.offsetHeight;
			const button = item.querySelector<HTMLElement>('.note-button');

			if (button && item.classList.contains('active')) {
				const style = getComputedStyle(button);
				const folded =
					parseFloat(style.lineHeight) * 3 +
					parseFloat(style.paddingTop) +
					parseFloat(style.paddingBottom);

				height = Math.min(height, folded);
			}

			const mark = n ? bodyEl.querySelector<HTMLElement>(`#note-mark-${n}`) : null;
			// 楷体旁批的首行比正文行略矮，往上提一点让两者看起来在同一行
			const desired = mark ? mark.getBoundingClientRect().top - origin - 4 : floor;
			const top = Math.max(desired, floor);

			tops.push(top);
			floor = top + height + 14;
		}

		noteTops = tops;
		marginHeight = floor;
	};

	const startReview = () => {
		if (!submitted) {
			return;
		}

		controller?.abort();
		const own = new AbortController();
		controller = own;

		let timedOut = false;
		const ceiling = setTimeout(() => {
			timedOut = true;
			own.abort();
		}, CLIENT_TIMEOUT_MS);

		review = null;
		failure = '';
		justGraded = false;
		activeNote = null;
		selectedDimension = null;
		noteTops = [];
		phase = 'grading';

		elapsed = 0;
		stopTicker();
		ticker = setInterval(() => {
			elapsed += 1;
		}, 1000);

		void scrollDeskTop();

		const { text, topic: title, notebookIds: ids } = submitted;

		void reviewEssay(selectedModelId, text, title, ids, own.signal)
			.then((data) => {
				clearTimeout(ceiling);

				if (own.signal.aborted) {
					return;
				}

				stopTicker();
				review = data;
				// 默认展开得分率最低的那一项：学生最该先看的就是它
				selectedDimension = weakestDimension(data.dimensions)?.name ?? null;
				justGraded = true;
				phase = 'result';
				void scrollDeskTop();
			})
			.catch((error: unknown) => {
				clearTimeout(ceiling);

				if (timedOut) {
					stopTicker();
					failure = '等了 4 分钟还没批完，basic-agent 可能没在正常回话。';
					phase = 'failed';
					return;
				}

				if (own.signal.aborted) {
					return;
				}

				stopTicker();
				// 就地停下、稿子原样留着：最常见的失败是 429（并发名额满），
				// 等十几秒点重试就行，不该让学生重新贴一遍。
				failure = error instanceof Error ? error.message : '批改失败，请重试。';
				phase = 'failed';
			});
	};

	/** 载入范例。稿纸上已经有自己写的东西时要点两次，免得一下子覆盖掉 */
	const loadSample = (sample: EssaySample) => {
		const dirty = draft.trim() !== '' && draft !== sampleBody;

		if (dirty && pendingSample !== sample.id) {
			pendingSample = sample.id;

			if (pendingTimer !== null) {
				clearTimeout(pendingTimer);
			}

			pendingTimer = setTimeout(() => {
				pendingSample = '';
			}, 5000);
			return;
		}

		topic = sample.topic;
		draft = sample.body;
		sampleBody = sample.body;
		pendingSample = '';

		void tick().then(() => {
			fitTextarea();
			textareaEl?.focus({ preventScroll: true });
		});
	};

	const submit = () => {
		if (!canSubmit) {
			return;
		}

		submitted = { text: pyStrip(draft), topic: topic.trim(), notebookIds: [...notebookIds] };
		startReview();
	};

	const backToDraft = () => {
		controller?.abort();
		controller = null;
		stopTicker();
		review = null;
		failure = '';
		justGraded = false;
		activeNote = null;
		phase = 'compose';

		void tick().then(() => {
			fitTextarea();
			textareaEl?.focus({ preventScroll: true });
		});
	};

	const onDraftKeydown = (event: KeyboardEvent) => {
		if (event.key === 'Enter' && (event.metaKey || event.ctrlKey) && !event.isComposing) {
			event.preventDefault();
			submit();
		}
	};

	/** 点旁批：把对应的那句滚到眼前。窄屏时旁批在文末，这一下最有用 */
	const showMark = (n: number) => {
		const mark = document.getElementById(`note-mark-${n}`);

		if (!mark) {
			return;
		}

		activeNote = n;
		mark.scrollIntoView({ block: 'center', behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
		mark.focus({ preventScroll: true });
	};

	$effect(() => {
		const snapshot = JSON.stringify({ topic, draft });

		// 恢复草稿之前别写：否则第一次运行就会拿空稿把上次存的盖掉
		if (!draftRestored) {
			return;
		}

		try {
			sessionStorage.setItem(DRAFT_KEY, snapshot);
		} catch {
			// 存储不可用（隐私模式等）就不存，不影响批改
		}
	});

	$effect(() => {
		void draft;

		if (phase === 'compose') {
			void tick().then(fitTextarea);
		}
	});

	$effect(() => {
		if (!wideSheet || phase !== 'result' || !placement) {
			return;
		}

		void tick().then(layoutNotes);
	});

	// 从答疑带来的笔记本，等笔记本列表读回来后预选一次
	$effect(() => {
		if (notebookPreselected || !initialNotebook || notebooks.length === 0) {
			return;
		}

		notebookPreselected = true;

		if (selectedSourceKeys.length > 0) {
			return;
		}

		const collection = findCollection(initialNotebook, notebooks);

		if (collection) {
			selectedSourceKeys = sourceKeysForCollection(collection.id, notebooks);
		}
	});

	onMount(() => {
		try {
			const saved = JSON.parse(sessionStorage.getItem(DRAFT_KEY) ?? 'null') as {
				topic?: unknown;
				draft?: unknown;
			} | null;

			if (typeof saved?.draft === 'string') {
				draft = saved.draft;
			}

			if (typeof saved?.topic === 'string') {
				topic = saved.topic;
			}
		} catch {
			// 读不到就当没有草稿
		}

		draftRestored = true;

		const query = window.matchMedia('(min-width: 1024px)');
		const syncWidth = () => {
			wideSheet = query.matches;
		};
		syncWidth();
		query.addEventListener('change', syncWidth);

		// 只盯外层滚动区的尺寸（跟着视口变），不盯稿纸本身——稿纸高度随打字变化，
		// 盯它会和 fitTextarea 互相触发
		const observer = new ResizeObserver(() => {
			fitTextarea();
			layoutNotes();
		});

		if (deskEl) {
			observer.observe(deskEl);
		}

		// 宋体/楷体是系统字体，首帧可能还在用回退字体排版，换上之后行高会变
		void document.fonts?.ready.then(() => {
			fitTextarea();
			layoutNotes();
		});

		void getAgentModels()
			.then((list) => {
				models = list.data.map((model) => ({ id: model.id, name: model.name || model.id }));

				if (!models.some((model) => model.id === selectedModelId)) {
					selectedModelId = models[0]?.id ?? '';
				}

				if (models.length === 0) {
					modelsError = 'basic-agent 已连上，但还没有登记任何模型。';
				}
			})
			.catch(() => {
				models = [];
				selectedModelId = '';
				modelsError = '读不到 basic-agent 的模型列表，请确认它已经启动。';
			})
			.finally(() => {
				modelsLoading = false;
			});

		return () => {
			query.removeEventListener('change', syncWidth);
			observer.disconnect();
		};
	});

	onDestroy(() => {
		controller?.abort();
		stopTicker();

		if (pendingTimer !== null) {
			clearTimeout(pendingTimer);
		}
	});
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

{#snippet legend()}
	<p class="legend">
		<span>{@render kindSample('issue')}需修改</span>
		<span>{@render kindSample('praise')}写得好</span>
	</p>
{/snippet}

{#snippet emptyNotes()}
	<p class="margin-copy">
		这篇没有挑出需要逐句批注的句子。每一项扣在哪条要点上，点上方评分栏里的评分项名字就能看到。
	</p>
{/snippet}

{#snippet notesList(layered: boolean)}
	<ol
		bind:this={notesEl}
		class="notes"
		class:layered
		class:measuring={layered && noteTops.length !== noteCount}
		class:reveal={justGraded}
	>
		{#each placement?.placed ?? [] as note, index (note.n)}
			<li
				class="note"
				class:active={activeNote === note.n}
				data-note={note.n}
				style={`--order: ${note.n};${layered ? ` top: ${noteTops[index] ?? 0}px;` : ''}`}
			>
				<button
					type="button"
					id={`note-${note.n}`}
					class="note-button"
					onmouseenter={() => (activeNote = note.n)}
					onmouseleave={() => (activeNote = null)}
					onfocus={() => (activeNote = note.n)}
					onblur={() => (activeNote = null)}
					onclick={() => showMark(note.n)}
				>
					<span class="note-body">
						<span class="note-head" aria-hidden="true">
							{circled(note.n)}
							{@render kindSample(note.kind)}
						</span>
						<span class="sr-only">
							第 {note.n} 处，{note.kind === 'issue' ? '需修改' : '写得好'}：
						</span>
						{humanizeRefs(note.comment)}
					</span>
				</button>
			</li>
		{/each}

		{#each placement?.unplaced ?? [] as note, index (index)}
			{@const order = (placement?.placed.length ?? 0) + index}
			<li
				class="note stray"
				style={`--order: ${order + 1};${layered ? ` top: ${noteTops[order] ?? 0}px;` : ''}`}
			>
				<span class="stray-head">这条批注对不上原文位置，没有画线。原句：「{note.text}」</span>
				<span class="note-text">{humanizeRefs(note.comment)}</span>
			</li>
		{/each}
	</ol>
{/snippet}

<div class="flex h-[100dvh] flex-col bg-[#171717] text-gray-100">
	<header
		class="flex shrink-0 items-center justify-between gap-3 border-b border-white/[0.08] px-4 py-2.5"
	>
		<div class="flex min-w-0 items-baseline gap-3">
			<button
				type="button"
				class="shrink-0 text-sm text-gray-400 transition hover:text-gray-200"
				onclick={onBack}
			>
				‹ 返回
			</button>

			<h1 class="truncate text-[15px] font-semibold">论文批改</h1>
		</div>

		<select
			class="h-8 max-w-52 min-w-0 rounded-lg border border-white/[0.18] bg-[#242424] px-2 text-xs text-gray-100 outline-none focus:border-blue-400 disabled:cursor-not-allowed disabled:opacity-60"
			bind:value={selectedModelId}
			disabled={modelsLoading || phase !== 'compose' || models.length === 0}
			aria-label="批改模型"
			title={phase === 'compose' ? '选择批改模型' : '本次批改已锁定模型'}
		>
			{#each models as model (model.id)}
				<option value={model.id}>{model.name}</option>
			{/each}
		</select>
	</header>

	<div bind:this={deskEl} class="min-h-0 flex-1 overflow-y-auto">
		<div class="mx-auto w-full max-w-[64rem] px-3 pt-5 pb-10 sm:px-6">
			{#if phase === 'compose'}
				<div class="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:gap-3">
					<span class="shrink-0 text-sm text-gray-400 sm:pt-2">对照材料</span>

					<div class="min-w-0 flex-1">
						<KnowledgeCombobox
							bind:value={materialFilter}
							bind:selectedKeys={selectedSourceKeys}
							bind:collections={notebooks}
							placeholder="选笔记本或来源，不选就检索全部"
						/>

						<p class="mt-1.5 text-xs leading-relaxed text-gray-500">
							批改会按题目（没写题目就按开头几句）到这些材料里找课程内容，用来判断你有没有用上课程概念。
						</p>
					</div>
				</div>

				{#if samples.length > 0}
					<div class="mt-3 flex flex-wrap items-center gap-2">
						<span class="shrink-0 text-sm text-gray-400">范例</span>

						{#each samples as sample (sample.id)}
							<button
								type="button"
								class="rounded-lg border border-white/[0.18] px-2.5 py-1 text-xs text-gray-300 transition hover:border-white/30 hover:bg-white/[0.06]"
								onclick={() => loadSample(sample)}
								title={pendingSample === sample.id
									? '再点一次会覆盖稿纸上现在的内容'
									: `载入范例：${sample.title}`}
							>
								{pendingSample === sample.id ? '再点一次覆盖稿纸' : sample.title}
							</button>
						{/each}
					</div>
				{/if}
			{:else}
				<p class="text-sm text-gray-500">对照材料：{materialScope}</p>
			{/if}

			<article class="paper" class:wide={wideSheet} aria-label="稿纸">
				<ScoreSheet
					dimensions={review?.dimensions ?? null}
					score={review?.score ?? null}
					pending={phase === 'grading'}
					bind:selected={selectedDimension}
					animate={justGraded}
				/>

				<div class="sheet">
					<div bind:this={bodyEl} class="body">
						{#if phase === 'compose'}
							<input
								class="topic-input"
								bind:value={topic}
								maxlength={ESSAY_TOPIC_MAX}
								placeholder="在这一行写题目（选填）"
								aria-label="题目"
							/>

							<textarea
								bind:this={textareaEl}
								bind:value={draft}
								class="ruled draft"
								rows={MIN_LINES}
								spellcheck="false"
								aria-label="论文正文"
								placeholder={`把小论文正文粘贴到这里，也可以直接写。回车另起一段。\n${ESSAY_MIN_CHARS} 到 ${ESSAY_MAX_CHARS} 字，不算空格和换行。`}
								onkeydown={onDraftKeydown}></textarea>
						{:else if submitted && placement}
							{#if submitted.topic}
								<h2 class="topic">{submitted.topic}</h2>
							{/if}

							<div class="ruled">
								{#key review}
									<AnnotatedText
										paragraphs={placement.paragraphs}
										active={activeNote}
										onActivate={(n) => (activeNote = n)}
										animate={justGraded}
									/>
								{/key}
							</div>

							<div class="tally">
								{#if review}
									<p class="count">
										（全文共 {review.quick_scan.characters.toLocaleString()} 字，{review.quick_scan
											.paragraphs} 段，{review.quick_scan.sentences} 句）
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
										（全文共 {countCharacters(submitted.text).toLocaleString()} 字，{countParagraphs(
											submitted.text
										)} 段）
									</p>
								{/if}
							</div>

							{#if extraComment}
								<p class="end-comment">{extraComment}</p>
							{/if}

							{#if !wideSheet && phase === 'result'}
								<section class="inline-notes" aria-label="旁批">
									{#if noteCount > 0}
										{@render legend()}
										{@render notesList(false)}
									{:else}
										{@render emptyNotes()}
									{/if}
								</section>
							{/if}
						{/if}
					</div>

					{#if wideSheet}
						<aside class="margin" aria-label="旁批" style={`min-height: ${marginHeight}px`}>
							{#if phase === 'result'}
								{#if noteCount > 0}
									{@render legend()}
									{@render notesList(true)}
								{:else}
									{@render emptyNotes()}
								{/if}
							{:else}
								<div class="margin-copy">
									<p>这一栏留给旁批。</p>
									<p>
										交稿后会先通读全篇，再从问题最集中的几段里挑出最多 3 处要改的句子、2
										处写得好的句子，画线并在这里写明原因。
									</p>
									<p>不是每句都评。标得少，才值得逐条看完。</p>
								</div>
							{/if}
						</aside>
					{/if}
				</div>
			</article>
		</div>
	</div>

	<footer class="shrink-0 border-t border-white/[0.08] px-4 py-3">
		<div class="mx-auto flex w-full max-w-[64rem] items-center justify-between gap-4">
			{#if phase === 'compose'}
				<div class="min-w-0">
					<p class="text-sm text-gray-200">
						<span class="tabular-nums">{characters.toLocaleString()}</span> 字
						<span class="text-gray-500">，{paragraphCount} 段</span>
					</p>
					<p
						class={`mt-0.5 text-xs ${!gate.ok && gate.tooLong ? 'text-amber-300' : 'text-gray-500'}`}
					>
						{modelsError || gate.message}
					</p>
				</div>

				<button
					type="button"
					class="shrink-0 rounded-xl bg-white px-5 py-2.5 text-sm font-medium text-gray-900 transition hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-white"
					disabled={!canSubmit}
					onclick={submit}
					title="也可以在稿纸里按 ⌘/Ctrl + Enter"
				>
					开始批改
				</button>
			{:else if phase === 'grading'}
				<div class="min-w-0">
					<p class="text-sm text-gray-200">
						三个评分项同时在批，已用 <span class="tabular-nums">{formatDuration(elapsed)}</span>
					</p>
					<p class="mt-0.5 text-xs text-gray-500">分数和旁批会一起写到稿纸上。</p>
				</div>

				<button
					type="button"
					class="shrink-0 rounded-xl border border-gray-700 px-4 py-2.5 text-sm text-gray-300 transition hover:bg-gray-800"
					onclick={backToDraft}
				>
					取消
				</button>
			{:else if phase === 'result'}
				<p class="min-w-0 text-xs leading-relaxed text-gray-500">
					改完可以再交一次，每次都按同一套评分要点重新计分。
				</p>

				<button
					type="button"
					class="shrink-0 rounded-xl bg-white px-5 py-2.5 text-sm font-medium text-gray-900 transition hover:bg-gray-200"
					onclick={backToDraft}
				>
					修改后再批
				</button>
			{:else}
				<div class="min-w-0">
					<p class="text-sm text-red-300">{failure}</p>
					{#if busy}
						<p class="mt-0.5 text-xs text-gray-500">
							出卷、判卷和批改共用两个名额，等十几秒再点重试。
						</p>
					{/if}
				</div>

				<div class="flex shrink-0 gap-2">
					<button
						type="button"
						class="rounded-xl border border-gray-700 px-4 py-2.5 text-sm text-gray-300 transition hover:bg-gray-800"
						onclick={backToDraft}
					>
						返回修改
					</button>

					<button
						type="button"
						class="rounded-xl bg-white px-5 py-2.5 text-sm font-medium text-gray-900 transition hover:bg-gray-200"
						onclick={startReview}
					>
						重试
					</button>
				</div>
			{/if}
		</div>
	</footer>
</div>

<style>
	/*
		稿纸：整个页面唯一的浅色面。
		印出来的东西（评分栏、学生正文、字数）用宋体 + 墨色 + 格线绿；
		模型判出来的东西（分数、勾叉、下划线、旁批）一律朱笔 + 楷体。
		朱色只出现在纸上，不拿去当暗色界面的强调色。
	*/
	.paper {
		--paper: #f1f3ec;
		--rule: #ccd8c7;
		--rule-strong: #9fb59f;
		--rule-wash: rgba(159, 181, 159, 0.16);
		--ink: #23251f;
		--ink-soft: #5c6357;
		--vermilion: #c23a2b;
		--song:
			'Songti SC', STSong, 'Noto Serif SC', 'Noto Serif CJK SC', 'Source Han Serif SC', SimSun,
			serif;
		--kai: 'Kaiti SC', STKaiti, KaiTi, 'Noto Serif SC', serif;

		color-scheme: light;
		margin-top: 1rem;
		padding: 1.25rem 1.125rem 2rem;
		border-radius: 2px;
		background: var(--paper);
		color: var(--ink);
		box-shadow:
			0 0 0 1px rgba(255, 255, 255, 0.04),
			0 36px 60px -32px rgba(0, 0, 0, 0.75);
	}

	.paper ::selection {
		color: inherit;
		background: rgba(159, 181, 159, 0.45);
	}

	.sheet {
		margin-top: 2rem;
	}

	.paper.wide .sheet {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 16rem;
		column-gap: 2.5rem;
	}

	/* 正文一行 35 字上下：再宽就读不动了 */
	.body {
		min-width: 0;
		max-width: 38rem;
	}

	.topic-input,
	.topic {
		display: block;
		width: 100%;
		margin: 0 0 0.75rem;
		padding: 0 0 0.5rem;
		border: 0;
		background: transparent;
		color: var(--ink);
		font-family: var(--song);
		font-size: 1.375rem;
		font-weight: 700;
		line-height: 1.5;
		text-align: center;
	}

	.topic-input::placeholder {
		color: var(--ink-soft);
		font-size: 1rem;
		font-weight: 400;
	}

	.ruled {
		--indent: 2em;
		--mark-ink: var(--vermilion);
		--mark-wash: rgba(194, 58, 43, 0.12);
		--mark-offset: 7px;
		--hand: var(--kai);

		font-family: var(--song);
		font-size: 17px;
		line-height: 34px;
		letter-spacing: 0.02em;
		overflow-wrap: anywhere;
		background-image: repeating-linear-gradient(
			to bottom,
			transparent 0,
			transparent 33px,
			var(--rule) 33px,
			var(--rule) 34px
		);
		background-attachment: local;
	}

	.draft {
		display: block;
		width: 100%;
		min-height: calc(34px * 14);
		padding: 0;
		border: 0;
		resize: none;
		overflow: hidden;
		background-color: transparent;
		color: var(--ink);
		outline: none;
	}

	.draft::placeholder {
		color: var(--ink-soft);
	}

	.topic-input:focus-visible,
	.draft:focus-visible {
		outline: 1px dashed var(--rule-strong);
		outline-offset: 6px;
	}

	.tally {
		margin-top: 1rem;
		font-family: var(--song);
		font-size: 0.875rem;
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

	/* 旁批栏：一道竖格线隔开，像稿纸右边留的批注栏 */
	.margin {
		position: relative;
		padding-left: 1.25rem;
		border-left: 1px solid var(--rule-strong);
	}

	.inline-notes {
		margin-top: 1.75rem;
		padding-top: 1.25rem;
		border-top: 1px solid var(--rule-strong);
	}

	.margin-copy {
		font-family: var(--song);
		font-size: 0.8125rem;
		line-height: 1.85;
		color: var(--ink-soft);
	}

	.margin-copy p {
		margin: 0 0 0.625rem;
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

	.notes:not(.layered) .note + .note {
		margin-top: 0.75rem;
	}

	.notes.layered .note {
		position: absolute;
		left: 0;
		right: 0;
		transition: top 0.2s ease;
	}

	.notes.measuring .note {
		visibility: hidden;
	}

	/*
		宽屏旁批只露三行：模型评语常有六七十字，五条全展开就会一条压一条，
		后面几条被挤到离原句好几段远。悬停、聚焦或点中的那条展开，盖在下面几条上面。
	*/
	.notes.layered .note-body {
		display: -webkit-box;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 3;
		line-clamp: 3;
		overflow: hidden;
	}

	.notes.layered .note.active {
		z-index: 2;
	}

	.notes.layered .note.active .note-body {
		display: block;
		-webkit-line-clamp: unset;
		line-clamp: unset;
		overflow: visible;
	}

	.notes.layered .note.active .note-button {
		background: color-mix(in srgb, var(--vermilion) 7%, var(--paper));
		box-shadow: 0 14px 28px -18px rgba(35, 37, 31, 0.55);
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

	/* 旁批跟在下划线之后落笔（下划线的节奏见 AnnotatedText） */
	.reveal .note {
		animation: note-in 0.4s ease-out both;
		animation-delay: calc(var(--order) * 140ms + 520ms);
	}

	@keyframes note-in {
		from {
			opacity: 0;
			transform: translateX(6px);
		}
	}

	@media (min-width: 640px) {
		.paper {
			padding: 2.25rem 2.5rem 2.75rem;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.reveal .note {
			animation: none;
		}

		.notes.layered .note {
			transition: none;
		}
	}
</style>
