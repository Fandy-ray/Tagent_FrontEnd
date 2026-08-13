<script lang="ts">
	import { onDestroy, onMount } from 'svelte';

	type Phase = 'idle' | 'generating' | 'answering' | 'submitting' | 'result';
	type QuestionType = 'cloze' | 'choice' | 'essay';
	type Verdict = 'correct' | 'partial' | 'wrong' | 'unanswered';
	type ExamAnswer = string | number | null;
	type ExamAnswers = Record<string, ExamAnswer>;

	type AgentModel = {
		id: string;
		name: string;
		tags?: Array<{
			name: string;
		}>;
	};

	type ClozeQuestion = {
		id: string;
		type: 'cloze';
		points: number;
		cue: string;
		text: string;
		answer: string;
		explanation: string;
	};

	type ChoiceQuestion = {
		id: string;
		type: 'choice';
		points: number;
		question: string;
		options: string[];
		answer: number;
		explanation: string;
	};

	type EssayQuestion = {
		id: string;
		type: 'essay';
		points: number;
		question: string;
		answer: string;
		keywords: string[];
		explanation: string;
	};

	type PublicQuestion = ClozeQuestion | ChoiceQuestion | EssayQuestion;

	type PublicExam = {
		exam_id: string;
		title: string;
		cloze: ClozeQuestion[];
		choice: ChoiceQuestion[];
		essay: EssayQuestion[];
	};

	type ReviewResult = {
		id: string;
		type: QuestionType;
		score: number;
		points: number;
		verdict: Verdict;
		my_answer: string | number | null;
		correct_answer: string;
		feedback: string;
		explanation: string;
	};

	type ExamSectionReview = {
		earned: number;
		max: number;
	};

	type ExamReview = {
		total_score: number;
		total_points: number;
		overall_comment: string;
		sections: Record<QuestionType, ExamSectionReview>;
		results: ReviewResult[];
	};

	type Props = {
	fullPage?: boolean;
	onClose?: (() => void) | null;
	modelId?: string;
};

	let {
	fullPage = false,
	onClose = null,
	modelId = 'deepseek'
}: Props = $props();

	const LETTERS = ['A', 'B', 'C', 'D'];

	const SECTION_LABELS: Record<QuestionType, string> = {
		cloze: '填空题',
		choice: '选择题',
		essay: '大题'
	};

	const availableModels: AgentModel[] = [
		{
			id: 'deepseek',
			name: 'deepseek',
			tags: []
		}
	];

	let phase = $state<Phase>('idle');
	let exam = $state<PublicExam | null>(null);
	let review = $state<ExamReview | null>(null);
	let answers = $state<ExamAnswers>({});

	let pageIndex = $state(0);
	let resultIndex = $state(0);
	let topic = $state('');
	let errorMsg = $state('');

	let selectedModelId = $state(modelId);
	let modelsLoading = $state(false);

	let panelWidth = $state(0);
	let isFullscreen = $state(false);
	let rootEl = $state<HTMLElement>();

	let resizeObserver: ResizeObserver | null = null;
	let generateTimer: number | null = null;
	let submitTimer: number | null = null;

	let allQuestions = $derived<PublicQuestion[]>(
		exam ? [...exam.cloze, ...exam.choice, ...exam.essay] : []
	);

	let questionById = $derived(
		new Map<string, PublicQuestion>(
			allQuestions.map((question) => [question.id, question])
		)
	);

	let currentQuestion = $derived<PublicQuestion | null>(
		allQuestions[pageIndex] ?? null
	);

	let currentResult = $derived<ReviewResult | null>(
		resultIndex > 0 ? (review?.results[resultIndex - 1] ?? null) : null
	);

	let currentResultQuestion = $derived<PublicQuestion | null>(
		currentResult ? (questionById.get(currentResult.id) ?? null) : null
	);

	let wide = $derived(panelWidth >= 760);
	let totalCount = $derived(allQuestions.length);

	const hasAnswer = (
		question: PublicQuestion,
		answerMap: ExamAnswers
	) => {
		const answer = answerMap[question.id];

		if (question.type === 'choice') {
			return typeof answer === 'number';
		}

		return typeof answer === 'string' && answer.trim() !== '';
	};

	let answeredCount = $derived(
		allQuestions.filter((question) => hasAnswer(question, answers)).length
	);

	let progressPct = $derived(
		totalCount > 0
			? Math.round((answeredCount / totalCount) * 100)
			: 0
	);

	const createMockExam = (selectedTopic: string): PublicExam => {
		const examTopic = selectedTopic.trim() || '系统建模与仿真';

		return {
			exam_id: `mock-exam-${Date.now()}`,
			title: `${examTopic}知识测评`,
			cloze: [
				{
					id: 'F1',
					type: 'cloze',
					points: 10,
					cue: '请填写下列句子中的空缺内容。',
					text: '系统状态只在一系列离散时刻发生变化的仿真方法称为____仿真。',
					answer: '离散事件',
					explanation:
						'离散事件仿真中，系统状态不是连续变化，而是在事件发生时产生跳跃式变化。'
				},
				{
					id: 'F2',
					type: 'cloze',
					points: 10,
					cue: '请填写下列句子中的空缺内容。',
					text: '事件调度法通常使用____保存未来将要发生的事件。',
					answer: '未来事件表',
					explanation:
						'未来事件表按照事件发生时间保存和排列待处理事件，是事件调度法的核心数据结构。'
				}
			],
			choice: [
				{
					id: 'C1',
					type: 'choice',
					points: 10,
					question: '下列哪一项最符合离散事件系统的特点？',
					options: [
						'系统状态随时间连续变化',
						'系统状态只在事件发生时变化',
						'系统不存在时间变量',
						'系统只能使用微分方程描述'
					],
					answer: 1,
					explanation:
						'离散事件系统的核心特征是系统状态只在离散事件发生时改变。'
				},
				{
					id: 'C2',
					type: 'choice',
					points: 10,
					question: '事件调度法中，仿真时钟通常如何推进？',
					options: [
						'每次固定增加一个时间单位',
						'随机选择一个时间点',
						'推进到未来事件表中最早事件的发生时间',
						'始终保持不变'
					],
					answer: 2,
					explanation:
						'事件调度法从未来事件表中选择最早发生的事件，并将仿真时钟推进到该时刻。'
				}
			],
			essay: [
				{
					id: 'E1',
					type: 'essay',
					points: 30,
					question: '请简述事件调度法进行离散事件仿真的基本步骤。',
					answer:
						'初始化系统状态和仿真时钟，建立未来事件表；选择发生时间最早的事件；将仿真时钟推进到该事件发生时刻；执行事件并更新系统状态；生成新的未来事件；判断是否满足仿真终止条件。',
					keywords: [
						'初始化',
						'未来事件表',
						'仿真时钟',
						'事件',
						'系统状态',
						'终止'
					],
					explanation:
						'事件调度法的核心是使用未来事件表管理事件，并根据最早事件的发生时间推进仿真时钟。'
				},
				{
					id: 'E2',
					type: 'essay',
					points: 30,
					question: '请说明连续系统仿真和离散事件仿真的主要区别。',
					answer:
						'连续系统的状态随时间连续变化，通常使用微分方程描述，并通过数值积分方法求解；离散事件系统的状态只在事件发生时改变，通常使用事件、状态变量、仿真时钟和未来事件表进行描述。',
					keywords: [
						'连续变化',
						'微分方程',
						'数值积分',
						'离散事件',
						'事件发生',
						'未来事件表'
					],
					explanation:
						'二者最主要的区别是系统状态的变化方式，以及推进仿真时间所采用的方法不同。'
				}
			]
		};
	};

	const clearTimers = () => {
		if (generateTimer !== null) {
			window.clearTimeout(generateTimer);
			generateTimer = null;
		}

		if (submitTimer !== null) {
			window.clearTimeout(submitTimer);
			submitTimer = null;
		}
	};

	const startGenerate = () => {
		if (phase === 'generating') {
			return;
		}

		if (!selectedModelId) {
			errorMsg = '请先选择可用模型。';
			return;
		}

		clearTimers();

		errorMsg = '';
		exam = null;
		review = null;
		answers = {};
		pageIndex = 0;
		resultIndex = 0;
		phase = 'generating';

		generateTimer = window.setTimeout(() => {
			exam = createMockExam(topic);
			answers = {};
			pageIndex = 0;
			resultIndex = 0;
			phase = 'answering';
			generateTimer = null;
		}, 1200);
	};

	const normalizeText = (value: unknown) =>
		String(value ?? '')
			.trim()
			.toLowerCase()
			.replace(/\s+/g, '');

	const reviewClozeQuestion = (
		question: ClozeQuestion,
		answer: ExamAnswer
	): ReviewResult => {
		const userAnswer = typeof answer === 'string' ? answer.trim() : '';

		const correct =
			normalizeText(userAnswer) === normalizeText(question.answer);

		return {
			id: question.id,
			type: question.type,
			score: correct ? question.points : 0,
			points: question.points,
			verdict: !userAnswer
				? 'unanswered'
				: correct
					? 'correct'
					: 'wrong',
			my_answer: userAnswer,
			correct_answer: question.answer,
			feedback: !userAnswer
				? '本题未作答。'
				: correct
					? '回答正确，你已经掌握了该知识点。'
					: '回答与参考答案不一致，请结合解析复习该知识点。',
			explanation: question.explanation
		};
	};

	const reviewChoiceQuestion = (
		question: ChoiceQuestion,
		answer: ExamAnswer
	): ReviewResult => {
		const selectedAnswer = typeof answer === 'number' ? answer : null;
		const correct = selectedAnswer === question.answer;

		return {
			id: question.id,
			type: question.type,
			score: correct ? question.points : 0,
			points: question.points,
			verdict:
				selectedAnswer === null
					? 'unanswered'
					: correct
						? 'correct'
						: 'wrong',
			my_answer:
				selectedAnswer === null
					? null
					: `${LETTERS[selectedAnswer]}．${question.options[selectedAnswer]}`,
			correct_answer:
				`${LETTERS[question.answer]}．${question.options[question.answer]}`,
			feedback:
				selectedAnswer === null
					? '本题未作答。'
					: correct
						? '选择正确。'
						: '选择错误，请查看参考答案和解析。',
			explanation: question.explanation
		};
	};

	const reviewEssayQuestion = (
		question: EssayQuestion,
		answer: ExamAnswer
	): ReviewResult => {
		const userAnswer = typeof answer === 'string' ? answer.trim() : '';

		if (!userAnswer) {
			return {
				id: question.id,
				type: question.type,
				score: 0,
				points: question.points,
				verdict: 'unanswered',
				my_answer: '',
				correct_answer: question.answer,
				feedback: '本题未作答。',
				explanation: question.explanation
			};
		}

		const matchedKeywords = question.keywords.filter((keyword) =>
			userAnswer.includes(keyword)
		).length;

		const matchRatio = matchedKeywords / question.keywords.length;

		let score: number;
		let verdict: Verdict;
		let feedback: string;

		if (matchRatio >= 0.7) {
			score = question.points;
			verdict = 'correct';
			feedback = '回答完整，涵盖了本题的主要知识点。';
		} else if (matchRatio >= 0.3 || userAnswer.length >= 40) {
			score = Math.round(question.points * 0.6);
			verdict = 'partial';
			feedback = '回答包含部分关键内容，可以结合参考答案进一步完善。';
		} else {
			score = Math.round(question.points * 0.25);
			verdict = 'wrong';
			feedback = '回答涉及的关键知识点较少，请结合参考答案重新梳理。';
		}

		return {
			id: question.id,
			type: question.type,
			score,
			points: question.points,
			verdict,
			my_answer: userAnswer,
			correct_answer: question.answer,
			feedback,
			explanation: question.explanation
		};
	};

	const reviewQuestion = (
		question: PublicQuestion,
		answer: ExamAnswer
	): ReviewResult => {
		if (question.type === 'cloze') {
			return reviewClozeQuestion(question, answer);
		}

		if (question.type === 'choice') {
			return reviewChoiceQuestion(question, answer);
		}

		return reviewEssayQuestion(question, answer);
	};

	const createMockReview = (): ExamReview => {
		const results = allQuestions.map((question) =>
			reviewQuestion(question, answers[question.id])
		);

		const sections: Record<QuestionType, ExamSectionReview> = {
			cloze: {
				earned: 0,
				max: 0
			},
			choice: {
				earned: 0,
				max: 0
			},
			essay: {
				earned: 0,
				max: 0
			}
		};

		for (const result of results) {
			sections[result.type].earned += result.score;
			sections[result.type].max += result.points;
		}

		const totalScore = results.reduce(
			(sum, result) => sum + result.score,
			0
		);

		const totalPoints = results.reduce(
			(sum, result) => sum + result.points,
			0
		);

		const scoreRatio =
			totalPoints > 0 ? totalScore / totalPoints : 0;

		let overallComment: string;

		if (scoreRatio >= 0.85) {
			overallComment =
				'本次测评完成得很好，你已经较好地掌握了相关知识点。';
		} else if (scoreRatio >= 0.6) {
			overallComment =
				'你已经掌握了大部分基础内容，建议重点复习部分失分知识点。';
		} else {
			overallComment =
				'本次测评仍有较大提升空间，建议结合逐题解析重新复习课程内容。';
		}

		return {
			total_score: totalScore,
			total_points: totalPoints,
			overall_comment: overallComment,
			sections,
			results
		};
	};

	const submit = () => {
		if (!exam || phase === 'submitting') {
			return;
		}

		clearTimers();

		errorMsg = '';
		phase = 'submitting';

		submitTimer = window.setTimeout(() => {
			review = createMockReview();
			resultIndex = 0;
			phase = 'result';
			submitTimer = null;
		}, 900);
	};

	const restart = () => {
		clearTimers();

		exam = null;
		review = null;
		answers = {};
		pageIndex = 0;
		resultIndex = 0;
		topic = '';
		errorMsg = '';
		phase = 'idle';
	};

	const goToQuestion = (index: number) => {
		pageIndex = Math.max(
			0,
			Math.min(index, Math.max(0, allQuestions.length - 1))
		);
	};

	const goToResult = (index: number) => {
		resultIndex = Math.max(
			0,
			Math.min(index, review?.results.length ?? 0)
		);
	};

	const answerNavClass = (
		question: PublicQuestion,
		index: number,
		currentIndex: number,
		answerMap: ExamAnswers
	) =>
		index === currentIndex
			? 'bg-blue-500 text-white border-blue-500'
			: hasAnswer(question, answerMap)
				? 'bg-emerald-950/40 text-emerald-300 border-emerald-900'
				: 'bg-gray-800 text-gray-400 border-gray-700';

	const resultNavClass = (item: ReviewResult) => {
		if (item.verdict === 'correct') {
			return 'bg-emerald-950/40 text-emerald-300 border-emerald-900';
		}

		if (item.verdict === 'partial') {
			return 'bg-amber-950/40 text-amber-300 border-amber-900';
		}

		if (item.verdict === 'unanswered') {
			return 'bg-gray-800 text-gray-400 border-gray-700';
		}

		return 'bg-red-950/40 text-red-300 border-red-900';
	};

	const verdictClass = (verdict: Verdict) => {
		if (verdict === 'correct') {
			return 'text-emerald-400';
		}

		if (verdict === 'partial') {
			return 'text-amber-400';
		}

		if (verdict === 'unanswered') {
			return 'text-gray-500';
		}

		return 'text-red-400';
	};

	const verdictLabel = (verdict: Verdict) => {
		const labels: Record<Verdict, string> = {
			correct: '✓ 正确',
			partial: '◐ 部分得分',
			wrong: '✗ 错误',
			unanswered: '未作答'
		};

		return labels[verdict];
	};

	const onFullscreenChange = () => {
		isFullscreen = document.fullscreenElement === rootEl;
	};

	const toggleFullscreen = async () => {
		if (!rootEl) {
			return;
		}

		if (document.fullscreenElement === rootEl) {
			await document.exitFullscreen().catch(() => {});
			return;
		}

		await rootEl.requestFullscreen().catch(() => {});
	};

	const onKeydown = (event: KeyboardEvent) => {
		if (
			event.key !== 'ArrowLeft' &&
			event.key !== 'ArrowRight'
		) {
			return;
		}

		if (
			event.isComposing ||
			event.ctrlKey ||
			event.altKey ||
			event.metaKey ||
			event.shiftKey
		) {
			return;
		}

		const target = event.target;

		if (
			target instanceof Element &&
			target.closest(
				'input, textarea, select, button, [contenteditable="true"]'
			)
		) {
			return;
		}

		const offset = event.key === 'ArrowRight' ? 1 : -1;

		if (
			(phase === 'answering' || phase === 'submitting') &&
			allQuestions.length > 0
		) {
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
		document.addEventListener(
			'fullscreenchange',
			onFullscreenChange
		);

		window.addEventListener('keydown', onKeydown);

		if (rootEl) {
			resizeObserver = new ResizeObserver(([entry]) => {
				panelWidth = Math.round(entry.contentRect.width);
			});

			resizeObserver.observe(rootEl);

			panelWidth = Math.round(
				rootEl.getBoundingClientRect().width
			);
		}
	});

	onDestroy(() => {
		clearTimers();
		resizeObserver?.disconnect();

		document.removeEventListener(
			'fullscreenchange',
			onFullscreenChange
		);

		window.removeEventListener('keydown', onKeydown);

		if (document.fullscreenElement === rootEl) {
			document.exitFullscreen().catch(() => {});
		}
	});
</script>

<div
	bind:this={rootEl}
	class="flex h-full min-h-0 flex-col bg-[#242424] text-gray-100"
>
	<div
		class="flex shrink-0 items-center justify-between border-b border-white/[0.08] px-3.5 pt-3 pb-2"
	>
		<div class="flex min-w-0 items-baseline gap-2">
			<div class="truncate font-semibold">
				{exam?.title ?? '智能测评'}
			</div>

			<div class="whitespace-nowrap text-xs text-gray-500">
				AI 智能试卷
			</div>
		</div>

		<div class="flex min-w-0 items-center gap-1.5">
			<select
				class="h-8 min-w-0 max-w-52 rounded-lg border border-white/[0.18] bg-[#242424] px-2 text-xs text-gray-100 outline-none focus:border-blue-400 disabled:cursor-not-allowed disabled:opacity-60"
				bind:value={selectedModelId}
				disabled={modelsLoading || phase !== 'idle' || availableModels.length === 0}
				aria-label="测评模型"
				title={phase === 'idle' ? '选择测评模型' : '本试卷已锁定出卷模型'}
			>
				{#each availableModels as model (model.id)}
					<option value={model.id}>
						{model.name || model.id}
					</option>
				{/each}
			</select>

			{#if !fullPage}
				<button
					type="button"
					class="rounded-lg p-1.5 text-gray-400 transition hover:bg-gray-800 hover:text-white"
					onclick={toggleFullscreen}
					aria-label={isFullscreen ? '退出全屏' : '全屏'}
					title={isFullscreen ? '退出全屏' : '全屏'}
				>
					<svg
						class="size-4"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="1.5"
						aria-hidden="true"
					>
						{#if isFullscreen}
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								d="M9 9V4.5M9 9H4.5M9 9 3.75 3.75M9 15v4.5M9 15H4.5M9 15l-5.25 5.25M15 9h4.5M15 9V4.5M15 9l5.25-5.25M15 15h4.5M15 15v4.5m0-4.5 5.25 5.25"
							></path>
						{:else}
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15"
							></path>
						{/if}
					</svg>
				</button>

				{#if onClose}
					<button
						type="button"
						class="rounded-lg p-1.5 text-gray-400 transition hover:bg-gray-800 hover:text-white"
						onclick={() => onClose?.()}
						aria-label="关闭"
					>
						<svg
							class="size-4"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="1.5"
							aria-hidden="true"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								d="M6 18 18 6M6 6l12 12"
							></path>
						</svg>
					</button>
				{/if}
			{/if}
		</div>
	</div>

	{#if phase === 'answering' || phase === 'submitting'}
		<div class="shrink-0 px-3.5 pt-2">
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

	{#if errorMsg}
		<div
			class="mx-3.5 mt-2 shrink-0 rounded-lg bg-red-950/40 px-3 py-2 text-sm text-red-400"
		>
			{errorMsg}
		</div>
	{/if}

	<div class="flex min-h-0 flex-1 flex-col px-3.5 py-3">
		{#if phase === 'idle'}
			<div class="flex h-full flex-col items-center justify-center gap-4 px-4 text-center">
				<div class="text-4xl">📝</div>

				<div class="text-lg font-semibold">
					AI 智能试卷
				</div>

				<p class="max-w-xs text-sm text-gray-400">
					基于课程知识库生成一套包含<b>闪卡填空、选择题、大题</b>的测验卷，提交后自动判分并给出解析。
				</p>

				<input
					class="w-full max-w-xs rounded-lg border border-white/[0.22] bg-transparent px-3 py-2 text-sm text-gray-100 outline-none placeholder:text-gray-500 focus:border-blue-400"
					placeholder="可选：输入测验主题"
					maxlength="100"
					bind:value={topic}
					onkeydown={(event) => {
						if (event.key === 'Enter') {
							startGenerate();
						}
					}}
				/>

				<button
					type="button"
					class="rounded-xl bg-white px-6 py-2.5 text-sm font-medium text-gray-900 transition hover:bg-gray-200"
					onclick={startGenerate}
				>
					生成试卷
				</button>
			</div>
		{:else if phase === 'generating'}
			<div class="flex h-full flex-col items-center justify-center gap-4 px-4 text-center">
				<svg
					class="size-8 animate-spin text-blue-500"
					viewBox="0 0 24 24"
					fill="none"
					aria-hidden="true"
				>
					<circle
						class="opacity-25"
						cx="12"
						cy="12"
						r="10"
						stroke="currentColor"
						stroke-width="4"
					></circle>

					<path
						class="opacity-75"
						fill="currentColor"
						d="M4 12a8 8 0 0 1 8-8v4a4 4 0 0 0-4 4H4z"
					></path>
				</svg>

				<div class="text-sm text-gray-400">
					正在检索知识库并生成试卷，预计需要 30~60 秒…
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
									wide
										? 'grid grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]'
										: 'flex flex-col'
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
												{part}

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
											{currentQuestion.question}
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
																answers[currentQuestion.id] === index
																	? null
																	: index
														};
													}}
												>
													<span class="mr-2 font-mono font-semibold text-gray-400">
														{LETTERS[index]}
													</span>

													{option}
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
											}}
										></textarea>
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
								title={`${question.id} · ${
									hasAnswer(question, answers) ? '已作答' : '未作答'
								}`}
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
							<div
								class="mb-3 font-mono text-xs tracking-[0.2em] text-gray-500 uppercase"
							>
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
									<div
										class="rounded-xl border border-gray-700 bg-gray-800 px-3 py-2"
									>
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
									wide
										? 'grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)]'
										: 'flex flex-col'
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

										<span
											class={`text-xs font-semibold ${verdictClass(
												currentResult.verdict
											)}`}
										>
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
												{currentResultQuestion.text}
											</div>
										{:else if currentResultQuestion.type === 'choice'}
											<div class="leading-relaxed font-medium">
												{currentResultQuestion.question}
											</div>

											<div class="mt-3 space-y-1 text-xs text-gray-400">
												{#each currentResultQuestion.options as option, index}
													<div>
														<span class="mr-2 font-mono">
															{LETTERS[index]}
														</span>

														{option}
													</div>
												{/each}
											</div>
										{:else}
											<div class="leading-relaxed font-medium">
												{currentResultQuestion.question}
											</div>
										{/if}
									{:else}
										<div class="font-medium">
											题目 {currentResult.id}
										</div>
									{/if}

									<div class="mt-5 rounded-xl bg-gray-800 p-3">
										<div class="mb-1 text-[11px] font-semibold text-gray-500">
											我的答案
										</div>

										<div class="text-sm leading-relaxed">
											{currentResult.my_answer !== null &&
											currentResult.my_answer !== undefined &&
											currentResult.my_answer !== ''
												? currentResult.my_answer
												: '未作答'}
										</div>
									</div>
								</section>

								<section
									class="min-h-0 min-w-0 flex-1 space-y-3 overflow-y-auto p-4"
								>
									<div
										class="rounded-xl border border-emerald-900/60 bg-emerald-950/30 p-3"
									>
										<div
											class="mb-1 text-[11px] font-semibold text-emerald-400"
										>
											参考答案
										</div>

										<div class="text-sm leading-relaxed">
											{currentResult.correct_answer}
										</div>
									</div>

									{#if currentResult.feedback}
										<div class="rounded-xl bg-gray-800 p-3">
											<div class="mb-1 text-[11px] font-semibold text-gray-500">
												评语
											</div>

											<div class="text-sm leading-relaxed">
												{currentResult.feedback}
											</div>
										</div>
									{/if}

									{#if currentResult.explanation}
										<div
											class="rounded-xl border border-blue-900/60 bg-blue-950/30 p-3"
										>
											<div class="mb-1 text-[11px] font-semibold text-blue-400">
												解析
											</div>

											<div class="text-sm leading-relaxed text-gray-300">
												{currentResult.explanation}
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
					onclick={restart}
				>
					再来一套
				</button>
			</div>
		{/if}
	</div>
</div>