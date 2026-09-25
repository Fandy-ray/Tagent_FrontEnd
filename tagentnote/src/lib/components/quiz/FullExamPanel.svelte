<script lang="ts">
	import { onDestroy, onMount } from 'svelte';

	import { annotateExamAnswer, generateExam, reviewExam } from '$lib/apis/agent';
	import MathText from '$lib/components/MathText.svelte';
	import AnnotatedText from '$lib/components/essay/AnnotatedText.svelte';
	import {
		ANNOTATE_MIN_ANSWER_CHARS,
		circled,
		countCharacters,
		humanizeRefs,
		placeAnnotations,
		pyStrip,
		type Annotation
	} from '$lib/data/essay';
	import {
		LETTERS,
		SECTION_LABELS,
		answerNavClass,
		formatDuration,
		hasAnswer,
		resultNavClass,
		verdictClass,
		verdictLabel,
		type ExamAnswers,
		type ExamReview,
		type PublicExam,
		type PublicQuestion,
		type ReviewResult
	} from '$lib/data/exam';

	type Phase = 'generating' | 'answering' | 'submitting' | 'result' | 'failed';

	/** 客户端兜底上限；后端 EXAM_LLM_BUDGET=480s 已经封了顶，这条只防"再也不回话" */
	const CLIENT_TIMEOUT_MS = 540_000;

	type Props = {
		modelId: string;
		topic: string;
		notebookIds: string[];
		wide: boolean;
		onTitle: (title: string) => void;
		onError: (message: string) => void;
		onExit: () => void;
		onSwitchToFlash: () => void;
	};

	let { modelId, topic, notebookIds, wide, onTitle, onError, onExit, onSwitchToFlash }: Props =
		$props();

	// 只是生成中屏的静态说明，题量取自 app/schema/exam.py 的 *_COUNT_RANGE
	const STAGES = [
		{ name: '填空题', count: '8~10 道' },
		{ name: '选择题', count: '6~8 道' },
		{ name: '解答题', count: '2~3 道' }
	];

	let phase = $state<Phase>('generating');
	let exam = $state<PublicExam | null>(null);
	let review = $state<ExamReview | null>(null);
	let answers = $state<ExamAnswers>({});

	let pageIndex = $state(0);
	let resultIndex = $state(0);

	// 出卷要等多久取决于接的是哪个模型（实测 DeepSeek 十秒上下，后端注释里那组
	// 几十秒的旧数据出自另一个模型），所以屏上不写预期秒数、只报真实已用时——
	// 一个不动的转圈太难熬，而写死的预期一旦不准就更难熬。
	// 服务端不分段回报，这里也就只能报总用时。
	let elapsed = $state(0);
	let ticker: ReturnType<typeof setInterval> | null = null;

	// 出卷这段等待里，用户完全可能返回首屏或改用闪卡。面板卸载了、
	// 请求还在飞，回来时 onTitle/onError 会改到已经不属于它的外层状态
	// （实测过：切到闪卡之后，标题被迟到的整卷标题覆盖）。所以每次请求都带一个
	// controller，离场即 abort，回调里再判一次 aborted。
	let controller: AbortController | null = null;
	let failure = $state('');

	type AnswerNotes =
		| { status: 'loading'; source: string }
		| { status: 'done'; source: string; items: Annotation[] }
		| { status: 'failed'; source: string; error: string };

	// 大题的逐句批注是**按需**的：判卷已经等过一轮模型，再给每道大题各发一轮等待就翻倍了；
	// 学生点开哪道才批哪道（见 basic-agent 的 /quiz/exam/annotate）。结果按题号留着，来回翻页不重复花调用。
	let answerNotes = $state<Record<string, AnswerNotes>>({});
	let activeNote = $state<number | null>(null);
	// 只是在飞的请求句柄，不参与渲染，所以用普通对象而不是响应式容器
	const noteControllers: Record<string, AbortController> = {};

	let allQuestions = $derived<PublicQuestion[]>(
		exam ? [...exam.cloze, ...exam.choice, ...exam.essay] : []
	);

	let questionById = $derived(
		new Map<string, PublicQuestion>(allQuestions.map((question) => [question.id, question]))
	);

	let currentQuestion = $derived<PublicQuestion | null>(allQuestions[pageIndex] ?? null);

	let currentResult = $derived<ReviewResult | null>(
		resultIndex > 0 ? (review?.results[resultIndex - 1] ?? null) : null
	);

	let currentResultQuestion = $derived<PublicQuestion | null>(
		currentResult ? (questionById.get(currentResult.id) ?? null) : null
	);

	let totalCount = $derived(allQuestions.length);

	let answeredCount = $derived(
		allQuestions.filter((question) => hasAnswer(question, answers)).length
	);

	let progressPct = $derived(totalCount > 0 ? Math.round((answeredCount / totalCount) * 100) : 0);

	let currentNotes = $derived<AnswerNotes | null>(
		currentResult ? (answerNotes[currentResult.id] ?? null) : null
	);

	// 批注下标相对后端 strip() 之后的作答计算，所以发出去、画高亮都用同一份 pyStrip 过的文本
	let currentSource = $derived(
		currentResult?.type === 'essay' ? pyStrip(String(answers[currentResult.id] ?? '')) : ''
	);

	// 不足 40 字后端直接回空数组，干脆不给按钮
	let canAnnotate = $derived(countCharacters(currentSource) >= ANNOTATE_MIN_ANSWER_CHARS);

	let currentPlacement = $derived(
		currentNotes?.status === 'done'
			? placeAnnotations(currentNotes.source, currentNotes.items)
			: null
	);

	const resetNotes = () => {
		for (const [questionId, pending] of Object.entries(noteControllers)) {
			pending.abort();
			delete noteControllers[questionId];
		}

		answerNotes = {};
		activeNote = null;
	};

	const requestCurrentNotes = () => {
		if (!exam || !currentResult || !canAnnotate) {
			return;
		}

		const questionId = currentResult.id;
		const source = currentSource;

		noteControllers[questionId]?.abort();
		const own = new AbortController();
		noteControllers[questionId] = own;
		answerNotes = { ...answerNotes, [questionId]: { status: 'loading', source } };

		void annotateExamAnswer(modelId, exam.exam_id, questionId, source, own.signal)
			.then((data) => {
				if (own.signal.aborted) {
					return;
				}

				answerNotes = {
					...answerNotes,
					[questionId]: { status: 'done', source, items: data.annotations }
				};
			})
			.catch((error: unknown) => {
				if (own.signal.aborted) {
					return;
				}

				answerNotes = {
					...answerNotes,
					[questionId]: {
						status: 'failed',
						source,
						error: error instanceof Error ? error.message : '批注失败，请重试。'
					}
				};
			})
			.finally(() => {
				if (noteControllers[questionId] === own) {
					delete noteControllers[questionId];
				}
			});
	};

	const stopTicker = () => {
		if (ticker !== null) {
			clearInterval(ticker);
			ticker = null;
		}
	};

	const startGenerate = () => {
		if (!modelId) {
			onError('请先选择可用模型。');
			onExit();
			return;
		}

		controller?.abort();
		const own = new AbortController();
		controller = own;
		const signal = own.signal;

		let timedOut = false;
		const ceiling = setTimeout(() => {
			timedOut = true;
			own.abort();
		}, CLIENT_TIMEOUT_MS);

		failure = '';
		exam = null;
		review = null;
		answers = {};
		pageIndex = 0;
		resultIndex = 0;
		resetNotes();
		phase = 'generating';

		elapsed = 0;
		stopTicker();
		ticker = setInterval(() => {
			elapsed += 1;
		}, 1000);

		void generateExam(modelId, topic, notebookIds, signal)
			.then((data) => {
				clearTimeout(ceiling);

				if (signal.aborted) {
					return;
				}

				stopTicker();
				exam = data;
				onTitle(data.title);
				answers = {};
				pageIndex = 0;
				resultIndex = 0;
				phase = 'answering';
			})
			.catch((error: unknown) => {
				clearTimeout(ceiling);

				if (timedOut) {
					stopTicker();
					failure = '等了 9 分钟还没出卷，basic-agent 可能没在正常回话。';
					phase = 'failed';
					return;
				}

				if (signal.aborted) {
					return;
				}

				stopTicker();
				// 就地停下，别弹回模式选择首屏：最常见的失败是 429（并发闸门满），
				// 弹回去只会让人觉得"点一下自己退回来了"，还得重走一遍选择流程。
				failure = error instanceof Error ? error.message : '出卷失败，请重试。';
				phase = 'failed';
			});
	};

	const submit = () => {
		if (!exam || phase === 'submitting') {
			return;
		}

		phase = 'submitting';

		controller?.abort();
		controller = new AbortController();
		const signal = controller.signal;

		void reviewExam(modelId, exam.exam_id, answers, signal)
			.then((data) => {
				if (signal.aborted) {
					return;
				}

				review = data;
				resultIndex = 0;
				phase = 'result';
			})
			.catch((error: unknown) => {
				if (signal.aborted) {
					return;
				}

				onError(error instanceof Error ? error.message : '判卷失败，请重试。');
				phase = 'answering';
			});
	};

	const goToQuestion = (index: number) => {
		pageIndex = Math.max(0, Math.min(index, Math.max(0, allQuestions.length - 1)));
	};

	const goToResult = (index: number) => {
		resultIndex = Math.max(0, Math.min(index, review?.results.length ?? 0));
		activeNote = null;
	};

	const onKeydown = (event: KeyboardEvent) => {
		if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') {
			return;
		}

		if (event.isComposing || event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) {
			return;
		}

		const target = event.target;

		if (
			target instanceof Element &&
			target.closest('input, textarea, select, button, [contenteditable="true"]')
		) {
			return;
		}

		const offset = event.key === 'ArrowRight' ? 1 : -1;

		if ((phase === 'answering' || phase === 'submitting') && allQuestions.length > 0) {
			event.preventDefault();
			goToQuestion(pageIndex + offset);
			return;
		}

		if (phase === 'result' && review) {
			event.preventDefault();
			goToResult(resultIndex + offset);
		}
	};

	onMount(() => {
		window.addEventListener('keydown', onKeydown);
		startGenerate();
	});

	onDestroy(() => {
		stopTicker();
		controller?.abort();
		resetNotes();

		// onDestroy 在 SSR 渲染完也会跑一次，那边没有 window。
		if (typeof window === 'undefined') {
			return;
		}

		window.removeEventListener('keydown', onKeydown);
	});
</script>

<div class="flex h-full min-h-0 flex-col">
	{#if phase === 'answering' || phase === 'submitting'}
		<div class="shrink-0 pb-2">
			<div class="h-1.5 overflow-hidden rounded-full bg-gray-800">
				<div
					class="h-full rounded-full bg-gradient-to-r from-blue-500 to-sky-400 transition-all duration-300"
					style={`width: ${progressPct}%`}
				></div>
			</div>

			<div class="mt-1 flex justify-between font-mono text-[11px] text-gray-500">
				<span>已作答 {answeredCount} / {totalCount}</span>
				<span>{progressPct}%</span>
			</div>
		</div>
	{/if}

	<div class="flex min-h-0 flex-1 flex-col">
		{#if phase === 'failed'}
			<div class="flex h-full flex-col items-center justify-center gap-4 px-6 text-center">
				<svg
					class="size-8 text-amber-400"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="1.5"
					stroke-linecap="round"
					stroke-linejoin="round"
					aria-hidden="true"
				>
					<path d="M12 9v4"></path>
					<path d="M12 17h.01"></path>
					<path
						d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"
					></path>
				</svg>

				<div class="text-sm font-medium">这一轮没能出卷</div>

				<p class="max-w-sm text-sm leading-relaxed text-gray-400">{failure}</p>

				{#if failure.includes('过多')}
					<p class="max-w-sm text-xs leading-relaxed text-gray-500">
						服务端同时只接两个出题/判分请求，等十几秒再重试就好。
					</p>
				{/if}

				<div class="mt-1 flex gap-2">
					<button
						type="button"
						class="rounded-xl bg-white px-5 py-2.5 text-sm font-medium text-gray-900 transition hover:bg-gray-200"
						onclick={startGenerate}
					>
						重试
					</button>

					<button
						type="button"
						class="rounded-xl border border-gray-700 px-5 py-2.5 text-sm text-gray-400 transition hover:bg-gray-800 hover:text-gray-200"
						onclick={onExit}
					>
						返回模式选择
					</button>
				</div>
			</div>
		{:else if phase === 'generating'}
			<div class="flex h-full flex-col items-center justify-center gap-4 px-6 text-center">
				<svg
					class="size-8 animate-spin text-blue-500"
					viewBox="0 0 24 24"
					fill="none"
					aria-hidden="true"
				>
					<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"
					></circle>

					<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8v4a4 4 0 0 0-4 4H4z"
					></path>
				</svg>

				<div class="font-mono text-3xl font-bold">{formatDuration(elapsed)}</div>

				<div class="text-sm text-gray-400">正在生成整卷</div>

				<div class="flex w-full max-w-sm flex-col gap-2.5">
					{#each STAGES as stage (stage.name)}
						<div>
							<div class="mb-1.5 flex justify-between">
								<span class="text-[13px]">
									{stage.name}
									<span class="font-mono text-gray-500">{stage.count}</span>
								</span>

								<span class="font-mono text-[11px] text-gray-500">并行进行中</span>
							</div>

							<div class="indeterminate h-1 overflow-hidden rounded-full bg-gray-800"></div>
						</div>
					{/each}
				</div>

				<p class="max-w-sm text-xs leading-relaxed text-gray-500">
					三段同时向模型发问。要等三段全部回来才能把分值归一到 100
					分，所以中途没有可以展示的分段进度 —— 这里只报总用时。
				</p>

				<div
					class="mt-1 flex w-full max-w-sm items-center justify-between gap-3 border-t border-gray-800 pt-4 text-left"
				>
					<div class="min-w-0">
						<div class="text-[13px] font-medium">等不及？</div>
						<div class="mt-0.5 text-xs text-gray-500">
							闪卡只出能本地判定的题型（填空 + 选择），答完当场就知道对错，不用再等一轮模型批改。
						</div>
					</div>

					<button
						type="button"
						class="shrink-0 rounded-xl border border-gray-700 px-4 py-2 text-[13px] whitespace-nowrap transition hover:bg-gray-800"
						onclick={onSwitchToFlash}
					>
						改用闪卡
					</button>
				</div>
			</div>
		{:else if (phase === 'answering' || phase === 'submitting') && exam && currentQuestion}
			<div class="flex min-h-0 flex-1 items-stretch gap-2">
				<button
					type="button"
					class="min-h-11 min-w-11 self-center rounded-xl border border-gray-700 text-2xl leading-none transition hover:bg-gray-800 disabled:opacity-40 disabled:hover:bg-transparent"
					disabled={pageIndex === 0}
					onclick={() => goToQuestion(pageIndex - 1)}
					aria-label="上一题"
					title="上一题"
				>
					‹
				</button>

				<div class="flex min-h-0 min-w-0 flex-1 items-center justify-center">
					{#key currentQuestion.id}
						<div
							class="relative h-full max-h-[640px] min-h-0 w-full overflow-hidden rounded-2xl border border-gray-700 bg-[#242424] shadow-sm"
						>
							<div class="absolute top-0 bottom-0 left-0 w-1 bg-blue-500"></div>

							<div
								class={`h-full min-h-0 ${
									wide ? 'grid grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]' : 'flex flex-col'
								}`}
							>
								<section
									class={`min-h-0 min-w-0 overflow-y-auto p-4 ${
										wide
											? 'border-r border-gray-800'
											: 'max-h-[46%] shrink-0 border-b border-gray-800'
									}`}
								>
									<div class="mb-4 flex items-center gap-2">
										<span
											class="rounded-lg bg-blue-950/40 px-2 py-1 text-xs font-semibold text-blue-300"
										>
											{SECTION_LABELS[currentQuestion.type]}
										</span>

										<span class="font-mono text-xs text-gray-500">
											{currentQuestion.id} · {currentQuestion.points} 分 ·
											{pageIndex + 1}/{totalCount}
										</span>
									</div>

									{#if currentQuestion.type === 'cloze'}
										<div class="mb-3 text-sm text-gray-400">
											{currentQuestion.cue}
										</div>

										<div class="text-lg leading-relaxed font-medium">
											{#each currentQuestion.text.split('____') as part, index}
												<MathText value={part} />

												{#if index < currentQuestion.text.split('____').length - 1}
													<span
														class="mx-1 inline-block min-w-20 border-b-2 border-blue-500 px-2 text-center text-blue-500"
													>
														{(answers[currentQuestion.id] as string) || ' '}
													</span>
												{/if}
											{/each}
										</div>
									{:else}
										<div class="text-lg leading-relaxed font-medium">
											<MathText value={currentQuestion.question} />
										</div>
									{/if}
								</section>

								<section
									class="flex min-h-0 min-w-0 flex-1 flex-col justify-center overflow-y-auto p-4"
								>
									{#if currentQuestion.type === 'cloze'}
										<label
											class="mb-2 text-xs font-semibold text-gray-500"
											for={`answer-${currentQuestion.id}`}
										>
											你的答案
										</label>

										<input
											id={`answer-${currentQuestion.id}`}
											class="w-full rounded-xl border border-gray-700 bg-transparent px-4 py-3 text-base outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/10 disabled:opacity-60"
											placeholder="输入你的答案"
											value={(answers[currentQuestion.id] as string) ?? ''}
											disabled={phase === 'submitting'}
											oninput={(event) => {
												answers = {
													...answers,
													[currentQuestion.id]: event.currentTarget.value
												};
											}}
										/>
									{:else if currentQuestion.type === 'choice'}
										<div class="flex flex-col gap-2">
											{#each currentQuestion.options as option, index}
												<button
													type="button"
													class={`rounded-xl border px-3.5 py-2.5 text-left text-sm transition disabled:opacity-60 ${
														answers[currentQuestion.id] === index
															? 'border-blue-500 bg-blue-950/40 text-blue-300'
															: 'border-gray-700 hover:bg-gray-800'
													}`}
													disabled={phase === 'submitting'}
													onclick={() => {
														answers = {
															...answers,
															[currentQuestion.id]:
																answers[currentQuestion.id] === index ? null : index
														};
													}}
												>
													<span class="mr-2 font-mono font-semibold text-gray-400">
														{LETTERS[index]}
													</span>

													<MathText value={option} />
												</button>
											{/each}
										</div>
									{:else}
										<label
											class="mb-2 text-xs font-semibold text-gray-500"
											for={`answer-${currentQuestion.id}`}
										>
											你的回答
										</label>

										<textarea
											id={`answer-${currentQuestion.id}`}
											class="min-h-40 w-full flex-1 resize-none rounded-xl border border-gray-700 bg-transparent px-3.5 py-3 text-sm leading-relaxed outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/10 disabled:opacity-60"
											placeholder="输入你的回答（判分时会结合课程知识库评审）"
											maxlength="5000"
											value={(answers[currentQuestion.id] as string) ?? ''}
											disabled={phase === 'submitting'}
											oninput={(event) => {
												answers = {
													...answers,
													[currentQuestion.id]: event.currentTarget.value
												};
											}}></textarea>
									{/if}
								</section>
							</div>
						</div>
					{/key}
				</div>

				<button
					type="button"
					class="min-h-11 min-w-11 self-center rounded-xl border border-gray-700 text-2xl leading-none transition hover:bg-gray-800 disabled:opacity-40 disabled:hover:bg-transparent"
					disabled={pageIndex >= totalCount - 1}
					onclick={() => goToQuestion(pageIndex + 1)}
					aria-label="下一题"
					title="下一题"
				>
					›
				</button>
			</div>

			<div class="mt-3 flex shrink-0 items-center gap-2 border-t border-gray-800 pt-3">
				<div class="min-w-0 flex-1 overflow-x-auto">
					<div class="flex min-w-max items-center gap-1.5">
						{#each allQuestions as question, index (question.id)}
							<button
								type="button"
								class={`h-8 rounded-lg border font-mono text-xs transition ${
									wide ? 'min-w-10 px-2' : 'min-w-7 px-1'
								} ${answerNavClass(question, index, pageIndex, answers)}`}
								onclick={() => goToQuestion(index)}
								aria-current={index === pageIndex ? 'page' : undefined}
								aria-label={`跳到第 ${index + 1} 题 ${question.id}`}
								title={`${question.id} · ${hasAnswer(question, answers) ? '已作答' : '未作答'}`}
							>
								{#if wide}
									{question.id}
								{:else}
									<span class="inline-block size-2 rounded-full bg-current"></span>
								{/if}
							</button>
						{/each}
					</div>
				</div>

				<button
					type="button"
					class="shrink-0 rounded-xl bg-white px-4 py-2.5 text-sm font-medium text-gray-900 transition hover:bg-gray-200 disabled:opacity-60"
					disabled={phase === 'submitting'}
					onclick={submit}
				>
					{phase === 'submitting' ? '正在判分…' : '提交试卷'}
				</button>
			</div>
		{:else if phase === 'result' && review}
			<div class="flex min-h-0 flex-1 items-stretch gap-2">
				<button
					type="button"
					class="min-h-11 min-w-11 self-center rounded-xl border border-gray-700 text-2xl leading-none transition hover:bg-gray-800 disabled:opacity-40 disabled:hover:bg-transparent"
					disabled={resultIndex === 0}
					onclick={() => goToResult(resultIndex - 1)}
					aria-label="上一页"
					title="上一页"
				>
					‹
				</button>

				<div class="flex min-h-0 min-w-0 flex-1 items-center justify-center">
					{#if resultIndex === 0}
						<div
							class="flex h-full max-h-[640px] w-full flex-col items-center justify-center overflow-y-auto rounded-2xl border border-gray-700 bg-[#242424] px-5 text-center"
						>
							<div class="mb-3 font-mono text-xs tracking-[0.2em] text-gray-500 uppercase">
								Exam completed
							</div>

							<div class="font-mono text-6xl font-bold text-blue-500">
								{review.total_score}

								<span class="text-lg text-gray-400">
									/ {review.total_points}
								</span>
							</div>

							<p class="mt-3 max-w-2xl text-sm leading-6 text-gray-400">
								{review.overall_comment}
							</p>

							<div class="mt-5 flex flex-wrap justify-center gap-2 font-mono text-xs text-gray-400">
								{#each Object.entries(review.sections) as [sectionType, section]}
									<div class="rounded-xl border border-gray-700 bg-gray-800 px-3 py-2">
										{sectionType === 'cloze'
											? '填空题'
											: sectionType === 'choice'
												? '选择题'
												: '大题'}

										<b>{section.earned}</b>/{section.max}
									</div>
								{/each}
							</div>
						</div>
					{:else if currentResult}
						<div
							class="h-full max-h-[640px] min-h-0 w-full overflow-hidden rounded-2xl border border-gray-700 bg-[#242424] shadow-sm"
						>
							<div
								class={`h-full min-h-0 ${
									wide ? 'grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)]' : 'flex flex-col'
								}`}
							>
								<section
									class={`min-h-0 min-w-0 overflow-y-auto p-4 ${
										wide
											? 'border-r border-gray-800'
											: 'max-h-[48%] shrink-0 border-b border-gray-800'
									}`}
								>
									<div class="mb-4 flex items-center justify-between gap-2">
										<span class="font-mono text-xs text-gray-500">
											{currentResult.id} ·
											{SECTION_LABELS[currentResult.type]}
										</span>

										<span class={`text-xs font-semibold ${verdictClass(currentResult.verdict)}`}>
											{verdictLabel(currentResult.verdict)} ·
											{currentResult.score}/{currentResult.points}
										</span>
									</div>

									{#if currentResultQuestion}
										{#if currentResultQuestion.type === 'cloze'}
											<div class="mb-2 text-sm text-gray-400">
												{currentResultQuestion.cue}
											</div>

											<div class="leading-relaxed font-medium">
												<MathText value={currentResultQuestion.text} />
											</div>
										{:else if currentResultQuestion.type === 'choice'}
											<div class="leading-relaxed font-medium">
												<MathText value={currentResultQuestion.question} />
											</div>

											<div class="mt-3 space-y-1 text-xs text-gray-400">
												{#each currentResultQuestion.options as option, index}
													<div>
														<span class="mr-2 font-mono">
															{LETTERS[index]}
														</span>

														<MathText value={option} />
													</div>
												{/each}
											</div>
										{:else}
											<div class="leading-relaxed font-medium">
												<MathText value={currentResultQuestion.question} />
											</div>
										{/if}
									{:else}
										<div class="font-medium">
											题目 {currentResult.id}
										</div>
									{/if}

									<div class="mt-5 rounded-xl bg-gray-800 p-3">
										<div class="mb-1 flex items-center justify-between gap-2">
											<span class="text-[11px] font-semibold text-gray-500">我的答案</span>

											{#if currentResult.type === 'essay' && canAnnotate && currentNotes?.status !== 'done'}
												<button
													type="button"
													class="rounded-lg border border-gray-700 px-2 py-0.5 text-[11px] text-gray-300 transition hover:bg-gray-700 disabled:opacity-60"
													disabled={currentNotes?.status === 'loading'}
													onclick={requestCurrentNotes}
													title="挑出这道题作答里最该改的一两句，画线并说明"
												>
													{currentNotes?.status === 'loading'
														? '正在逐句批注…'
														: currentNotes?.status === 'failed'
															? '重试逐句批注'
															: '逐句批注'}
												</button>
											{/if}
										</div>

										{#if currentPlacement && currentPlacement.placed.length > 0}
											<div class="text-sm leading-7">
												<AnnotatedText
													paragraphs={currentPlacement.paragraphs}
													active={activeNote}
													onActivate={(n) => (activeNote = n)}
												/>
											</div>

											<ol class="mt-3 space-y-1 border-t border-gray-700 pt-2.5">
												{#each currentPlacement.placed as note (note.n)}
													<li
														id={`note-${note.n}`}
														class={`rounded-lg px-2 py-1 text-xs leading-relaxed text-gray-300 transition ${
															activeNote === note.n ? 'bg-red-500/10' : ''
														}`}
													>
														<span class="mr-1 text-red-400">
															{circled(note.n)}
															{note.kind === 'issue' ? '需修改' : '写得好'}
														</span>
														{humanizeRefs(note.comment)}
													</li>
												{/each}
											</ol>
										{:else}
											<div class="text-sm leading-relaxed whitespace-pre-wrap">
												{currentResult.my_answer !== null &&
												currentResult.my_answer !== undefined &&
												currentResult.my_answer !== ''
													? currentResult.my_answer
													: '未作答'}
											</div>
										{/if}

										{#if currentNotes?.status === 'failed'}
											<p class="mt-2 text-xs text-red-400">{currentNotes.error}</p>
										{:else if currentPlacement && currentPlacement.unplaced.length > 0}
											<p class="mt-2 text-xs text-gray-500">
												有 {currentPlacement.unplaced.length} 条批注对不上作答原文的位置，没有画线。
											</p>
										{:else if currentPlacement && currentPlacement.placed.length === 0}
											<p class="mt-2 text-xs text-gray-500">
												没有挑出需要单独指出的句子，看右侧评语即可。
											</p>
										{:else if currentResult.type === 'essay' && currentSource && !canAnnotate}
											<p class="mt-2 text-[11px] text-gray-500">
												作答不足 {ANNOTATE_MIN_ANSWER_CHARS} 字，不做逐句批注。
											</p>
										{/if}
									</div>
								</section>

								<section class="min-h-0 min-w-0 flex-1 space-y-3 overflow-y-auto p-4">
									<div class="rounded-xl border border-emerald-900/60 bg-emerald-950/30 p-3">
										<div class="mb-1 text-[11px] font-semibold text-emerald-400">参考答案</div>

										<div class="text-sm leading-relaxed">
											<MathText value={currentResult.correct_answer} />
										</div>
									</div>

									{#if currentResult.feedback}
										<div class="rounded-xl bg-gray-800 p-3">
											<div class="mb-1 text-[11px] font-semibold text-gray-500">评语</div>

											<div class="text-sm leading-relaxed">
												<MathText value={currentResult.feedback} />
											</div>
										</div>
									{/if}

									{#if currentResult.explanation}
										<div class="rounded-xl border border-blue-900/60 bg-blue-950/30 p-3">
											<div class="mb-1 text-[11px] font-semibold text-blue-400">解析</div>

											<div class="text-sm leading-relaxed text-gray-300">
												<MathText value={currentResult.explanation} />
											</div>
										</div>
									{/if}
								</section>
							</div>
						</div>
					{/if}
				</div>

				<button
					type="button"
					class="min-h-11 min-w-11 self-center rounded-xl border border-gray-700 text-2xl leading-none transition hover:bg-gray-800 disabled:opacity-40 disabled:hover:bg-transparent"
					disabled={resultIndex >= review.results.length}
					onclick={() => goToResult(resultIndex + 1)}
					aria-label="下一页"
					title="下一页"
				>
					›
				</button>
			</div>

			<div class="mt-3 flex shrink-0 items-center gap-2 border-t border-gray-800 pt-3">
				<div class="min-w-0 flex-1 overflow-x-auto">
					<div class="flex min-w-max items-center gap-1.5">
						<button
							type="button"
							class={`h-8 rounded-lg border px-2.5 text-xs transition ${
								resultIndex === 0
									? 'border-blue-500 bg-blue-500 text-white'
									: 'border-gray-700 bg-gray-800 text-gray-400'
							}`}
							onclick={() => goToResult(0)}
							aria-current={resultIndex === 0 ? 'page' : undefined}
						>
							总览
						</button>

						{#each review.results as item, index (item.id)}
							<button
								type="button"
								class={`h-8 min-w-10 rounded-lg border px-2 font-mono text-xs transition ${resultNavClass(
									item
								)} ${
									resultIndex === index + 1
										? 'ring-2 ring-blue-500 ring-offset-1 ring-offset-[#242424]'
										: ''
								}`}
								onclick={() => goToResult(index + 1)}
								aria-current={resultIndex === index + 1 ? 'page' : undefined}
								title={`${item.id} · ${verdictLabel(item.verdict)}`}
							>
								{item.id}
							</button>
						{/each}
					</div>
				</div>

				<button
					type="button"
					class="shrink-0 rounded-xl bg-white px-4 py-2.5 text-sm font-medium text-gray-900 transition hover:bg-gray-200"
					onclick={onExit}
				>
					再来一套
				</button>
			</div>
		{/if}
	</div>
</div>

<style>
	/* 三段是真并行、服务端又不分段回报，所以用不定进度条：能表达"在跑"，
	   又不假装知道跑到哪了。 */
	.indeterminate {
		position: relative;
	}

	.indeterminate::after {
		content: '';
		position: absolute;
		inset: 0 auto 0 0;
		width: 38%;
		border-radius: 999px;
		background: linear-gradient(to right, #3b82f6, #38bdf8);
		animation: exam-stage-slide 1.9s ease-in-out infinite;
	}

	@keyframes exam-stage-slide {
		0% {
			transform: translateX(-105%);
		}
		100% {
			transform: translateX(275%);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.indeterminate::after {
			animation-duration: 6s;
		}
	}
</style>
