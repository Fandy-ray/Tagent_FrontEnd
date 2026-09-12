import { env } from '$env/dynamic/public';

import { type Citation } from '$lib/data/knowledge';
import type { ExamReview, PublicExam } from '$lib/data/exam';
import type { FlashDeck } from '$lib/data/flash';

// 试卷相关的形状统一在 $lib/data 里声明（后端 pydantic 保证），这里只做转发，
// 免得同一份契约在 api 层和组件里各写一遍还写不一样。
export type { ExamReview, FlashDeck, PublicExam };

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
