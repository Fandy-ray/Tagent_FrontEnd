<script lang="ts">
	import Switch from '$lib/components/common/Switch.svelte';
	import ManageModal from './Personalization/ManageModal.svelte';
	import { seedFromSettings } from './Personalization/memoryStore';
	import type { UserSettings } from '$lib/data/userSettings';

	type Props = {
		settings: UserSettings;
		saveSettings: (updated: Partial<UserSettings>) => Promise<void> | void;
		onSave?: () => void;
	};

	let { settings, saveSettings, onSave = () => {} }: Props = $props();

	let enableMemory = $state(settings.memory);
	let showManageModal = $state(false);
	let seeded = false;

	$effect(() => {
		enableMemory = settings.memory;
		// One-time seed so the ManageModal has a stable, mock-friendly
		// baseline list even before the user saves anything.
		if (!seeded) {
			seedFromSettings(settings.memories ?? []);
			seeded = true;
		}
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

<ManageModal bind:show={showManageModal} />
