<script lang="ts">
	type Props = {
		open?: boolean;
		modelName?: string;
		onClose?: () => void;
		onSubmit?: (content: string) => void;
	};

	let {
		open = $bindable(false),
		modelName = '',
		onClose = () => {},
		onSubmit = () => {}
	}: Props = $props();

	type Phase = 'listening' | 'thinking' | 'speaking';
	let phase = $state<Phase>('listening');
	let transcript = $state('');
	let timer: number | null = null;

	const close = () => {
		if (timer) {
			window.clearTimeout(timer);
			timer = null;
		}
		open = false;
		onClose();
	};

	const cycleDemo = () => {
		phase = 'listening';
		transcript = '';
		timer = window.setTimeout(() => {
			transcript = '请用一句话总结这节课的重点';
			phase = 'thinking';
			timer = window.setTimeout(() => {
				phase = 'speaking';
				onSubmit(transcript);
				timer = window.setTimeout(() => {
					phase = 'listening';
					transcript = '';
				}, 1800);
			}, 1200);
		}, 2200);
	};

	$effect(() => {
		if (!open) {
			if (timer) {
				window.clearTimeout(timer);
				timer = null;
			}
			return;
		}
		cycleDemo();
		return () => {
			if (timer) {
				window.clearTimeout(timer);
				timer = null;
			}
		};
	});
</script>

{#if open}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="fixed inset-0 z-[140] flex items-center justify-center bg-black/70 px-4" onclick={close}>
		<div
			class="relative w-full max-w-md rounded-3xl border border-gray-800 bg-gray-900 px-6 py-8 text-center text-white shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			role="dialog"
			aria-modal="true"
			aria-label="语音模式"
		>
			<button
				type="button"
				class="absolute top-3 right-3 rounded-full p-1.5 text-gray-400 hover:bg-gray-800 hover:text-white"
				onclick={close}
				aria-label="关闭语音模式"
			>
				<svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
					<path stroke-linecap="round" d="M6 6l12 12M18 6L6 18"></path>
				</svg>
			</button>

			<div class="mb-2 text-sm text-gray-400">{modelName || '语音模式'}</div>
			<div class="mb-6 text-lg font-medium">
				{#if phase === 'listening'}
					正在倾听...
				{:else if phase === 'thinking'}
					正在思考...
				{:else}
					正在回答...
				{/if}
			</div>

			<button
				type="button"
				class="mx-auto mb-6 flex size-24 items-center justify-center rounded-full bg-white text-black shadow-lg transition hover:bg-gray-100"
				onclick={() => {
					if (phase === 'listening' && transcript) {
						onSubmit(transcript);
						close();
						return;
					}
					if (phase === 'speaking') {
						phase = 'listening';
						transcript = '';
						return;
					}
					cycleDemo();
				}}
				aria-label="语音通话"
			>
				<svg class="size-10" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2.5">
					<path d="M12 4L12 20" stroke-linecap="round"></path>
					<path d="M8 9L8 15" stroke-linecap="round"></path>
					<path d="M20 10L20 14" stroke-linecap="round"></path>
					<path d="M4 10L4 14" stroke-linecap="round"></path>
					<path d="M16 7L16 17" stroke-linecap="round"></path>
				</svg>
			</button>

			<p class="min-h-10 text-sm text-gray-400">
				{transcript || '点击波形可打断 · 教学演示模式'}
			</p>
			<p class="mt-2 text-xs text-gray-600">点击以中断</p>
		</div>
	</div>
{/if}
