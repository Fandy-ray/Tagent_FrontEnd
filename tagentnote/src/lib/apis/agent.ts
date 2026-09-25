import { env } from '$env/dynamic/public';

import { type Citation } from '$lib/data/knowledge';
import type { AnswerAnnotations, EssayTopic, PaperReview } from '$lib/data/essay';
import type { ExamReview, PublicExam } from '$lib/data/exam';
import type { FlashDeck } from '$lib/data/flash';

// 试卷相关的形状统一在 $lib/data 里声明（后端 pydantic 保证），这里只做转发，
// 免得同一份契约在 api 层和组件里各写一遍还写不一样。
export type { AnswerAnnotations, EssayTopic, ExamReview, FlashDeck, PaperReview, PublicExam };

export type AgentModel = {
	id: string;
	name: string;
	object: 'model';
	created: number;
	owned_by: string;
};

export type AgentModelList = {
	object: 'list';
	data: AgentModel[];
};

export type AgentRagResponse = {
	code: number;
	msg: string;
	data: {
		user_question: string;
		final_answer: string;
		retrieved_context?: string;
		step_log?: string[];
		citations?: Citation[];
	};
	model: string;
};

const agentBase = () => (env.PUBLIC_AGENT_URL?.trim() || '/agent-api').replace(/\/$/, '');

const errorMessage = (payload: unknown, fallback: string) => {
	if (!payload || typeof payload !== 'object') {
		return fallback;
	}

	const record = payload as {
		error?: { message?: string; code?: string };
		msg?: string;
	};

	const code = record.error?.code;
	if (code === 'model_not_found') {
		return '没有这个模型。请回到选择页，选已登记的 DeepSeek 后再进入答疑。';
	}
	if (code === 'upstream_unavailable') {
		return '已经检索了知识库，但连不上 DeepSeek。请检查网络，或确认模型名和 Key 能访问 https://api.deepseek.com。';
	}
	if (code === 'upstream_authentication_error') {
		return 'DeepSeek 拒绝了当前 Key，请重新登记模型。';
	}
	if (code === 'message_too_long' || code === 'messages_too_long') {
		return '这次要发送的内容太长了（单条上限 2 万字）。删掉部分附件内容或任务卡里的长字段再试。';
	}

	return record.error?.message || (record.msg && record.msg !== 'success' ? record.msg : fallback);
};

async function agentFetch<T>(path: string, init?: RequestInit): Promise<T> {
	const response = await fetch(`${agentBase()}${path}`, init);
	const payload = await response.json().catch(() => ({}));

	if (!response.ok) {
		throw new Error(errorMessage(payload, `请求失败（${response.status}）`));
	}

	return payload as T;
}

export async function getAgentModels(): Promise<AgentModelList> {
	return agentFetch<AgentModelList>('/v1/models');
}

const knowledgeCitation = (): Citation => ({
	id: 'retrieved',
	collectionId: 'knowledge',
	collectionName: '知识库',
	fileId: 'retrieved',
	title: '检索到的知识片段',
	kind: 'note',
	href: '#'
});

export async function queryAgentRag(
	question: string,
	model: string,
	_collectionId?: string
): Promise<AgentRagResponse> {
	const payload = await agentFetch<AgentRagResponse>('/rag/query', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			model,
			user_question: question,
			notebook_ids: _collectionId ? [_collectionId] : undefined
		})
	});

	if (!payload.data?.citations) {
		const context = payload.data?.retrieved_context?.trim();
		payload.data = {
			...payload.data,
			citations: context ? [knowledgeCitation()] : []
		};
	}

	return payload;
}

export type AgentChatResult = {
	model: string;
	content: string;
	retrievedContext?: string;
	citations?: unknown[];
};

const asRecord = (value: unknown): Record<string, unknown> | null =>
	value && typeof value === 'object' && !Array.isArray(value)
		? (value as Record<string, unknown>)
		: null;

const mergeCitationPayload = (
	current: { retrievedContext?: string; citations?: unknown[] },
	frame: Record<string, unknown>
) => {
	const retrieved =
		(typeof frame.retrieved_context === 'string' && frame.retrieved_context) ||
		(typeof frame.retrievedContext === 'string' && frame.retrievedContext) ||
		(typeof frame.context === 'string' && frame.context) ||
		'';

	if (retrieved.trim()) {
		current.retrievedContext = retrieved;
	}

	const extra =
		(Array.isArray(frame.citations) && frame.citations) ||
		(Array.isArray(frame.sources) && frame.sources) ||
		(Array.isArray(frame.references) && frame.references) ||
		null;

	if (extra && extra.length > 0) {
		current.citations = extra;
	}

	const data = asRecord(frame.data);
	if (data) {
		mergeCitationPayload(current, data);
	}
};

export type AgentChatMode = 'qa' | 'paper';

export type AgentChatOptions = {
	notebookIds?: string[];
	mode?: AgentChatMode;
	system?: string;
	temperature?: number;
	top_p?: number;
	top_k?: number;
	min_p?: number;
	max_tokens?: number;
	frequency_penalty?: number;
	presence_penalty?: number;
	seed?: number;
	stop?: string[];
	logit_bias?: string;
	reasoning_effort?: string;
	stream_response?: boolean;
	[key: string]: unknown;
};

export async function streamAgentChat(
	question: string,
	model: string,
	onDelta: (content: string) => void,
	signal?: AbortSignal,
	notebookIdsOrOptions?: string[] | AgentChatOptions,
	mode: AgentChatMode = 'qa'
): Promise<AgentChatResult> {
	const options: AgentChatOptions = Array.isArray(notebookIdsOrOptions)
		? { notebookIds: notebookIdsOrOptions, mode }
		: { mode, ...(notebookIdsOrOptions ?? {}) };

	const messages = [
		...(options.system
			? [{ role: 'system' as const, content: options.system }]
			: []),
		{ role: 'user' as const, content: question }
	];

	const body: Record<string, unknown> = {
		model,
		stream: options.stream_response === false ? false : true,
		messages,
		notebook_ids: options.notebookIds?.filter(Boolean),
		// basic-agent：qa=课程答疑 prompt；paper=论文写作 prompt（需后端识别）
		mode: options.mode ?? 'qa'
	};

	const skip = new Set(['notebookIds', 'mode', 'system', 'stream_response']);
	for (const [key, value] of Object.entries(options)) {
		if (skip.has(key) || value === undefined || value === null) continue;
		body[key] = value;
	}

	const response = await fetch(`${agentBase()}/v1/chat/completions`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Accept: 'text/event-stream'
		},
		body: JSON.stringify(body),
		signal
	});

	if (!response.ok) {
		const payload = await response.json().catch(() => ({}));
		throw new Error(errorMessage(payload, `请求失败（${response.status}）`));
	}

	if (!response.body) {
		throw new Error('回答生成失败，请重试。');
	}

	const reader = response.body.getReader();
	const decoder = new TextDecoder();
	let buffer = '';
	let content = '';
	let servedModel = model;
	const extras: { retrievedContext?: string; citations?: unknown[] } = {};

	const consumeFrame = (raw: string) => {
		const data = raw.trim();
		if (!data || data === '[DONE]') {
			return data === '[DONE]';
		}

		try {
			const frame = JSON.parse(data) as Record<string, unknown>;
			servedModel = (typeof frame.model === 'string' && frame.model) || servedModel;
			mergeCitationPayload(extras, frame);
			const choices = Array.isArray(frame.choices) ? frame.choices : [];
			const choice = asRecord(choices[0]);
			const delta = asRecord(choice?.delta) ?? asRecord(choice?.message);
			const piece = typeof delta?.content === 'string' ? delta.content : '';
			if (piece) {
				content += piece;
				onDelta(content);
			}
			if (delta) {
				mergeCitationPayload(extras, delta);
			}
		} catch {
			// Ignore a torn or non-JSON SSE frame and keep reading.
		}

		return false;
	};

	while (true) {
		const { done, value } = await reader.read();
		if (done) {
			break;
		}

		buffer += decoder.decode(value, { stream: true });
		const frames = buffer.split('\n\n');
		buffer = frames.pop() ?? '';

		for (const frame of frames) {
			for (const line of frame.split('\n')) {
				const trimmed = line.trim();
				if (!trimmed.startsWith('data:')) {
					continue;
				}
				if (consumeFrame(trimmed.slice(5))) {
					return {
						model: servedModel,
						content,
						retrievedContext: extras.retrievedContext,
						citations: extras.citations
					};
				}
			}
		}
	}

	if (buffer.trim().startsWith('data:')) {
		consumeFrame(buffer.trim().slice(5));
	}

	return {
		model: servedModel,
		content,
		retrievedContext: extras.retrievedContext,
		citations: extras.citations
	};
}

export async function generateExam(
	model: string,
	topic?: string,
	notebookIds?: string[],
	signal?: AbortSignal
): Promise<PublicExam> {
	const payload = await agentFetch<{ data: PublicExam }>('/quiz/exam/generate', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		signal,
		body: JSON.stringify({
			model,
			topic: topic?.trim() || undefined,
			notebook_ids: notebookIds?.filter(Boolean)
		})
	});

	if (!payload.data?.exam_id) {
		throw new Error('出卷失败：没有返回试卷。');
	}

	return payload.data;
}

/**
 * 闪卡出卡。与 generateExam 是同一套参数与错误映射，只是后端那边只出能本地判定的
 * 题型（填空 + 选择），按材料分片并发。
 *
 * 耗时不写死：实测在 DeepSeek 上闪卡与整卷都是十秒上下，差距在**判卷**——闪卡没有
 * 判卷往返，整卷提交后还要再等模型一轮。（app/config.py 里那组几十秒的旧压测数据
 * 出自另一个没记名字的模型，别拿来当承诺。）
 *
 * 返回的卡片**带答案**（accept / accept_normalized / explanation）—— 翻面就是
 * 给用户看答案，判定也在浏览器本地做，所以没有配套的判卷接口。
 */
export async function generateFlashDeck(
	model: string,
	topic?: string,
	notebookIds?: string[],
	signal?: AbortSignal
): Promise<FlashDeck> {
	const payload = await agentFetch<{ data: FlashDeck }>('/quiz/flash/generate', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		signal,
		body: JSON.stringify({
			model,
			topic: topic?.trim() || undefined,
			notebook_ids: notebookIds?.filter(Boolean)
		})
	});

	if (!payload.data?.deck_id || !payload.data.cards?.length) {
		throw new Error('出卡失败：没有返回闪卡。');
	}

	return payload.data;
}

export async function reviewExam(
	model: string,
	examId: string,
	answers: Record<string, string | number | null>,
	signal?: AbortSignal
): Promise<ExamReview> {
	const payload = await agentFetch<{ data: ExamReview }>('/quiz/exam/review', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		signal,
		body: JSON.stringify({
			model,
			exam_id: examId,
			answers
		})
	});

	if (!payload.data) {
		throw new Error('判卷失败：没有返回结果。');
	}

	return payload.data;
}

/**
 * 小论文批改。三个维度在后端并发打分，论证维度点名了可疑段落时再多一轮逐句批注，
 * 全在这一次请求里完成（方案文档第六节：不做流式）。
 *
 * text 请先用 pyStrip 处理：批注下标是相对后端 strip 之后的正文算的，
 * 前端画高亮必须用同一份正文。
 */
export async function reviewEssay(
	model: string,
	text: string,
	topic?: string,
	notebookIds?: string[],
	signal?: AbortSignal
): Promise<PaperReview> {
	const payload = await agentFetch<{ data: PaperReview }>('/essay/review', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		signal,
		body: JSON.stringify({
			model,
			text,
			topic: topic?.trim() || undefined,
			notebook_ids: notebookIds?.filter(Boolean)
		})
	});

	if (!payload.data || !Array.isArray(payload.data.dimensions)) {
		throw new Error('批改失败：没有返回结果。');
	}

	return payload.data;
}

/**
 * 整卷大题的逐句批注，**按需**调用：学生点开哪道才批哪道，不点就一轮都不花。
 *
 * 题干与评分要点由后端按 exam_id + question_id 回缓存取，不从这里传——
 * 客户端给的评分标准一律不可信。模型必须与出卷时一致，否则后端回 422。
 * 作答不足 40 字（ANNOTATE_MIN_ANSWER_CHARS）时后端直接回空数组。
 */
export async function annotateExamAnswer(
	model: string,
	examId: string,
	questionId: string,
	answer: string,
	signal?: AbortSignal
): Promise<AnswerAnnotations> {
	const payload = await agentFetch<{ data: AnswerAnnotations }>('/quiz/exam/annotate', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		signal,
		body: JSON.stringify({
			model,
			exam_id: examId,
			question_id: questionId,
			answer
		})
	});

	if (!payload.data || !Array.isArray(payload.data.annotations)) {
		throw new Error('批注失败：没有返回结果。');
	}

	return payload.data;
}

/**
 * 答疑论文模式的「出题」：按笔记本材料出一道小论文题。hint 是学生给的选题方向（选填，≤100 字）。
 *
 * 后端检索不到材料也会出题（课程通用题），这时 grounded=false。
 */
export async function generateEssayTopic(
	model: string,
	hint?: string,
	notebookIds?: string[],
	signal?: AbortSignal
): Promise<EssayTopic> {
	const payload = await agentFetch<{ data: EssayTopic }>('/essay/topic', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		signal,
		body: JSON.stringify({
			model,
			topic: hint?.trim() || undefined,
			notebook_ids: notebookIds?.filter(Boolean)
		})
	});

	if (!payload.data?.title || !Array.isArray(payload.data.requirements)) {
		throw new Error('出题失败：没有返回题目。');
	}

	return payload.data;
}
