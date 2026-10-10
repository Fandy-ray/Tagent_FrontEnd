import assert from 'node:assert/strict';
import test from 'node:test';

const { completedAnswerNotes, loadFullExam, saveFullExam } =
	await import('../src/lib/data/exam.ts');

const storage = new Map();
globalThis.sessionStorage = {
	getItem: (key) => storage.get(key) ?? null,
	setItem: (key, value) => storage.set(key, value),
	removeItem: (key) => storage.delete(key)
};

const saved = {
	startedAt: Date.now(),
	modelId: 'deepseek',
	topic: '测试',
	notebookIds: [],
	exam: {
		exam_id: 'exam-test',
		title: '测试卷',
		total_points: 10,
		cloze: [],
		choice: [],
		enessay: [{ id: 'essay-1', type: 'essay', points: 10, question: '请作答' }]
	},
	answers: { 'essay-1': '回答' },
	pageIndex: 0,
	review: null,
	resultIndex: 0,
	answerNotes: {}
};

test('completed full-exam annotations survive save/load', () => {
	const note = { status: 'done', source: '第一句。', items: [] };
	saveFullExam({ ...saved, answerNotes: { 'essay-1': note } });
	assert.deepEqual(loadFullExam()?.answerNotes, { 'essay-1': note });
});

test('in-flight and failed annotations are excluded from persistence', () => {
	assert.deepEqual(
		completedAnswerNotes({
			loading: { status: 'loading', source: '请求中' },
			failed: { status: 'failed', source: '失败', error: '网络错误' },
			done: { status: 'done', source: '完成', items: [] }
		}),
		{ done: { status: 'done', source: '完成', items: [] } }
	);
});

test('old full-exam records without annotations remain loadable', () => {
	storage.set('tagent:full-exam', JSON.stringify({ ...saved, v: 1 }));
	assert.deepEqual(loadFullExam()?.answerNotes, {});
});
