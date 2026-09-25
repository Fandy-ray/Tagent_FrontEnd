<script lang="ts">
	type Props = {
		show?: boolean;
		floatingActionButtons?: { id: string; label: string; input: boolean; prompt: string }[] | null;
		onClose?: () => void;
		onSave?: (
			buttons: { id: string; label: string; input: boolean; prompt: string }[] | null
		) => void;
	};

	let {
		show = $bindable(false),
		floatingActionButtons = $bindable(null),
		onClose = () => {},
		onSave = () => {}
	}: Props = $props();

	const defaults = () => [
		{
			id: 'ask',
			label: '提问',
			input: true,
			prompt: '{{SELECTED_CONTENT}}\n\n\n{{INPUT_CONTENT}}'
		},
		{
			id: 'explain',
			label: '解释',
			input: false,
			prompt: '{{SELECTED_CONTENT}}\n\n\n解释'
		}
	];

	const ensure = () => {
		if (!floatingActionButtons) floatingActionButtons = defaults();
	};
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
			class="w-full max-w-md rounded-2xl border border-gray-800 bg-gray-850 p-4 text-sm shadow-2xl"
			onclick={(e) => e.stopPropagation()}
		>
			<div class="mb-3 flex items-center justify-between">
				<div class="text-lg font-medium">快捷操作</div>
				<button type="button" class="text-gray-500" onclick={() => { show = false; onClose(); }}>关闭</button>
			</div>

			<div class="mb-2 flex items-center justify-between text-xs">
				<div class="font-medium">操作</div>
				<button
					type="button"
					class="text-gray-400 hover:text-white"
					onclick={() => {
						ensure();
						floatingActionButtons = [
							...(floatingActionButtons ?? []),
							{
								id: crypto.randomUUID().slice(0, 8),
								label: '新操作',
								input: false,
								prompt: '{{SELECTED_CONTENT}}'
							}
						];
					}}
				>
					添加
				</button>
			</div>

			<div class="max-h-72 space-y-2 overflow-y-auto">
				{#if !(floatingActionButtons?.length)}
					<p class="text-xs text-gray-500">使用默认快捷操作，或点击添加自定义项。</p>
				{:else}
					{#each floatingActionButtons as action, idx}
						<div class="space-y-1 rounded-xl border border-gray-800 p-2">
							<input
								class="w-full bg-transparent text-xs outline-none"
								bind:value={action.label}
								placeholder="标签"
							/>
							<textarea
								class="w-full resize-y bg-transparent text-xs outline-none"
								rows="2"
								bind:value={action.prompt}
								placeholder="提示词模板"
							></textarea>
							<div class="flex items-center justify-between text-xs">
								<label class="flex items-center gap-1 text-gray-400">
									<input type="checkbox" bind:checked={action.input} />
									需要额外输入
								</label>
								<button
									type="button"
									class="text-red-300"
									onclick={() => {
										floatingActionButtons = (floatingActionButtons ?? []).filter((_, i) => i !== idx);
										if (!floatingActionButtons.length) floatingActionButtons = null;
									}}
								>
									删除
								</button>
							</div>
						</div>
					{/each}
				{/if}
			</div>

			<div class="mt-3 flex justify-end gap-2">
				<button
					type="button"
					class="rounded-full px-3 py-1.5 text-xs text-gray-400 hover:bg-gray-800"
					onclick={() => {
						floatingActionButtons = null;
					}}
				>
					恢复默认
				</button>
				<button
					type="button"
					class="rounded-full bg-white px-3.5 py-1.5 text-xs font-medium text-black"
					onclick={() => {
						onSave(floatingActionButtons);
						show = false;
					}}
				>
					保存
				</button>
			</div>
		</div>
	</div>
{/if}
