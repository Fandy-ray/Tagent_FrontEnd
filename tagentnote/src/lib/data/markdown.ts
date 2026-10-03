/**
 * 对话回答的 Markdown 渲染：marked + 公式 + 中文友好的加粗。
 *
 * 公式：模型（DeepSeek 等）写公式多用 \(…\) / \[…\]，也有 $…$ / $$…$$。marked 本身不认公式，
 * 还会把 \[ 当成转义吃掉反斜杠，学生看到的是「[ \lambda_i = \frac{…} ]」。这里在 marked 之前把公式认出来，
 * 交给 KaTeX（$lib/data/math，按需加载；没加载好时按原文显示，不丢字）。
 *
 * 加粗：CommonMark 规定 ** 紧挨标点时要看两边是不是空白，中文没有空格，
 * 「一个**“分时段”的实验**。」这种开头的 ** 就不算数，原样露出两个星号。这里放宽成：
 * ** 后面、收尾 ** 前面不是空白就算加粗。
 *
 * 安全：回答来自模型、模型读的是笔记本里的任意内容，所以整段照旧过 DOMPurify。
 * 公式先换成空的占位 <span>，消毒之后再填回 KaTeX 的输出——KaTeX 的标记不用放进消毒白名单，
 * 它自己对公式原文做转义，且 trust:false（不认 \href 这类注入链接的宏）。
 */
import { Marked, type TokenizerAndRendererExtension, type Tokens } from 'marked';

import { renderTex } from '$lib/data/math';

// $…$ 用 pandoc 的规矩：$ 后、收尾 $ 前不能是空白，收尾 $ 后不能紧跟数字——「$5 和 $8」不会被当成公式
const INLINE_MATH: [RegExp, boolean][] = [
	[/^\\\[([\s\S]+?)\\\]/, true],
	[/^\$\$([\s\S]+?)\$\$/, true],
	[/^\\\(([\s\S]+?)\\\)/, false],
	[/^\$(?![\s$])([^$\n]+?)(?<![\s\\])\$(?!\d)/, false]
];
const BLOCK_MATH = /^ {0,3}(?:\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\])[ \t]*(?:\n+|$)/;
const FORMULA =
	/\\\([\s\S]+?\\\)|\\\[[\s\S]+?\\\]|\$\$[\s\S]+?\$\$|\$(?![\s$])[^$\n]+?(?<![\s\\])\$(?!\d)/;

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
	start: (src) => src.match(/^ {0,3}(?:\$\$|\\\[)/m)?.index,
	tokenizer(src) {
		const match = BLOCK_MATH.exec(src);
		if (match) {
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
				return { type: 'inlineMath', raw: match[0], text: match[1], display };
			}
		}
	},
	renderer: (token) => {
		const { text, raw, display } = token as MathToken;
		return slot(renderTex(text, display, raw));
	}
};

const cjkStrong: TokenizerAndRendererExtension = {
	name: 'cjkStrong',
	level: 'inline',
	start(src) {
		const index = src.indexOf('**');
		return index >= 0 ? index : undefined;
	},
	tokenizer(src) {
		const match = /^\*\*(?![\s*])((?:\\[\s\S]|[^\\*]|\*(?!\*))+?)(?<![\s\\])\*\*(?!\*)/.exec(src);
		if (match) {
			return {
				type: 'cjkStrong',
				raw: match[0],
				text: match[1],
				tokens: this.lexer.inlineTokens(match[1])
			};
		}
	},
	renderer(token) {
		return `<strong>${this.parser.parseInline(token.tokens ?? [])}</strong>`;
	}
};

const markdown = new Marked(
	{ gfm: true, breaks: true },
	{ extensions: [blockMath, inlineMath, cjkStrong] }
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
