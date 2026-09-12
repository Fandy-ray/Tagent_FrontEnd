<script lang="ts">
	import { renderMathToHtml } from '$lib/data/math';

	type Props = {
		value: string;
		/** 额外的类名；组件本身是 inline 的 <span>，排版由调用方决定 */
		class?: string;
	};

	let { value, class: className = '' }: Props = $props();
</script>

<!--
	这里的 {@html} 是刻意为之，也是经过审的：renderMathToHtml 把非公式部分全部
	转义，公式部分交给 KaTeX 且 trust:false（不认 \href/\url 这类注入链接的宏）。
	题面来自模型、模型又读笔记本里的任意内容，所以**只能**喂它的返回值，
	绝不能把原始题面直接 {@html}。
-->
<!-- eslint-disable-next-line svelte/no-at-html-tags -->
<span class={className}>{@html renderMathToHtml(value)}</span>
