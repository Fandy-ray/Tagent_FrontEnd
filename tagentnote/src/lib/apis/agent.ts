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

export async function streamAgentChat(
	question: string,
	model: string,
	onDelta: (content: string) => void,
	signal?: AbortSignal,
	notebookIds?: string[]
): Promise<{ model: string; content: string }> {
	const response = await fetch(`${agentBase()}/v1/chat/completions`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Accept: 'text/event-stream'
		},
		body: JSON.stringify({
			model,
			stream: true,
			messages: [{ role: 'user', content: question }],
			notebook_ids: notebookIds?.filter(Boolean)
		}),
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

	const consumeFrame = (raw: string) => {
		const data = raw.trim();
		if (!data || data === '[DONE]') {
			return data === '[DONE]';
		}

		try {
			const frame = JSON.parse(data) as {
				model?: string;
				choices?: Array<{ delta?: { content?: string } }>;
			};
			servedModel = frame.model || servedModel;
			const delta = frame.choices?.[0]?.delta?.content;
			if (typeof delta === 'string' && delta) {
				content += delta;
				onDelta(content);
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
					return { model: servedModel, content };
				}
			}
		}
	}

	if (buffer.trim().startsWith('data:')) {
		consumeFrame(buffer.trim().slice(5));
	}

	return { model: servedModel, content };
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
