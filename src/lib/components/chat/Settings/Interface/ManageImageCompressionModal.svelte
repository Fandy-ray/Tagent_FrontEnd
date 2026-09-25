<script lang="ts">
	type Props = {
		show?: boolean;
		size?: { width: string; height: string };
		onClose?: () => void;
		onSave?: (size: { width: string; height: string }) => void;
	};

	let {
		show = $bindable(false),
		size = $bindable({ width: '', height: '' }),
		onClose = () => {},
		onSave = () => {}
	}: Props = $props();
</script>

{#if show}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-[90] flex items-center justify-center bg-black/70 px-4"
		onclick={() => {
			show = false;
			onClose();
		}}
	>
		<div
			class="w-full max-w-sm rounded-2xl border border-gray-800 bg-gray-850 p-4 text-sm shadow-2xl"
			onclick={(e) => e.stopPropagation()}
		>
			<div class="mb-3 flex items-center justify-between">
				<div class="text-lg font-medium">管理</div>
				<button type="button" class="text-gray-500" onclick={() => { show = false; onClose(); }}>关闭</button>
			</div>

			<div class="mb-2 text-xs">图像最大压缩尺寸</div>
			<div class="flex items-center gap-2">
				<input
					class="w-full bg-transparent text-center text-sm outline-none"
					type="text"
					inputmode="numeric"
					placeholder="宽度"
					bind:value={size.width}
				/>
				<span class="text-gray-500">×</span>
				<input
					class="w-full bg-transparent text-center text-sm outline-none"
					type="text"
					inputmode="numeric"
					placeholder="高度"
					bind:value={size.height}
				/>
			</div>
			<p class="mt-2 text-[11px] text-gray-500">留空表示不限制对应边。上传图片时将按此上限缩放。</p>

			<div class="mt-4 flex justify-end">
				<button
					type="button"
					class="rounded-full bg-white px-3.5 py-1.5 text-xs font-medium text-black"
					onclick={() => {
						onSave({ ...size });
						show = false;
					}}
				>
					保存
				</button>
			</div>
		</div>
	</div>
{/if}
