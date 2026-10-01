<script lang="ts">
	import { getI18nContext } from '$lib/i18n';
	const i18n = getI18nContext();

	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import { updateMemoryById, type MemoryRecord } from './memoryStore';

	type Props = {
		show?: boolean;
		memory?: MemoryRecord | null;
		onSave?: () => void;
	};

	let { show = $bindable(false), memory = null, onSave = () => {} }: Props = $props();

	let loading = false;
	let content = '';

	$effect(() => {
		if (show && memory) {
			content = memory.content;
		}
	});

	const submitHandler = async () => {
		const trimmed = content.trim();
		if (!trimmed || !memory) return;
		loading = true;
		const res = await updateMemoryById(null, memory.id, trimmed);
		loading = false;
		if (res) {
			show = false;
			onSave();
		}
	};
</script>

<Modal bind:show size="sm">
	<div>
		<div class="flex justify-between px-5 pt-4 pb-2 text-gray-200">
			<div class="self-center text-lg font-medium">
				编辑记忆
			</div>
			<button
				class="self-center"
				aria-label="关闭"
				onclick={() => {
					show = false;
				}}
			>
				<XMark className={'size-5'} />
			</button>
		</div>

		<form
			class="flex w-full flex-col px-5 pb-4 text-gray-200"
			onsubmit={(e) => {
				e.preventDefault();
				submitHandler();
			}}
		>
			<textarea
				bind:value={content}
				class="w-full resize-y rounded-xl border border-gray-800 bg-transparent p-3 text-sm outline-none"
				rows="6"
				placeholder="输入一段关于你自己的细节，供 LLM 在后续对话中调用"
			></textarea>
			<div class="text-xs text-gray-500">
				ⓘ 请使用第一人称「用户」来描述自己（例如：「用户正在学习西班牙语」）
			</div>

			<div class="mt-3 flex justify-end">
				<button
					class="flex items-center gap-2 whitespace-nowrap rounded-full bg-white px-3.5 py-1.5 text-sm font-medium text-black transition hover:bg-gray-100 disabled:cursor-not-allowed"
					type="submit"
					disabled={loading}
				>
					更新
					{#if loading}
						<span class="shrink-0">
							<Spinner />
						</span>
					{/if}
				</button>
			</div>
		</form>
	</div>
</Modal>
