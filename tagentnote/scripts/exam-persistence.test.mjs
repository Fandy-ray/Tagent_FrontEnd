import assert from 'node:assert/strict';
import test from 'node:test';

const { completedAnswerNotes, loadFullExam, saveFullExam } =
	await import('../src/lib/data/exam.ts');
const { annotationLabel, paperReviewMarkdown, placeAnnotations } =
	await import('../src/lib/data/essay.ts');

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
		essay: [{ id: 'essay-1', type: 'essay', points: 10, question: '请作答' }]
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

test('five annotations keep their spans and kinds after a refresh', () => {
	const sentences = [
		'📊假设泊松到达、指数服务、单服务台且先到先服务。',
		'到达率为每小时6人，服务率分别为每小时10人和12人。',
		'方案一的平均逗留时间为15分钟。',
		'方案二的平均逗留时间为10分钟。',
		'仅凭变异系数不等于1不能判断具体分布类型。'
	];
	const source = sentences.join('\n');
	let offset = 0;
	const items = sentences.map((text, index) => {
		const start = offset;
		const end = start + Array.from(text).length;
		offset = end + 1;
		return {
			sentence_id: `P${index + 1}S1`,
			kind: index === 4 ? 'suggestion' : index < 2 ? 'praise' : 'issue',
			comment: index === 4 ? '表达完善：可补充这一结论的适用范围。' : '批注内容',
			start,
			end,
			text
		};
	});
	const review = {
		exam_id: saved.exam.exam_id,
		total_score: 10,
		total_points: 10,
		overall_comment: '全卷已答 1/1 题，得分 10/10。',
		sections: { essay: { earned: 10, max: 10 } },
		results: [
			{
				id: 'essay-1',
				type: 'essay',
				my_answer: source,
				score: 10,
				points: 10,
				feedback: '所有评分要点均已命中。'
			}
		]
	};
	saveFullExam({
		...saved,
		answers: { 'essay-1': source },
		review,
		answerNotes: { 'essay-1': { status: 'done', source, items } }
	});
	const restored = loadFullExam();
	assert.deepEqual(restored.review, review);
	const note = restored.answerNotes['essay-1'];
	assert.deepEqual(note.items, items);
	const placement = placeAnnotations(note.source, note.items);
	assert.equal(placement.placed.length, 5);
	assert.deepEqual(placement.unplaced, []);
	assert.deepEqual(
		placement.placed.map((item) => item.n),
		[1, 2, 3, 4, 5]
	);
	assert.equal(annotationLabel(placement.placed[4].kind), '表达完善');
	assert.deepEqual(
		placement.paragraphs.flatMap((paragraph) =>
			paragraph.segments.filter((segment) => segment.kind === 'mark').map((segment) => segment.text)
		),
		sentences
	);

	const markdown = paperReviewMarkdown(
		{
			score: 100,
			dimensions: [],
			quick_scan: { characters: Array.from(source).length },
			annotations: items,
			overall_comment: ''
		},
		'排队论',
		source
	);
	assert.match(markdown, /【表达完善】「仅凭变异系数/);
	assert.doesNotMatch(markdown, /【需修改】「仅凭变异系数/);
});
