/**
 * 范例正文。
 *
 * 正文放在 `src/lib/samples/*.txt`，构建时由 Vite 一起读进来（不走网络、不加接口）。
 * **那个目录里的 .txt 不进仓库**（见 .gitignore）：范例多半是从别处摘来的文章，
 * 版权不在我们手上，留在各自机器上就够了，仓库里只留格式说明。
 *
 * 文件格式（见 src/lib/samples/README.md）：
 *   第一行写题目，空一行，之后是正文；
 *   没有空行就整篇算正文，题目取文件名。
 */

export type EssaySample = {
	id: string;
	title: string;
	topic: string;
	body: string;
};

const files = import.meta.glob('../samples/*.txt', {
	eager: true,
	query: '?raw',
	import: 'default'
}) as Record<string, string>;

const stem = (path: string) =>
	path
		.split('/')
		.pop()
		?.replace(/\.txt$/i, '') ?? path;

const parse = (path: string, raw: string): EssaySample => {
	// 统一换行：Windows 上存的 \r\n 会被后端当成正文字符，行首行尾也会多出空白
	const text = raw.replace(/\r\n?/g, '\n').trim();
	const name = stem(path);
	const [first, second, ...rest] = text.split('\n');

	// 「第一行 + 空行 + 正文」才算带题目，否则整篇都是正文
	if (first && first.trim().length <= 100 && second !== undefined && second.trim() === '') {
		const body = rest.join('\n').trim();

		if (body) {
			return { id: path, title: first.trim(), topic: first.trim(), body };
		}
	}

	return { id: path, title: name, topic: '', body: text };
};

/** 按文件名排序，方便用序号控制出现顺序（01-xxx.txt、02-xxx.txt）。 */
export const essaySamples = (): EssaySample[] =>
	Object.entries(files)
		.sort(([a], [b]) => a.localeCompare(b, 'zh-Hans-CN'))
		.map(([path, raw]) => parse(path, raw))
		.filter((sample) => sample.body.length > 0);
