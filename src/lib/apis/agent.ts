import { env } from '$env/dynamic/public';

import { type Citation } from '$lib/data/knowledge';

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

export type PublicExam = {
	exam_id: string;
	title: string;
	total_points?: number;
	cloze: Array<Record<string, unknown>>;
	choice: Array<Record<string, unknown>>;
	essay: Array<Record<string, unknown>>;
};

export type ExamReview = {
	exam_id: string;
	total_score: number;
	total_points: number;
	overall_comment: string;
	sections: Record<string, { earned: number; max: number }>;
	results: Array<Record<string, unknown>>;
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
	notebookIds?: string[]
): Promise<PublicExam> {
	const payload = await agentFetch<{ data: PublicExam }>('/quiz/exam/generate', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
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

export async function reviewExam(
	model: string,
	examId: string,
	answers: Record<string, string | number | null>
): Promise<ExamReview> {
	const payload = await agentFetch<{ data: ExamReview }>('/quiz/exam/review', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
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
