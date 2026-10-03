/**
 * 把 LLM 输出里的 LaTeX 渲染成 HTML。
 *
 * 出题 prompt（`app/prompts/exam_prompts.py:41`）要求"公式一律用 $...$ 或
 * $$...$$ 包裹，前端会渲染"——但前端长期没有任何数学渲染器，那句承诺一直是空头的，
 * `$$\\lambda/\\mu$$` 就原样当文字显示。这个模块把它补上。
 *
 * 安全：题面来自模型，而模型读的是笔记本里的任意内容，所以**非公式部分一律转义**，
 * 公式部分交给 KaTeX（`trust: false`，不认 \\href/\\url 这类会注入链接的宏）。
 * 调用方用 {@html} 渲染本函数的返回值是安全的；直接 {@html} 原始题面则不是。
 *
 * KaTeX 有两百多 KB，按需加载（loadKatex）：测评首页、没有公式的卷子都用不着它，
 * 以前静态打进测评页，页面一打开就要先下它。加载完成之前，公式先按原文（$…$）转义显示。
 */

type Katex = typeof import('katex').default;

let katex: Katex | null = null;
let loading: Promise<boolean> | null = null;

/** 加载 KaTeX 及其样式。失败（断网等）返回 false、下次再试，公式先按原文显示 */
export const loadKatex = (): Promise<boolean> =>
	(loading ??= Promise.all([import('katex'), import('katex/dist/katex.min.css')])
		.then(([mod]) => {
			katex = mod.default;
			return true;
		})
		.catch(() => {
			loading = null;
			return false;
		}));

export const katexLoaded = () => katex !== null;

// $$...$$ 允许跨行；$...$ 不允许，否则「$5 和 $8」这种会被吃成一段公式
const MATH_PATTERN = /\$\$([\s\S]+?)\$\$|\$([^$\n]+?)\$/g;

const ESCAPES: Record<string, string> = {
	'&': '&amp;',
	'<': '&lt;',
	'>': '&gt;',
	'"': '&quot;',
	"'": '&#39;'
};

const escapeHtml = (value: string) => value.replace(/[&<>"']/g, (ch) => ESCAPES[ch]);

// 流式回答每来一段就整篇重画一次，同一个公式会被反复渲染：记住结果，满了就清空重来
const rendered = new Map<string, string>();
const RENDER_CACHE_LIMIT = 500;

/**
 * 渲染一个公式。KaTeX 还没加载好（或渲染失败）时，按 source（公式连同定界符的原文）转义显示，
 * 不吞内容；source 缺省时按 $…$ / $$…$$ 补上定界符。
 */
export const renderTex = (tex: string, displayMode: boolean, source?: string) => {
	const fallback = () => escapeHtml(source ?? (displayMode ? `$$${tex}$$` : `$${tex}$`));

	if (!katex) {
		return fallback();
	}

	const key = `${displayMode ? 'D' : 'I'}${tex}`;
	const hit = rendered.get(key);
	if (hit !== undefined) {
		return hit;
	}

	try {
		const html = katex.renderToString(tex.trim(), {
			displayMode,
			throwOnError: false, // 语法错的公式显示成红色原文，不要整段炸掉
			trust: false,
			strict: 'ignore',
			output: 'html'
		});
		if (rendered.size >= RENDER_CACHE_LIMIT) {
			rendered.clear();
		}
		rendered.set(key, html);
		return html;
	} catch {
		// renderToString 理论上不会抛（throwOnError=false），兜底保证不吞内容
		return fallback();
	}
};

const renderOne = (tex: string, displayMode: boolean) => renderTex(tex, displayMode);

/** 文本里是否含公式。没有就不必走 {@html}。 */
export const hasMath = (value: string) => {
	MATH_PATTERN.lastIndex = 0;
	return MATH_PATTERN.test(value ?? '');
};

/**
 * 没有 $ 包裹、但整条就是一个 LaTeX 式子。
 *
 * prompt 要求公式用 $...$ 包裹，模型在题干里照做了，但 accept 数组里经常直接
 * 裸写 `\rho = \frac{\lambda}{\mu}`——这种如果不管，学生看到的就是一堆反斜杠。
 *
 * 判定刻意收得很紧，避免把正常文字误当公式：整条不含中文、含至少一个
 * \命令、且不长。中文答案里出现反斜杠的概率远低于漏渲染的代价。
 */
const BARE_LATEX = /^[^\u4e00-\u9fa5]*\\[a-zA-Z]+[^\u4e00-\u9fa5]*$/;

const looksLikeBareLatex = (text: string) =>
	text.length > 0 && text.length <= 120 && !text.includes('$') && BARE_LATEX.test(text);

/** 这段文字要不要 KaTeX（有 $…$，或整条就是一个裸 LaTeX 式子） */
export const needsKatex = (raw: string) => hasMath(raw) || looksLikeBareLatex((raw ?? '').trim());

export const renderMathToHtml = (raw: string): string => {
	const text = raw ?? '';

	if (looksLikeBareLatex(text.trim())) {
		return renderOne(text.trim(), false);
	}

	let out = '';
	let last = 0;

	for (const match of text.matchAll(MATH_PATTERN)) {
		const index = match.index ?? 0;
		out += escapeHtml(text.slice(last, index));

		const display = match[1] !== undefined;
		out += renderOne((display ? match[1] : match[2]) ?? '', display);
		last = index + match[0].length;
	}

	return out + escapeHtml(text.slice(last));
};
