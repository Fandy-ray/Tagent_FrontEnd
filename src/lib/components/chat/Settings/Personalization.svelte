<script lang="ts">
	import Switch from '$lib/components/common/Switch.svelte';
	import type { MemoryItem, UserSettings } from '$lib/data/userSettings';

	type Props = {
		settings: UserSettings;
		saveSettings: (updated: Partial<UserSettings>) => Promise<void> | void;
		onSave?: () => void;
	};

	let { settings, saveSettings, onSave = () => {} }: Props = $props();

	let enableMemory = $state(settings.memory);
	let showManageModal = $state(false);
	let memories = $state<MemoryItem[]>([...(settings.memories ?? [])]);
	let draft = $state('');

	$effect(() => {
		enableMemory = settings.memory;
		memories = [...(settings.memories ?? [])];
	});
</script>

<form
	id="tab-personalization"
	class="flex h-full flex-col justify-between space-y-3 text-sm"
	onsubmit={(e) => {
		e.preventDefault();
		onSave();
	}}
>
	<div class="max-h-[28rem] overflow-y-scroll py-1 md:max-h-full">
		<div class="mb-1 flex items-center justify-between">
			<div class="flex items-center gap-2 text-sm font-medium">
				记忆
				<span
					class="rounded-full bg-gray-800 px-1.5 py-0.5 text-[0.65rem] font-medium uppercase text-gray-400"
					>实验性</span
				>
			</div>
			<Switch
				bind:state={enableMemory}
				onChange={async () => {
					await saveSettings({ memory: enableMemory });
				}}
			/>
		</div>

		<div class="text-xs text-gray-400">
			你可以通过下方「管理」按钮添加记忆，让模型交互更贴合你。
		</div>

		<div class="mb-1 ml-1 mt-3">
			<button
				type="button"
				class="rounded-3xl px-3.5 py-1.5 font-medium outline outline-1 outline-gray-800 hover:bg-white/5"
				onclick={() => {
					showManageModal = true;
				}}
			>
				管理
			</button>
		</div>
	</div>

	<div class="flex justify-end text-sm font-medium">
		<button
			class="rounded-full bg-white px-3.5 py-1.5 text-sm font-medium text-black transition hover:bg-gray-100"
			type="submit"
		>
			保存
		</button>
	</div>
</form>

{#if showManageModal}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-[90] flex items-center justify-center bg-black/70 px-4"
		onclick={() => {
			showManageModal = false;
		}}
	>
		<div
			class="w-full max-w-lg rounded-2xl border border-gray-800 bg-gray-850 p-4 text-sm shadow-2xl"
			onclick={(e) => e.stopPropagation()}
		>
			<div class="mb-3 flex items-center justify-between">
				<div class="font-medium">管理记忆</div>
				<button type="button" class="text-gray-500" onclick={() => (showManageModal = false)}>关闭</button>
			</div>

			<div class="mb-3 max-h-60 space-y-2 overflow-y-auto">
				{#if memories.length === 0}
					<div class="text-xs text-gray-500">暂无记忆</div>
				{:else}
					{#each memories as item}
						<div class="flex items-start gap-2 rounded-xl border border-gray-800 px-3 py-2">
							<div class="min-w-0 flex-1 text-xs text-gray-200">{item.content}</div>
							<button
								type="button"
								class="text-xs text-red-300"
								onclick={() => {
									memories = memories.filter((m) => m.id !== item.id);
									saveSettings({ memories });
								}}
							>
								删除
							</button>
						</div>
					{/each}
				{/if}
			</div>

			<textarea
				class="mb-2 w-full resize-y rounded-xl border border-gray-800 bg-transparent px-3 py-2 text-xs outline-none"
				rows="3"
				placeholder="添加一条新记忆…"
				bind:value={draft}
			></textarea>
			<div class="flex justify-end">
				<button
					type="button"
					class="rounded-full bg-white px-3.5 py-1.5 text-xs font-medium text-black"
					onclick={() => {
						const content = draft.trim();
						if (!content) return;
						memories = [
							...memories,
							{ id: crypto.randomUUID(), content, createdAt: Date.now() }
						];
						draft = '';
						saveSettings({ memories, memory: true });
						enableMemory = true;
					}}
				>
					添加
				</button>
			</div>
		</div>
	</div>
{/if}
