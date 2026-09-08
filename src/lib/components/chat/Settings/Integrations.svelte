<script lang="ts">
	import Plus from '$lib/components/icons/Plus.svelte';
	import type { ToolServer, UserSettings } from '$lib/data/userSettings';

	type Props = {
		settings: UserSettings;
		saveSettings: (updated: Partial<UserSettings>) => Promise<void> | void;
		onSave?: () => void;
	};

	let { settings, saveSettings, onSave = () => {} }: Props = $props();

	let servers = $state<ToolServer[]>([...(settings.toolServers ?? [])]);
	let showAdd = $state(false);
	let draftUrl = $state('');
	let draftKey = $state('');
	let draftPath = $state('/openapi.json');

	$effect(() => {
		servers = [...(settings.toolServers ?? [])];
	});

	const persist = async () => {
		await saveSettings({ toolServers: servers });
		onSave();
	};

	const addServer = async () => {
		const url = draftUrl.trim().replace(/\/$/, '');
		if (!url) return;
		servers = [
			...servers,
			{ url, key: draftKey.trim(), path: draftPath.trim() || '/openapi.json', enabled: true }
		];
		draftUrl = '';
		draftKey = '';
		draftPath = '/openapi.json';
		showAdd = false;
		await persist();
	};
</script>

<form
	id="tab-tools"
	class="flex h-full flex-col justify-between text-sm"
	onsubmit={(e) => {
		e.preventDefault();
		persist();
	}}
>
	<div class="h-full overflow-y-scroll">
		<div class="pr-1.5">
			<div class="mb-0.5 flex items-center justify-between">
				<div class="font-medium">管理工具服务器</div>
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
						placeholder="https://example.com"
						bind:value={draftUrl}
					/>
					<input
						class="w-full bg-transparent text-xs outline-none"
						placeholder="/openapi.json"
						bind:value={draftPath}
					/>
					<input
						class="w-full bg-transparent text-xs outline-none"
						placeholder="Bearer Token（可选）"
						type="password"
						bind:value={draftKey}
					/>
					<div class="flex justify-end gap-2">
						<button type="button" class="px-2 text-xs text-gray-500" onclick={() => (showAdd = false)}>取消</button>
						<button type="button" class="rounded-full bg-white px-3 py-1 text-xs text-black" onclick={addServer}>添加</button>
					</div>
				</div>
			{/if}

			<div class="flex flex-col gap-1.5">
				{#each servers as server, idx}
					<div class="flex items-center gap-2 rounded-xl border border-gray-800 px-3 py-2">
						<input
							type="checkbox"
							bind:checked={server.enabled}
							onchange={() => {
								servers = [...servers];
								saveSettings({ toolServers: servers });
							}}
						/>
						<div class="min-w-0 flex-1">
							<input
								class="w-full truncate bg-transparent text-xs outline-none"
								bind:value={server.url}
								onchange={() => {
									servers = [...servers];
									saveSettings({ toolServers: servers });
								}}
							/>
							<input
								class="mt-1 w-full bg-transparent text-xs text-gray-500 outline-none"
								bind:value={server.path}
								onchange={() => {
									servers = [...servers];
									saveSettings({ toolServers: servers });
								}}
							/>
						</div>
						<button
							type="button"
							class="text-xs text-red-300"
							onclick={() => {
								servers = servers.filter((_, i) => i !== idx);
								saveSettings({ toolServers: servers });
							}}
						>
							删除
						</button>
					</div>
				{/each}
			</div>

			<div class="my-1.5 text-xs text-gray-500">
				连接到你自己的 OpenAPI 兼容外部工具服务器。
				<br />
				提供方必须正确配置 CORS。
			</div>
			<div class="mb-2 text-xs text-gray-300">
				<a
					class="underline"
					href="https://github.com/open-webui/openapi-servers"
					target="_blank"
					rel="noreferrer">了解更多关于 OpenAPI 工具服务器 ↗</a
				>
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
