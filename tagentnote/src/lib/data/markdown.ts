/**
 * 对话回答的 Markdown 渲染：marked + 公式 + 中文友好的加粗。
 *
 * 公式：模型（DeepSeek 等）写公式多用 \(…\) / \[…\]，也有 $…$ / $$…$$。marked 本身不认公式，
 * 还会把 \[ 当成转义吃掉反斜杠，学生看到的是「[ \lambda_i = \frac{…} ]」。这里在 marked 之前把公式认出来，
 * 交给 KaTeX（$lib/data/math，按需加载；没加载好时按原文显示，不丢字）。
 *
 * 加粗：CommonMark 规定 ** 紧挨标点时要看两边是不是空白，中文没有空格，
 * 「一个**“分时段”的实验**。」这种开头的 ** 就不算数，原样露出两个星号。这里先让 marked 按标准判，
 * 判不成再补判一次：** 后面、收尾 ** 前面不是空白就算加粗。
 *
 * 安全：回答来自模型、模型读的是笔记本里的任意内容，所以整段照旧过 DOMPurify。
 * 公式先换成空的占位 <span>，消毒之后再填回 KaTeX 的输出——KaTeX 的标记不用放进消毒白名单，
 * 它自己对公式原文做转义，且 trust:false（不认 \href 这类注入链接的宏）。
 */
import { Marked, Tokenizer, type TokenizerAndRendererExtension, type Tokens } from 'marked';

import { renderTex } from '$lib/data/math';

// $…$ 用 pandoc 的规矩：$ 后、收尾 $ 前不能是空白，收尾 $ 后不能紧跟数字；再加一条不能紧跟英文字母——
// 「$5 和 $8」「$HOME/$PATH」都不会被当成公式
const INLINE_MATH: [RegExp, boolean][] = [
	[/^\\\[([\s\S]+?)\\\]/, true],
	[/^\$\$([\s\S]+?)\$\$/, true],
	[/^\\\(([\s\S]+?)\\\)/, false],
	[/^\$(?![\s$])([^$\n]+?)(?<![\s\\])\$(?![A-Za-z\d])/, false]
];
const BLOCK_MATH = /^ {0,3}(?:\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\])[ \t]*(?:\n+|$)/;
const FORMULA =
	/\\\([\s\S]+?\\\)|\\\[[\s\S]+?\\\]|\$\$[\s\S]+?\$\$|\$(?![\s$])[^$\n]+?(?<![\s\\])\$(?![A-Za-z\d])/;

// \[…\] 也是 Markdown 里转义方括号的写法（「参考文献 \[1\]」）。写在一行之内的，
// 里面得像公式（有 \ ^ _ = { } < > | 之一）才算；跨行的照算——转义的方括号不会跨行。
const looksLikeTex = (text: string) => text.includes('\n') || /[\\^_={}<>|]/.test(text);

/** 内容里有没有公式（有才去加载 KaTeX） */
export const hasFormula = (content: string) => FORMULA.test(content ?? '');

// 本次 renderMarkdown 收集到的公式 HTML；parse 是同步的，用模块级变量传给扩展的 renderer 就够了。
// 占位符带每次随机的记号：回答里照抄一个占位 <span> 也对不上号，填不进东西。
let slots: string[] = [];
let slotTag = '';

const slot = (html: string) => {
	slots.push(html);
	return `<span data-tex-slot="${slotTag}-${slots.length - 1}"></span>`;
};

type MathToken = Tokens.Generic & { text: string; display: boolean };

const blockMath: TokenizerAndRendererExtension = {
	name: 'blockMath',
	level: 'block',
	// 只认真正的行首（换行之后）：marked 从段落第二个字起问「下一个块从哪开始」，
	// 用 ^…/m 的话「见 \[1\]」里的「 \[」也算行首，段落会被从中间切开、再用换行接回去
	start(src) {
		const match = /\n {0,3}(?:\$\$|\\\[)/.exec(src);
		return match ? match.index + 1 : undefined;
	},
	tokenizer(src) {
		const match = BLOCK_MATH.exec(src);
		if (match && (match[2] === undefined || looksLikeTex(match[2]))) {
			return { type: 'blockMath', raw: match[0], text: match[1] ?? match[2] ?? '', display: true };
		}
	},
	renderer: (token) => {
		const { text, raw } = token as MathToken;
		return `<div class="tex-block">${slot(renderTex(text, true, raw.trim()))}</div>\n`;
	}
};

const inlineMath: TokenizerAndRendererExtension = {
	name: 'inlineMath',
	level: 'inline',
	start(src) {
		const index = src.search(/\\[([]|\$/);
		return index >= 0 ? index : undefined;
	},
	tokenizer(src) {
		for (const [pattern, display] of INLINE_MATH) {
			const match = pattern.exec(src);
			if (match) {
				if (src.startsWith('\\[') && !looksLikeTex(match[1])) {
					return; // 转义的方括号，交回 marked 当普通文字
				}
				return { type: 'inlineMath', raw: match[0], text: match[1], display };
			}
		}
	},
	renderer: (token) => {
		const { text, raw, display } = token as MathToken;
		return slot(renderTex(text, display, raw));
	}
};

const standardEmStrong = Tokenizer.prototype.emStrong;

/**
 * 先按 CommonMark 判斜体 / 加粗；判不成、而开头是 ** 时再补判中文的情形。
 * 收尾的 ** 在 maskedSrc 里找：marked 已经把行内代码、链接、转义字符都遮掉了，
 * 「**计算 `x**2` 的值**」不会在代码里收尾。
 */
function emStrong(this: Tokenizer, src: string, maskedSrc: string, prevChar?: string) {
	const token = standardEmStrong.call(this, src, maskedSrc, prevChar);
	if (token || !/^\*\*(?![\s*])/.test(src)) {
		return token;
	}
	const closing = /(?<![\s*])\*\*(?!\*)/g;
	closing.lastIndex = 3; // 中间至少一个字
	const match = closing.exec(maskedSrc.slice(-src.length));
	if (!match) {
		return undefined;
	}
	const text = src.slice(2, match.index);
	const strong: Tokens.Strong = {
		type: 'strong',
		raw: src.slice(0, match.index + 2),
		text,
		tokens: this.lexer.inlineTokens(text)
	};
	return strong;
}

const markdown = new Marked(
	{ gfm: true, breaks: true },
	{ extensions: [blockMath, inlineMath], tokenizer: { emStrong } }
);

/** Markdown → HTML。sanitize 在公式填回之前对整段跑（浏览器里传 DOMPurify） */
export const renderMarkdown = (
	content: string,
	sanitize: (html: string) => string = (html) => html
) => {
	slots = [];
	slotTag = Math.random().toString(36).slice(2, 10);
	try {
		const html = sanitize(markdown.parse(content ?? '', { async: false }) as string);
		if (slots.length === 0) {
			return html;
		}
		const filled = slots;
		const pattern = new RegExp(`<span data-tex-slot="${slotTag}-(\\d+)"></span>`, 'g');
		return html.replace(pattern, (_, index: string) => filled[Number(index)] ?? '');
	} finally {
		slots = [];
	}
};
