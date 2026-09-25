<script lang="ts">
	import { onMount } from 'svelte';

	import { circled, type RenderedParagraph } from '$lib/data/essay';

	type Props = {
		/** placeAnnotations() 的产物：区间来自后端，这里只负责画 */
		paragraphs: RenderedParagraph[];
		/** 当前高亮的批注编号（与旁批联动） */
		active?: number | null;
		onActivate?: (n: number | null) => void;
		/** 批改结果刚到时让下划线依次落笔；重复渲染（例如切页回来）时不要再演一遍 */
		animate?: boolean;
		/**
		 * 高亮与旁批互相引用的 id 前缀。同一页有好几份批改时（答疑里一篇篇交稿就会这样）
		 * 必须各给各的，否则 note-mark-1 撞车，点旁批会跳到别的卷子上去。
		 */
		idPrefix?: string;
		class?: string;
	};

	let {
		paragraphs,
		active = null,
		onActivate = () => {},
		animate = false,
		idPrefix = 'note',
		class: className = ''
	}: Props = $props();

	// 初始值只在挂载时读一次：animate 是「这一次挂载要不要演」，不是持续状态
	// svelte-ignore state_referenced_locally
	let shown = $state(!animate);

	onMount(() => {
		if (shown) {
			return;
		}

		// 先以透明下划线画出一帧，下一帧再切到可见，transition 才有起点
		const frame = requestAnimationFrame(() => {
			shown = true;
		});

		return () => cancelAnimationFrame(frame);
	});

	// 悬停联动用指针事件做委托：批注本身是 <mark>，不该变成可点的控件；
	// 键盘用户走旁批那一侧（旁批是按钮），这里只是视觉上的呼应。
	const track = (event: PointerEvent) => {
		const anchor =
			event.target instanceof Element ? event.target.closest<HTMLElement>('[data-note]') : null;
		onActivate(anchor ? Number(anchor.dataset.note) : null);
	};
</script>

<!-- 悬停联动只是视觉呼应，键盘路径在旁批按钮那一侧（见上面 track 的注释） -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class={`annotated ${className}`}
	class:shown
	onpointerover={track}
	onpointerleave={() => onActivate(null)}
>
	{#each paragraphs as paragraph (paragraph.key)}
		<p>
			{#each paragraph.segments as segment, index (index)}
				{#if segment.kind === 'text'}{segment.text}{:else}<mark
						id={`${idPrefix}-mark-${segment.note.n}`}
						class={segment.note.kind}
						class:active={active === segment.note.n}
						data-note={segment.note.n}
						style={`--order: ${segment.note.n}`}
						tabindex="-1"
						aria-describedby={`${idPrefix}-${segment.note.n}`}>{segment.text}</mark
					><sup data-note={segment.note.n} style={`--order: ${segment.note.n}`}
						>{circled(segment.note.n)}</sup
					>{/if}
			{/each}
		</p>
	{/each}
</div>

<style>
	/*
		颜色、缩进、落笔字体都走 CSS 变量，由外层元素设置、靠继承传进来：
		稿纸上是朱笔 + 楷体，整卷暗色面板里是偏亮的红。
		默认值只能写在 var() 的兜底里——写在本组件根元素上会盖掉外层传进来的值。
	*/
	p {
		margin: 0;
		text-indent: var(--indent, 0);
	}

	mark {
		color: inherit;
		background: transparent;
		border-radius: 2px;
		text-decoration-line: underline;
		text-decoration-thickness: 2px;
		text-decoration-color: transparent;
		text-decoration-skip-ink: none;
		text-underline-offset: var(--mark-offset, 0.3em);
		-webkit-box-decoration-break: clone;
		box-decoration-break: clone;
		transition:
			text-decoration-color 0.45s ease-out calc(var(--order) * 140ms + 260ms),
			background-color 0.15s ease;
	}

	/* 好句画波浪线——语文老师的老规矩，学生一眼就认得 */
	mark.praise {
		text-decoration-style: wavy;
		text-decoration-thickness: 1.5px;
	}

	.shown mark {
		text-decoration-color: var(--mark-ink, #f87171);
	}

	mark.active {
		background-color: var(--mark-wash, rgba(248, 113, 113, 0.16));
	}

	mark:focus {
		outline: none;
		background-color: var(--mark-wash, rgba(248, 113, 113, 0.16));
	}

	sup {
		/* line-height: 0 让编号不撑高行盒，稿纸横线才对得齐 */
		line-height: 0;
		margin-left: 0.08em;
		font-family: var(--hand, inherit);
		font-size: 0.72em;
		color: var(--mark-ink, #f87171);
		text-indent: 0;
		opacity: 0;
		transition: opacity 0.3s ease-out calc(var(--order) * 140ms + 420ms);
	}

	.shown sup {
		opacity: 1;
	}

	@media (prefers-reduced-motion: reduce) {
		mark,
		sup {
			transition: none;
		}
	}
</style>
