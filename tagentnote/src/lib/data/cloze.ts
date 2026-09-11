/**
 * 填空判定的前端实现 —— 与后端 `app/schema/exam.py:391-424` 是同一套规则。
 *
 * 为什么会有两份：闪卡的答案本来就要下发到浏览器（翻面就是给用户看答案），
 * 既然答案已经在手上，为了比较两个字符串再发一次请求只会让「零等待」落空。
 *
 * 怎么防漂移：
 * 1. 参考答案那一侧**不在这里归一** —— 后端随卡片下发 `accept_normalized`，
 *    这里只归一用户输入，少一半出错的机会。
 * 2. 下面这张用例表与 `basic-agent/tests/test_flash_schema.py` 的
 *    NORMALIZE_CASES 一一对应，改一边就要改另一边。Python 侧有断言，
 *    这里没有测试运行器，靠这条注释和评审。
 *
 *    ('服务机构。', ['服务机构'], 'text')  -> true   首尾中文标点
 *    ('ＭＷ',      ['MW'],       'text')  -> true   NFKC 全角→半角
 *    ('mw',        ['MW'],       'text')  -> true   text 模式不分大小写
 *    ('mW',        ['MW'],       'exact') -> false  exact 模式大小写敏感
 *    ('负  指数',  ['负 指数'],  'text')  -> true   空白折叠
 *    ('服务',      ['服务机构'], 'text')  -> false  上位概念不算对
 *
 * 已知的细微差异：Python 用 `casefold()`，这里用 `toLowerCase()`。两者只在
 * ß / ẞ / 词尾 ς 这几个字符上不同，中文课程内容里不会出现。
 *
 * 注意别把这条当成"以后端为准就行"——闪卡**没有服务端判定**，这里就是唯一的
 * 裁判。真要命中这几个字符，结果就是同一个答案在闪卡里判对、在整卷的填空里
 * （走后端 casefold）判错。要消掉这个缝，只能把两边统一到 `casefold` 的语义，
 * 而不是指望某一边兜底。
 */

export type MatchMode = 'text' | 'exact';

// 与 exam.py 的 _TEXT_STRIP_PUNCT 逐字符一致
const STRIP_PUNCT = '。，,.;；:：!！?？、"\'“”‘’()（）[]【】';

const stripPunct = (value: string) => {
	let start = 0;
	let end = value.length;

	while (start < end && STRIP_PUNCT.includes(value[start])) {
		start += 1;
	}

	while (end > start && STRIP_PUNCT.includes(value[end - 1])) {
		end -= 1;
	}

	return value.slice(start, end);
};

/** 普通文字答案：NFKC → 小写 → 去首尾空白与中英标点 → 空白折叠。 */
export const normalizeTextAnswer = (value: string) =>
	stripPunct((value ?? '').normalize('NFKC').toLowerCase().trim())
		.trim()
		.replace(/\s+/g, ' ');

/** 公式/单位/大小写敏感符号：只做宽度归一与首尾空白清理（mW ≠ MW）。 */
export const normalizeExactAnswer = (value: string) => (value ?? '').normalize('NFKC').trim();

export const normalizeAnswer = (value: string, matchMode: MatchMode) =>
	matchMode === 'exact' ? normalizeExactAnswer(value) : normalizeTextAnswer(value);

/**
 * 用户输入是否命中参考答案。
 *
 * `acceptNormalized` 必须是后端下发的那一份（已按同样规则归一），不要传原始
 * `accept` —— 那样参考侧就没归一，`服务机构。` 之类的写法会判错。
 */
export const clozeMatches = (
	userAnswer: string,
	acceptNormalized: string[],
	matchMode: MatchMode
) => {
	const mine = normalizeAnswer(userAnswer ?? '', matchMode);

	if (!mine) {
		return false;
	}

	return acceptNormalized.includes(mine);
};
