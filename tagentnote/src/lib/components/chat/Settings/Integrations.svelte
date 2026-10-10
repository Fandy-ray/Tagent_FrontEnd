<script lang="ts">
	import { getI18nContext } from '$lib/i18n';
	const i18n = getI18nContext();

	import Spinner from '$lib/components/common/Spinner.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';
	import Connection from './Tools/Connection.svelte';
	import Terminals from './Integrations/Terminals.svelte';

	import AddToolServerModal from './Tools/AddToolServerModal.svelte';

	import type { UserSettings, ToolServer, TerminalServer } from '$lib/data/userSettings';

	type Props = {
		settings: UserSettings;
		saveSettings: (updated: Partial<UserSettings>) => Promise<void> | void;
		onSave?: () => void;
	};

	let { settings, saveSettings, onSave = () => {} }: Props = $props();

	let servers = $state<ToolServer[]>([]);
	let terminalServerConfigs = $state<TerminalServer[]>([]);
	let showConnectionModal = $state(false);
	let loaded = $state(false);

	const loadFromSettings = () => {
		servers = Array.isArray(settings?.toolServers) ? [...settings.toolServers] : [];
		terminalServerConfigs = Array.isArray(settings?.terminalServers)
			? [...settings.terminalServers]
			: [];
		loaded = true;
	};

	$effect(() => {
		if (!loaded) {
			loadFromSettings();
		}
	});

	const addConnectionHandler = async (server: ToolServer) => {
		servers = [...servers, server];
		await updateHandler();
	};

	const updateHandler = async () => {
		await saveSettings({
			toolServers: servers,
			terminalServers: terminalServerConfigs
		});
		onSave();
	};
</script>

<AddToolServerModal bind:show={showConnectionModal} onSubmit={addConnectionHandler} />

<form
	id="tab-tools"
	class="flex h-full flex-col justify-between text-sm"
	onsubmit={(e) => {
		e.preventDefault();
		updateHandler();
	}}
>
	<div class="scrollbar-hidden h-full overflow-y-scroll">
		{#if loaded}
			<div>
				<div class="pr-1.5">
					<div>
						<div class="mb-0.5 flex items-center justify-between">
							<div class="font-medium">{$i18n.t('Manage OpenAPI Tool Servers')}</div>

							<Tooltip content={$i18n.t('Add Connection')}>
								<button
									aria-label={$i18n.t('Add Connection')}
									class="px-1"
									onclick={() => (showConnectionModal = true)}
									type="button"
								>
									<Plus />
								</button>
							</Tooltip>
						</div>

						<div class="flex flex-col gap-1.5">
							{#each servers as _, idx}
								<Connection
									bind:connection={servers[idx]}
									onSubmit={() => updateHandler()}
									onDelete={() => {
										servers = servers.filter((_, i) => i !== idx);
										updateHandler();
									}}
								/>
							{/each}
						</div>
					</div>

					<div class="my-1.5">
						<div class="text-xs text-gray-500">
							{$i18n.t('Connect to your own OpenAPI compatible external tool servers.')}
							<br />
							{$i18n.t(
								'CORS must be properly configured by the provider to allow requests from Open WebUI.'
							)}
						</div>
					</div>

					<div class="mb-2 text-xs text-gray-600 dark:text-gray-300">
						<a
							class="underline"
							href="https://github.com/open-webui/openapi-servers"
							target="_blank">{$i18n.t('Learn more about OpenAPI tool servers.')} ↗</a
						>
					</div>
				</div>

				<hr class="dark:border-gray-850/50 my-4 border-gray-100/50" />

				<div class="pr-1.5">
					<Terminals bind:servers={terminalServerConfigs} onChange={() => updateHandler()} />

					<div class="mt-1.5">
						<div class="text-xs text-gray-500">
							{$i18n.t(
								'Connect to Open Terminal instances to browse files and use them as always-on tools. Only one can be active at a time.'
							)}
						</div>

						<div class="mt-1 text-xs text-gray-600 dark:text-gray-300">
							<a
								class="underline"
								href="https://github.com/open-webui/open-terminal"
								target="_blank">{$i18n.t('Learn more about Open Terminal')} ↗</a
							>
						</div>
					</div>
				</div>
			</div>
		{:else}
			<div class="flex h-full justify-center">
				<div class="my-auto">
					<Spinner className="size-6" />
				</div>
			</div>
		{/if}
	</div>

	<div class="flex justify-end pt-3 text-sm font-medium">
		<button
			class="rounded-full bg-black px-3.5 py-1.5 text-sm font-medium text-white transition hover:bg-gray-900 dark:bg-white dark:text-black dark:hover:bg-gray-100"
			type="submit"
		>
			{$i18n.t('Save')}
		</button>
	</div>
</form>
