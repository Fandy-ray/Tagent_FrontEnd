import assert from 'node:assert/strict';
import test from 'node:test';

const { sourceKeysForCollection } = await import('../src/lib/data/knowledge.ts');

const collections = [
	{
		id: 'notebook:1',
		name: '系统仿真',
		description: '',
		files: [
			{ id: 'source:ok', title: '讲义', kind: 'file', status: 'ready' },
			{ id: 'source:bad', title: '坏链接', kind: 'file', status: 'failed' },
			{ id: 'note:1', title: '笔记', kind: 'note' }
		]
	}
];

test('selecting a whole notebook skips sources that failed to download', () => {
	assert.deepEqual(sourceKeysForCollection('notebook:1', collections), [
		'notebook:1||source:ok',
		'notebook:1||note:1'
	]);
});

test('an unknown notebook selects nothing', () => {
	assert.deepEqual(sourceKeysForCollection('notebook:404', collections), []);
});
