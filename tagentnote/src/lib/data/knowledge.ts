import { resolve } from '$app/paths';

// 知识源的数据模型与纯函数。
//
// 这里**不放任何知识内容**：笔记本、来源、笔记一律来自 OpenNotebook
// （见 $lib/apis/opennotebook.ts），所以每个函数都要求调用方把 collections 传进来。

export type SourceKind = 'file' | 'note' | 'web';

export type KnowledgeFile = {
	id: string;
	title: string;
	kind: SourceKind;
};

export type KnowledgeCollection = {
	id: string;
	name: string;
	description: string;
	files: KnowledgeFile[];
};

export type Citation = {
	id: string;
	collectionId: string;
	collectionName: string;
	fileId: string;
	title: string;
	kind: SourceKind;
	href: string;
};

export const KIND_LABEL: Record<SourceKind, string> = {
	file: '文件',
	note: '笔记',
	web: '网页'
};

export function sourceKey(collectionId: string, fileId: string) {
	return `${collectionId}||${fileId}`;
}

export function parseSourceKey(key: string) {
	const separator = key.indexOf('||');

	if (separator > 0) {
		return {
			collectionId: key.slice(0, separator),
			fileId: key.slice(separator + 2)
		};
	}

	// OpenNoteBook 的 id 形如 `note:abc`，冒号不能当作分隔符来切，
	// 只有在没有 `||` 的旧链接里才退回这条路径。
	const fallback = key.indexOf(':');

	if (fallback <= 0) {
		return null;
	}

	return {
		collectionId: key.slice(0, fallback),
		fileId: key.slice(fallback + 1)
	};
}

export function findCollection(idOrName: string, collections: KnowledgeCollection[]) {
	const key = idOrName.trim().toLowerCase();

	if (!key) {
		return null;
	}

	return (
		collections.find(
			(collection) => collection.id === idOrName.trim() || collection.name.toLowerCase() === key
		) ?? null
	);
}

export function findSource(key: string, collections: KnowledgeCollection[]) {
	const parsed = parseSourceKey(key);

	if (!parsed) {
		return null;
	}

	const collection = collections.find((item) => item.id === parsed.collectionId);
	const file = collection?.files.find((item) => item.id === parsed.fileId);

	if (!collection || !file) {
		return null;
	}

	return { collection, file };
}

export function sourceKeysForCollection(collectionId: string, collections: KnowledgeCollection[]) {
	const collection = findCollection(collectionId, collections);

	return collection?.files.map((file) => sourceKey(collection.id, file.id)) ?? [];
}

/** 笔记本页的深链。不传 fileId 时只定位到笔记本。 */
export function sourceHref(collectionId: string, fileId = '', from = 'qa') {
	const params = new URLSearchParams({ from, collection: collectionId });

	if (fileId) {
		params.set('file', fileId);
	}

	return resolve(`/notebook?${params.toString()}`);
}
