/**
 * Mock memory store for Personalization settings.
 *
 * Mirrors the shape of the upstream $lib/apis/memories functions
 * (addNewMemory, updateMemoryById, deleteMemoryById, deleteMemoriesByUserId,
 * getMemories) but keeps everything client-side in memory. Items are
 * seeded from the user's persisted settings on first call so the
 * Manage modal still feels connected to whatever the user entered
 * via the legacy inline textarea.
 */

import { writable, get } from 'svelte/store';
import type { MemoryItem } from '$lib/data/userSettings';

export type MemoryRecord = {
	id: string;
	content: string;
	createdAt: number; // unix seconds (mirrors dayjs(memory.updated_at*1000) upstream)
	updatedAt: number;
};

const seed: MemoryRecord[] = [
	{
		id: 'seed-1',
		content: 'User is currently working on a paper-assistant workspace for arXiv.',
		createdAt: Math.floor(Date.now() / 1000) - 86400 * 3,
		updatedAt: Math.floor(Date.now() / 1000) - 86400 * 3
	},
	{
		id: 'seed-2',
		content: 'User prefers concise, technical responses in Chinese.',
		createdAt: Math.floor(Date.now() / 1000) - 86400 * 2,
		updatedAt: Math.floor(Date.now() / 1000) - 86400
	},
	{
		id: 'seed-3',
		content: 'User often asks questions about Svelte 5 runes and Tailwind utilities.',
		createdAt: Math.floor(Date.now() / 1000) - 86400,
		updatedAt: Math.floor(Date.now() / 1000) - 3600 * 4
	}
];

export const memories = writable<MemoryRecord[]>([...seed]);

/** Seed the store from previously persisted MemoryItem[] (newest first). */
export const seedFromSettings = (items: MemoryItem[]) => {
	if (!items || items.length === 0) return;
	const mapped: MemoryRecord[] = items.map((m, idx) => {
		const t = m.createdAt ?? Date.now() - idx * 1000;
		return {
			id: m.id,
			content: m.content,
			createdAt: Math.floor(t / 1000),
			updatedAt: Math.floor(t / 1000)
		};
	});
	memories.set(mapped);
};

export const listMemories = async (): Promise<MemoryRecord[]> => {
	// Simulate a tiny latency so the loading spinner is visible.
	await new Promise((r) => setTimeout(r, 120));
	return get(memories);
};

export const addNewMemory = async (_token: unknown, content: string) => {
	const trimmed = content.trim();
	if (!trimmed) return null;
	const now = Math.floor(Date.now() / 1000);
	const record: MemoryRecord = {
		id: `mem-${crypto.randomUUID()}`,
		content: trimmed,
		createdAt: now,
		updatedAt: now
	};
	memories.update((list) => [record, ...list]);
	await new Promise((r) => setTimeout(r, 80));
	return record;
};

export const updateMemoryById = async (_token: unknown, id: string, content: string) => {
	const trimmed = content.trim();
	if (!trimmed) return null;
	let updated: MemoryRecord | null = null;
	memories.update((list) =>
		list.map((m) => {
			if (m.id !== id) return m;
			updated = { ...m, content: trimmed, updatedAt: Math.floor(Date.now() / 1000) };
			return updated;
		})
	);
	await new Promise((r) => setTimeout(r, 80));
	return updated;
};

export const deleteMemoryById = async (_token: unknown, id: string) => {
	memories.update((list) => list.filter((m) => m.id !== id));
	await new Promise((r) => setTimeout(r, 80));
	return { id };
};

export const deleteMemoriesByUserId = async (_token: unknown) => {
	const count = get(memories).length;
	memories.set([]);
	await new Promise((r) => setTimeout(r, 80));
	return { deleted: count };
};
