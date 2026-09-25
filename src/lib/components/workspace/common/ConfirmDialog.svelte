<script lang="ts">
	type Props = {
		show?: boolean;
		title?: string;
		message?: string;
		confirmLabel?: string;
		onConfirm?: () => void;
		onCancel?: () => void;
	};

	let {
		show = $bindable(false),
		title = '确认删除？',
		message = '此操作无法撤销。',
		confirmLabel = '删除',
		onConfirm = () => {},
		onCancel = () => {}
	}: Props = $props();
</script>

{#if show}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 px-4"
		onclick={() => {
			show = false;
			onCancel();
		}}
	>
		<div
			class="w-full max-w-sm rounded-2xl border border-gray-800 bg-gray-850 p-4 text-white shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			role="dialog"
			aria-modal="true"
		>
			<h3 class="text-base font-medium">{title}</h3>
			<p class="mt-2 text-sm text-gray-400">{message}</p>
			<div class="mt-4 flex justify-end gap-2">
				<button
					type="button"
					class="rounded-xl px-3 py-1.5 text-sm text-gray-400 hover:bg-gray-800"
					onclick={() => {
						show = false;
						onCancel();
					}}
				>
					取消
				</button>
				<button
					type="button"
					class="rounded-xl bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-500"
					onclick={() => {
						show = false;
						onConfirm();
					}}
				>
					{confirmLabel}
				</button>
			</div>
		</div>
	</div>
{/if}
