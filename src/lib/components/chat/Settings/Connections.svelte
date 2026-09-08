<script lang="ts">
	import Plus from '$lib/components/icons/Plus.svelte';
	import type { DirectConnection, UserSettings } from '$lib/data/userSettings';

	type Props = {
		settings: UserSettings;
		saveSettings: (updated: Partial<UserSettings>) => Promise<void> | void;
		onSave?: () => void;
	};

	let { settings, saveSettings, onSave = () => {} }: Props = $props();

	let connections = $state<DirectConnection[]>([...(settings.directConnections ?? [])]);
	let showAdd = $state(false);
	let draftUrl = $state('');
	let draftKey = $state('');

	$effect(() => {
		connections = [...(settings.directConnections ?? [])];
	});

	const persist = async () => {
		await saveSettings({ directConnections: connections });
		onSave();
	};

	const addConnection = async () => {
		const url = draftUrl.trim().replace(/\/$/, '');
		if (!url) return;
		connections = [...connections, { url, key: draftKey.trim(), enabled: true }];
		draftUrl = '';
		draftKey = '';
		showAdd = false;
		await persist();
	};
</script>

<form
	id="tab-connections"
	class="flex h-full flex-col justify-between text-sm"
	onsubmit={(e) => {
		e.preventDefault();
		persist();
	}}
>
	<div class="h-full overflow-y-scroll">
		<div class="pr-1.5">
			<div class="mb-0.5 flex items-center justify-between">
				<div class="font-medium">管理直接连接</div>
				<button
					class="px-1"
					type="button"
					aria-label="添加连接"
					onclick={() => {
						showAdd = !showAdd;
					}}
				>
					<Plus />
				</button>
			</div>

			{#if showAdd}
				<div class="mb-2 space-y-2 rounded-xl border border-gray-800 p-3">
					<input
						class="w-full bg-transparent text-xs outline-none"
						placeholder="https://api.openai.com/v1"
						bind:value={draftUrl}
					/>
					<input
						class="w-full bg-transparent text-xs outline-none"
						placeholder="API Key（可选）"
						type="password"
						bind:value={draftKey}
					/>
					<div class="flex justify-end gap-2">
						<button type="button" class="px-2 text-xs text-gray-500" onclick={() => (showAdd = false)}>取消</button>
						<button type="button" class="rounded-full bg-white px-3 py-1 text-xs text-black" onclick={addConnection}>添加</button>
					</div>
				</div>
			{/if}

			<div class="flex flex-col gap-1.5">
				{#each connections as conn, idx}
					<div class="flex items-center gap-2 rounded-xl border border-gray-800 px-3 py-2">
						<input
							type="checkbox"
							bind:checked={conn.enabled}
							onchange={() => {
								connections = [...connections];
								saveSettings({ directConnections: connections });
							}}
						/>
						<div class="min-w-0 flex-1">
							<input
								class="w-full truncate bg-transparent text-xs outline-none"
								bind:value={conn.url}
								onchange={() => {
									connections = [...connections];
									saveSettings({ directConnections: connections });
								}}
							/>
							<input
								class="mt-1 w-full bg-transparent text-xs text-gray-500 outline-none"
								type="password"
								placeholder="API Key"
								bind:value={conn.key}
								onchange={() => {
									connections = [...connections];
									saveSettings({ directConnections: connections });
								}}
							/>
						</div>
						<button
							type="button"
							class="text-xs text-red-300"
							onclick={() => {
								connections = connections.filter((_, i) => i !== idx);
								saveSettings({ directConnections: connections });
							}}
						>
							删除
						</button>
					</div>
				{/each}
			</div>

			<div class="my-1.5 text-xs text-gray-500">
				连接到你自己的 OpenAI 兼容 API 端点。
				<br />
				提供方必须正确配置 CORS，以允许来自本应用的请求。
			</div>
		</div>
	</div>

	<div class="flex justify-end pt-2 text-sm font-medium">
		<button
			class="rounded-full bg-white px-3.5 py-1.5 text-sm font-medium text-black transition hover:bg-gray-100"
			type="submit"
		>
			保存
		</button>
	</div>
</form>
