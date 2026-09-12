<script lang="ts">
	import { fade } from 'svelte/transition';
	import type { Snippet } from 'svelte';

	type Props = {
		show?: boolean;
		size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl' | 'full';
		containerClassName?: string;
		className?: string;
		children?: Snippet;
	};

	let {
		show = $bindable(false),
		size = 'md',
		containerClassName = 'p-3',
		className = 'bg-[#171717]/95 backdrop-blur-sm rounded-[1.75rem]',
		children
	}: Props = $props();

	const sizeToWidth = (value: string) => {
		switch (value) {
			case 'full':
				return 'w-full';
			case 'xs':
				return 'w-[16rem]';
			case 'sm':
				return 'w-[30rem]';
			case 'md':
				return 'w-[42rem]';
			case 'lg':
				return 'w-[56rem]';
			case 'xl':
				return 'w-[70rem]';
			case '2xl':
				return 'w-[84rem]';
			case '3xl':
				return 'w-[100rem]';
			default:
				return 'w-[56rem]';
		}
	};

	$effect(() => {
		if (!show) return;
		const onKey = (event: KeyboardEvent) => {
			if (event.key === 'Escape') {
				show = false;
			}
		};
		const prev = document.body.style.overflow;
		document.body.style.overflow = 'hidden';
		window.addEventListener('keydown', onKey);
		return () => {
			document.body.style.overflow = prev;
			window.removeEventListener('keydown', onKey);
		};
	});
</script>

{#if show}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		aria-modal="true"
		role="dialog"
		tabindex="-1"
		class="modal fixed inset-0 z-[9999] flex h-screen max-h-[100dvh] w-full justify-center overflow-y-auto overscroll-contain bg-black/60 {containerClassName}"
		style="scrollbar-gutter: stable;"
		transition:fade={{ duration: 10 }}
		onmousedown={() => {
			show = false;
		}}
	>
		<div
			class="modal-content m-auto min-h-fit max-w-full border border-white/10 shadow-2xl {sizeToWidth(
				size
			)} {size !== 'full' ? 'mx-2' : ''} {className}"
			onmousedown={(e) => e.stopPropagation()}
		>
			{#if children}
				{@render children()}
			{/if}
		</div>
	</div>
{/if}

<style>
	.modal-content {
		animation: scaleUp 0.1s ease-out forwards;
	}

	@keyframes scaleUp {
		from {
			transform: scale(0.985);
			opacity: 0;
		}
		to {
			transform: scale(1);
			opacity: 1;
		}
	}
</style>
