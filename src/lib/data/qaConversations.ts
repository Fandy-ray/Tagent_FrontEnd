import { browser } from '$app/environment';

import type { Citation } from '$lib/data/knowledge';
import type { PaperTask } from '$lib/data/paperWorkflow';

export type AssistMode = 'qa' | 'paper';

export type QaMessage = {
	id: string;
	role: 'user' | 'assistant';
	content: string;
	/** 卡片操作只展示简短标签，真正发送给 Agent 的请求保存在这里。 */
	requestContent?: string;
	model?: string;
	citations?: Citation[];
	streaming?: boolean;
	followUps?: string[];
	tags?: string[];
};

export type QaChat = {
	id: string;
	title: string;
	updatedAt: number;
	collectionId?: string;
	folderId?: string | null;
	tags?: string[];
	mode?: AssistMode;
	paperTask?: PaperTask;
	archived?: boolean;
	messages: QaMessage[];
};

const STORAGE_KEY = 'tagentnote.qa.chats.v1';
const MAX_CHATS = 40;

type StoredBundle = {
	chats: QaChat[];
	activeId: string | null;
};

const snapshotMessage = (message: QaMessage): QaMessage => ({
	id: message.id,
	role: message.role,
	content: message.content,
	requestContent: message.requestContent,
	model: message.model,
	citations: message.citations?.map((citation) => ({ ...citation })),
	followUps: message.followUps?.slice(),
	tags: message.tags?.slice(),
	streaming: false
});

const snapshotChat = (chat: QaChat): QaChat => ({
	id: chat.id,
	title: chat.title,
	updatedAt: chat.updatedAt,
	collectionId: chat.collectionId,
	folderId: chat.folderId ?? null,
	tags: chat.tags ? [...chat.tags] : undefined,
	mode: chat.mode,
	paperTask: chat.paperTask
		? {
				...chat.paperTask,
				context: chat.paperTask.context
					? {
							...chat.paperTask.context,
							attachedNotes: Object.fromEntries(
								Object.entries(chat.paperTask.context.attachedNotes ?? {}).map(([key, notes]) => [
									key,
									notes?.map((note) => ({ ...note })) ?? []
								])
							),
							attachedFiles: chat.paperTask.context.attachedFiles?.map((file) => ({ ...file })) ?? []
						}
					: undefined
			}
		: undefined,
	archived: chat.archived,
	messages: chat.messages.map(snapshotMessage)
});

export function loadQaChats(): StoredBundle {
	if (!browser) {
		return { chats: [], activeId: null };
	}

	try {
		const raw = localStorage.getItem(STORAGE_KEY);

		if (!raw) {
			return { chats: [], activeId: null };
		}

		const parsed = JSON.parse(raw) as Partial<StoredBundle>;
		const chats = Array.isArray(parsed.chats)
			? parsed.chats
					.filter((chat) => chat && typeof chat.id === 'string' && Array.isArray(chat.messages))
					.map(snapshotChat)
			: [];
		const activeId =
			typeof parsed.activeId === 'string' && chats.some((chat) => chat.id === parsed.activeId)
				? parsed.activeId
				: null;

		return { chats, activeId };
	} catch {
		return { chats: [], activeId: null };
	}
}

export function saveQaChats(chats: QaChat[], activeId: string | null) {
	if (!browser) {
		return;
	}

	const bundle: StoredBundle = {
		chats: chats.slice(0, MAX_CHATS).map(snapshotChat),
		activeId
	};

	try {
		localStorage.setItem(STORAGE_KEY, JSON.stringify(bundle));
	} catch {
		// Quota or private mode. Keep going with in-memory chats.
	}
}
