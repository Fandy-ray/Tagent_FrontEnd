import { env } from '$env/dynamic/public';

import {
	type KnowledgeCollection,
	type KnowledgeFile,
	type SourceKind
} from '$lib/data/knowledge';

type NotebookListItem = {
	id: string;
	name: string;
	description?: string | null;
	archived?: boolean;
	source_count?: number;
	note_count?: number;
};

type SourceListItem = {
	id: string;
	title?: string | null;
	status?: string | null;
	asset?: {
		file_path?: string | null;
		url?: string | null;
	} | null;
};

type NoteListItem = {
	id: string;
	title?: string | null;
	name?: string | null;
};

const DEFAULT_API_URL = 'http://localhost:5055';

export function getOpenNotebookApiUrl() {
	const explicit = env.PUBLIC_OPENNOTEBOOK_API_URL?.trim();

	if (explicit) {
		return explicit.replace(/\/$/, '');
	}

	const ui = env.PUBLIC_OPENNOTEBOOK_URL?.trim();

	if (!ui) {
		return DEFAULT_API_URL;
	}

	try {
		const url = new URL(ui.includes('://') ? ui : `http://${ui}`);

		if (url.port === '8502' || url.port === '') {
			url.port = '5055';
		}

		url.pathname = '';
		url.search = '';
		url.hash = '';

		return url.toString().replace(/\/$/, '');
	} catch {
		return DEFAULT_API_URL;
	}
}

const fileNameFromPath = (path: string) => {
	const trimmed = path.trim();
	const parts = trimmed.split(/[\\/]/);

	return parts[parts.length - 1] || trimmed;
};

const sourceTitle = (source: SourceListItem) => {
	const title = source.title?.trim();

	if (title && title !== 'Processing...') {
		return title;
	}

	const path = source.asset?.file_path || source.asset?.url || '';

	return fileNameFromPath(path) || '未命名来源';
};

const sourceKind = (source: SourceListItem): SourceKind => {
	if (source.asset?.url) {
		return 'web';
	}

	return 'file';
};

const toSourceFile = (source: SourceListItem): KnowledgeFile => {
	const processing = source.status && source.status !== 'completed';
	const title = sourceTitle(source);

	return {
		id: source.id,
		title: processing ? `${title}（处理中）` : title,
		kind: sourceKind(source)
	};
};

const toNoteFile = (note: NoteListItem): KnowledgeFile => ({
	id: note.id,
	title: note.title?.trim() || note.name?.trim() || '未命名笔记',
	kind: 'note'
});

export type NotebookSummary = {
	id: string;
	name: string;
	description?: string | null;
	note_count?: number;
};

export type CreatedNote = {
	id: string;
	title: string | null;
	content: string | null;
};

const fetchJson = async <T>(path: string, signal?: AbortSignal): Promise<T> => {
	const response = await fetch(`${getOpenNotebookApiUrl()}${path}`, { signal });

	if (!response.ok) {
		throw new Error(`OpenNoteBook ${path} ${response.status}`);
	}

	return (await response.json()) as T;
};

const postJson = async <T>(path: string, body: unknown): Promise<T> => {
	const response = await fetch(`${getOpenNotebookApiUrl()}${path}`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json'
		},
		body: JSON.stringify(body)
	});

	if (!response.ok) {
		const detail = await response.text().catch(() => '');
		throw new Error(`OpenNoteBook ${path} ${response.status}${detail ? `: ${detail}` : ''}`);
	}

	return (await response.json()) as T;
};

export async function listNotebooks(signal?: AbortSignal): Promise<NotebookSummary[]> {
	return fetchJson<NotebookSummary[]>(
		'/api/notebooks?archived=false&order_by=updated+desc',
		signal
	);
}

export async function createNotebook(name: string, description = '') {
	return postJson<NotebookSummary>('/api/notebooks', {
		name: name.trim(),
		description
	});
}

export async function createNote(input: {
	title: string;
	content: string;
	notebookId: string;
	noteType?: 'human' | 'ai';
}) {
	return postJson<CreatedNote>('/api/notes', {
		title: input.title,
		content: input.content,
		notebook_id: input.notebookId,
		note_type: input.noteType ?? 'ai'
	});
}

export async function listNotebookKnowledge(
	signal?: AbortSignal
): Promise<KnowledgeCollection[]> {
	const notebooks = await fetchJson<NotebookListItem[]>(
		'/api/notebooks?archived=false&order_by=updated+desc',
		signal ?? new AbortController().signal
	);

	const collections = await Promise.all(
		notebooks.map(async (notebook) => {
			const [sources, notes] = await Promise.all([
				fetchJson<SourceListItem[]>(
					`/api/sources?notebook_id=${encodeURIComponent(notebook.id)}&limit=100&sort_by=updated&sort_order=desc`,
					signal ?? new AbortController().signal
				).catch(() => [] as SourceListItem[]),
				fetchJson<NoteListItem[]>(
					`/api/notes?notebook_id=${encodeURIComponent(notebook.id)}`,
					signal ?? new AbortController().signal
				).catch(() => [] as NoteListItem[])
			]);

			return {
				id: notebook.id,
				name: notebook.name,
				description: notebook.description?.trim() || 'OpenNoteBook 笔记本',
				files: [...sources.map(toSourceFile), ...notes.map(toNoteFile)]
			};
		})
	);

	return collections;
}
