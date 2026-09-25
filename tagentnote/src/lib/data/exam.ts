/**
 * 整卷（试卷模式）共用的类型与渲染工具。
 *
 * 从原来的 MockExamPanel（现 FullExamPanel）里抽出来，让闪卡与整卷两个面板共享同一份判定配色，
 * 不至于哪天改了「部分得分」的颜色只改了一半。
 *
 * 类型按**后端实际下发的字段**声明 —— `to_public()`（app/schema/exam.py:273）
 * 是显式逐字段投影，答案、正确选项、参考答案、解析都不会出现在题面里，
 * 解析只在判卷结果 `results[].explanation` 中返回。
 */

/** 测评的两种模式：闪卡（填空 + 选择、本地判定）与整卷（三段、100 分、AI 判大题）。 */
export type ExamMode = 'flash' | 'full';

export type QuestionType = 'cloze' | 'choice' | 'essay';
export type Verdict = 'correct' | 'partial' | 'wrong' | 'unanswered';

export type ExamAnswer = string | number | null;
export type ExamAnswers = Record<string, ExamAnswer>;

export type ClozeQuestion = {
	id: string;
	type: 'cloze';
	points: number;
	cue: string;
	text: string;
};

export type ChoiceQuestion = {
	id: string;
	type: 'choice';
	points: number;
	question: string;
	options: string[];
};

export type EssayQuestion = {
	id: string;
	type: 'essay';
	points: number;
	question: string;
};

export type PublicQuestion = ClozeQuestion | ChoiceQuestion | EssayQuestion;

export type PublicExam = {
	exam_id: string;
	title: string;
	total_points: number;
	cloze: ClozeQuestion[];
	choice: ChoiceQuestion[];
	essay: EssayQuestion[];
};

export type ReviewResult = {
	id: string;
	type: QuestionType;
	score: number;
	points: number;
	verdict: Verdict;
	my_answer: string | number | null;
	correct_answer: string;
	feedback: string;
	explanation: string;
};

export type ExamSectionReview = {
	earned: number;
	max: number;
};

export type ExamReview = {
	exam_id: string;
	total_score: number;
	total_points: number;
	overall_comment: string;
	sections: Record<QuestionType, ExamSectionReview>;
	results: ReviewResult[];
};

export const LETTERS = ['A', 'B', 'C', 'D'];

export const SECTION_LABELS: Record<QuestionType, string> = {
	cloze: '填空题',
	choice: '选择题',
	essay: '大题'
};

export const hasAnswer = (question: PublicQuestion, answerMap: ExamAnswers) => {
	const answer = answerMap[question.id];

	if (question.type === 'choice') {
		return typeof answer === 'number';
	}

	return typeof answer === 'string' && answer.trim() !== '';
};

export const answerNavClass = (
	question: PublicQuestion,
	index: number,
	currentIndex: number,
	answerMap: ExamAnswers
) =>
	index === currentIndex
		? 'bg-blue-500 text-white border-blue-500'
		: hasAnswer(question, answerMap)
			? 'bg-emerald-950/40 text-emerald-300 border-emerald-900'
			: 'bg-gray-800 text-gray-400 border-gray-700';

export const resultNavClass = (item: ReviewResult) => {
	if (item.verdict === 'correct') {
		return 'bg-emerald-950/40 text-emerald-300 border-emerald-900';
	}

	if (item.verdict === 'partial') {
		return 'bg-amber-950/40 text-amber-300 border-amber-900';
	}

	if (item.verdict === 'unanswered') {
		return 'bg-gray-800 text-gray-400 border-gray-700';
	}

	return 'bg-red-950/40 text-red-300 border-red-900';
};

export const verdictClass = (verdict: Verdict) => {
	if (verdict === 'correct') {
		return 'text-emerald-400';
	}

	if (verdict === 'partial') {
		return 'text-amber-400';
	}

	if (verdict === 'unanswered') {
		return 'text-gray-500';
	}

	return 'text-red-400';
};

export const verdictLabel = (verdict: Verdict) => {
	const labels: Record<Verdict, string> = {
		correct: '✓ 正确',
		partial: '◐ 部分得分',
		wrong: '✗ 错误',
		unanswered: '未作答'
	};

	return labels[verdict];
};

/** 秒 → m:ss。闪卡结算与整卷生成中的计时共用。 */
export const formatDuration = (seconds: number) => {
	const total = Math.max(0, Math.round(seconds));
	return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
};
